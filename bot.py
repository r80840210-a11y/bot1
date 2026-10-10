import os, secrets, time, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ["BOT_TOKEN"]
CODE_TTL = int(os.getenv("CODE_TTL_SECONDS", "300"))
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+7XXXXXXXXXX")
codes = {}  # Demo only; cleared on restart.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Номер: {PHONE_NUMBER}\n"
        "Команда /code выдаёт внутренний тестовый код.\n"
        "Бот не выдаёт реальные номера и не перехватывает SMS."
    )

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    value = f"{secrets.randbelow(1_000_000):06d}"
    codes[user.id] = {"code": value, "expires": int(time.time()) + CODE_TTL, "used": False}
    await update.message.reply_text(
        f"Номер: {PHONE_NUMBER}\nКод OrdoGram: {value}\n"
        f"Срок действия: {max(1, CODE_TTL // 60)} мин."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start — приветствие\n/code — получить тестовый код")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("code", code))
    app.add_handler(CommandHandler("help", help_command))
    app.run_polling()

if __name__ == "__main__":
    main()
