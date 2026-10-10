import os
import secrets
import time
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ["BOT_TOKEN"]
CODE_TTL = int(os.getenv("CODE_TTL_SECONDS", "300"))

# Demo only: this is a randomly generated number-shaped placeholder, not a real
# assigned phone number and it cannot receive SMS. Each user gets one per session.
sessions = {}
codes = {}


def make_demo_number():
    # Demo +7 format for UI/testing only; every digit after +7 is random, so this is not guaranteed to be an assigned phone number.
    digits = "".join(str(secrets.randbelow(10)) for _ in range(10))
    return f"+7 ({digits[:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        return


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.setdefault(user_id, {"phone": make_demo_number(), "confirmed": False})
    await update.message.reply_text(
        "Тестовый номер: " + session["phone"] + "\n\n"
        "Это случайный демонстрационный номер: он не является реальной SIM-картой "
        "и не может принимать SMS.\n\n"
        "Когда закончишь тестировать номер, отправь /used — бот выдаст внутренний тестовый код."
    )


async def used(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        await update.message.reply_text("Сначала получи тестовый номер командой /start.")
        return
    if session["confirmed"]:
        await update.message.reply_text("Код уже выдавался для этого тестового номера. Для нового теста отправь /start.")
        return

    session["confirmed"] = True
    value = f"{secrets.randbelow(1_000_000):06d}"
    codes[user_id] = {"code": value, "expires": int(time.time()) + CODE_TTL, "used": False}
    await update.message.reply_text(
        f"Внутренний тестовый код: {value}\n"
        f"Действует {max(1, CODE_TTL // 60)} мин.\n"
        "Это код самого бота, не SMS-код от телефонного оператора или стороннего сервиса."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — получить случайный демонстрационный номер +7\n"
        "/used — подтвердить использование номера и получить внутренний тестовый код\n"
        "/help — помощь"
    )


def main():
    start_health_server()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("used", used))
    app.add_handler(CommandHandler("help", help_command))
    app.run_polling()


if __name__ == "__main__":
    main()
