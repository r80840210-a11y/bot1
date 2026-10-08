import os
import json
import random
import asyncio

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# НАСТРОЙКИ
# ============================================================

# Можно указать токен здесь,
# но на Render лучше создать переменную BOT_TOKEN
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8888756629:AAEaRSG6glNJmkc55_PbN5pix5n3quapJMk"
)

# Render сам передаёт PORT
PORT = int(os.getenv("PORT", "10000"))

HOST = "0.0.0.0"

NUMBERS_FILE = "generated_numbers.json"


# ============================================================
# ЗАГРУЗКА ВЫДАННЫХ НОМЕРОВ
# ============================================================

def load_numbers():
    try:
        with open(
            NUMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        return set(data)

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError
    ):
        return set()


generated_numbers = load_numbers()


# ============================================================
# СОХРАНЕНИЕ
# ============================================================

def save_numbers():

    with open(
        NUMBERS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            list(generated_numbers),
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# ГЕНЕРАЦИЯ УНИКАЛЬНОГО ТЕСТОВОГО НОМЕРА
# ============================================================

def generate_number():

    while True:

        digits = "".join(
            str(random.randint(0, 9))
            for _ in range(10)
        )

        number = (
            f"+7 {digits[0:3]} "
            f"{digits[3:6]} "
            f"{digits[6:8]} "
            f"{digits[8:10]}"
        )

        if number not in generated_numbers:

            generated_numbers.add(number)
            save_numbers()

            return number


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я генерирую случайные тестовые номера.\n\n"
        "📱 /number — получить новый номер\n"
        "📊 /count — сколько уже выдано"
    )


# ============================================================
# /NUMBER
# ============================================================

async def number(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    new_number = generate_number()

    await update.message.reply_text(
        "📱 Новый номер:\n\n"
        f"`{new_number}`",
        parse_mode="Markdown"
    )


# ============================================================
# /COUNT
# ============================================================

async def count(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        f"📊 Уже сгенерировано: "
        f"{len(generated_numbers)}"
    )


# ============================================================
# HTTP SERVER ДЛЯ RENDER
# ============================================================

async def health(request):

    return web.Response(
        text="Bot is running!"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        HOST,
        PORT
    )

    await site.start()

    print(
        f"🌐 HTTP server: "
        f"{HOST}:{PORT}"
    )

    return runner


# ============================================================
# ЗАПУСК
# ============================================================

async def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_СЮДА"
    ):
        print(
            "❌ BOT_TOKEN не установлен!"
        )
        return

    # Создаём Telegram-приложение
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Команды
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "number",
            number
        )
    )

    application.add_handler(
        CommandHandler(
            "count",
            count
        )
    )

    # Запускаем Telegram
    await application.initialize()
    await application.start()

    await application.updater.start_polling()

    # Запускаем HTTP-порт для Render
    web_runner = await start_web_server()

    print("==============================")
    print("🤖 Telegram бот запущен!")
    print("==============================")
    print(
        f"📊 Номеров в базе: "
        f"{len(generated_numbers)}"
    )

    try:

        # Не даём процессу завершиться
        await asyncio.Event().wait()

    finally:

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

        await web_runner.cleanup()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 Бот остановлен."
        )
