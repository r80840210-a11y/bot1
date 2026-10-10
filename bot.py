import os
import asyncio
import secrets
import sqlite3
from contextlib import closing
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = os.environ.get("DB_PATH", "virtual_numbers.db")

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL
        )""")
        db.commit()

def new_phone():
    # Internal identifier only; not a real telephone number.
    return "+7" + "".join(str(secrets.randbelow(10)) for _ in range(10))

def get_or_create_phone(chat_id):
    with closing(sqlite3.connect(DB_PATH)) as db:
        row = db.execute("SELECT phone FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        if row:
            return row[0]
        for _ in range(20):
            phone = new_phone()
            try:
                db.execute("INSERT INTO users(chat_id, phone) VALUES (?, ?)", (chat_id, phone))
                db.commit()
                return phone
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("Could not allocate a unique virtual ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    phone = get_or_create_phone(chat_id)
    await update.message.reply_text(
        "Твой виртуальный номер для собственного приложения:\n"
        f"`{phone}`\n\n"
        "Это внутренний идентификатор, а не реальный телефонный номер. "
        "Когда приложение запросит вход по нему, одноразовый код придёт сюда.",
        parse_mode="Markdown"
    )

async def mynumber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = get_or_create_phone(update.effective_chat.id)
    await update.message.reply_text(f"Твой виртуальный номер: `{phone}`", parse_mode="Markdown")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mynumber", mynumber))
    app.run_polling()

if __name__ == "__main__":
    main()
