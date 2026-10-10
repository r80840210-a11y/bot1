import os
import asyncio
import logging
import secrets
import string
from aiohttp import web, ClientSession, ClientTimeout
import asyncpg
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
log = logging.getLogger("ordogram")

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
ORDOGRAM_API_KEY = os.getenv("ORDOGRAM_API_KEY", "")
# Optional API base URL for your own OrdoGram server.
ORDOGRAM_API_URL = os.getenv("ORDOGRAM_API_URL", "").rstrip("/")

# This starter assigns clearly synthetic test identifiers. It does not create
# working phone numbers or receive SMS. Replace with your own provisioned
# number inventory/provider integration if you control real numbers.
TEST_PREFIXES = ("100", "200", "300", "400", "500", "600", "700", "800")


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                assigned_number TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_events (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                event_type TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def make_test_number() -> str:
    # Clearly synthetic test value; not represented as a working phone number.
    digits = secrets.choice(TEST_PREFIXES) + "".join(
        secrets.choice(string.digits) for _ in range(7)
    )
    return f"TEST-{digits[:3]}-{digits[3:6]}-{digits[6:]}"


async def get_or_assign_number(pool: asyncpg.Pool, telegram_id: int) -> str:
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT assigned_number FROM users WHERE telegram_id = $1",
            telegram_id,
        )
        if existing:
            return existing

        # Use a transaction and UNIQUE constraints to avoid duplicate assignments.
        for _ in range(100):
            candidate = make_test_number()
            try:
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id, assigned_number)
                    VALUES ($1, $2)
                    ON CONFLICT (telegram_id) DO NOTHING
                    """,
                    telegram_id, candidate,
                )
                result = await conn.fetchval(
                    "SELECT assigned_number FROM users WHERE telegram_id = $1",
                    telegram_id,
                )
                if result:
                    return result
            except asyncpg.UniqueViolationError:
                continue
        raise RuntimeError("Could not allocate a unique test identifier")


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "👋 Добро пожаловать в OrdoGram!\n\n"
        "/number — получить свой закреплённый тестовый идентификатор\n"
        "/count — количество пользователей\n\n"
        "Это тестовые идентификаторы, они не являются телефонными номерами "
        "и не принимают SMS."
    )


async def number_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool: asyncpg.Pool = context.application.bot_data["pool"]
    user = update.effective_user
    if user is None or update.effective_message is None:
        return
    value = await get_or_assign_number(pool, user.id)
    await update.effective_message.reply_text(
        f"📱 Твой идентификатор OrdoGram:\n`{value}`\n\n"
        "Он закреплён за твоим Telegram-аккаунтом.",
        parse_mode="Markdown",
    )


async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool: asyncpg.Pool = context.application.bot_data["pool"]
    total = await pool.fetchval("SELECT COUNT(*) FROM users")
    await update.effective_message.reply_text(f"📊 Пользователей с назначением: {total}")


async def deliver_ordogram_event(request: web.Request) -> web.Response:
    """Receive an event from your own OrdoGram backend.

    POST /ordogram/event
    Headers: X-OrdoGram-Key: <ORDOGRAM_API_KEY>
    JSON: {"telegram_id": 123, "event": "login_approved",
           "message": "Вход в OrdoGram подтверждён."}

    This endpoint intentionally does not accept or relay login codes. Use a
    safe status notification for account events instead.
    """
    expected = request.app["ordogram_api_key"]
    supplied = request.headers.get("X-OrdoGram-Key", "")
    if not expected or not secrets.compare_digest(supplied, expected):
        raise web.HTTPUnauthorized(text="Unauthorized")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON")

    telegram_id = data.get("telegram_id")
    event = data.get("event")
    message = data.get("message")

    if not isinstance(telegram_id, int) or not isinstance(event, str):
        raise web.HTTPBadRequest(text="telegram_id and event are required")
    if not isinstance(message, str) or not message.strip() or len(message) > 1000:
        raise web.HTTPBadRequest(text="message must be 1-1000 characters")

    allowed_events = {"login_approved", "login_denied", "security_notice"}
    if event not in allowed_events:
        raise web.HTTPBadRequest(text="Unsupported event")

    bot_app: Application = request.app["telegram_application"]
    try:
        await bot_app.bot.send_message(
            chat_id=telegram_id,
            text=f"🔔 OrdoGram\n\n{message.strip()}",
        )
    except Exception:
        log.exception("Could not send event notification to Telegram user %s", telegram_id)
        # Telegram user must start the bot before the bot can message them.
        raise web.HTTPBadRequest(text="Could not message user; ensure they started the bot")

    pool: asyncpg.Pool = request.app["pool"]
    await pool.execute(
        "INSERT INTO verification_events (telegram_id, event_type) VALUES ($1, $2)",
        telegram_id, event,
    )
    return web.json_response({"ok": True})


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "ordogram-bot"})


async def start_http_server(bot_app: Application, pool: asyncpg.Pool) -> web.AppRunner:
    app = web.Application(client_max_size=16 * 1024)
    app["telegram_application"] = bot_app
    app["pool"] = pool
    app["ordogram_api_key"] = ORDOGRAM_API_KEY
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/ordogram/event", deliver_ordogram_event)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("HTTP server listening on 0.0.0.0:%s", PORT)
    return runner


async def main() -> None:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    await init_db(pool)

    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.bot_data["pool"] = pool
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("number", number_cmd))
    bot_app.add_handler(CommandHandler("count", count_cmd))

    await bot_app.initialize()
    await bot_app.start()
    if bot_app.updater is None:
        raise RuntimeError("Telegram updater is unavailable")
    await bot_app.updater.start_polling()

    runner = await start_http_server(bot_app, pool)
    log.info("OrdoGram bot started")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
