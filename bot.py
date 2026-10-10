import os, secrets, time, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ["BOT_TOKEN"]
CODE_TTL = int(os.getenv("CODE_TTL_SECONDS", "300"))
# Demo only: in-memory codes are cleared on restart.
codes = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот тестовой регистрации OrdoGram.\n"
        "Команда /code выдаёт внутренний тестовый код.\n"
        "Бот не выдаёт реальные номера и не перехватывает SMS."
    )

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    value = f"{secrets.randbelow(1_000_000):06d}"
    codes[user.id] = {"code": value, "expires": int(time.time()) + CODE_TTL, "used": False}
    await update.message.reply_text(
        f"Тестовый код OrdoGram: {value}\n"
        f"Действует около {max(1, CODE_TTL // 60)} мин. Используй только для тестовой учётной записи."
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
