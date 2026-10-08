import random
import json
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН_БОТА"

# Файл, в котором сохраняются уже выданные номера
NUMBERS_FILE = "generated_numbers.json"


# ============================================================
# ЗАГРУЗКА УЖЕ ВЫДАННЫХ НОМЕРОВ
# ============================================================

def load_numbers():
    if not os.path.exists(NUMBERS_FILE):
        return set()

    try:
        with open(NUMBERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return set(data)

    except (json.JSONDecodeError, OSError):
        return set()


generated_numbers = load_numbers()


# ============================================================
# СОХРАНЕНИЕ НОМЕРОВ
# ============================================================

def save_numbers():
    with open(NUMBERS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            list(generated_numbers),
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# ГЕНЕРАЦИЯ УНИКАЛЬНОГО ТЕСТОВОГО ЗНАЧЕНИЯ
# ============================================================

def generate_number():

    while True:

        # Генерируем 10 случайных цифр после +7.
        digits = "".join(
            str(random.randint(0, 9))
            for _ in range(10)
        )

        # Формат:
        # +7 XXX XXX XX XX

        number = (
            f"+7 {digits[0:3]} "
            f"{digits[3:6]} "
            f"{digits[6:8]} "
            f"{digits[8:10]}"
        )

        # Если такого значения ещё не было —
        # добавляем его в список.
        if number not in generated_numbers:

            generated_numbers.add(number)
            save_numbers()

            return number


# ============================================================
# КОМАНДА /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Это бот для генерации случайных тестовых номеров.\n\n"
        "📱 /number — получить новый номер\n"
        "📊 /count — количество уже выданных номеров"
    )


# ============================================================
# КОМАНДА /NUMBER
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
# КОМАНДА /COUNT
# ============================================================

async def count(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        f"📊 Уже сгенерировано: {len(generated_numbers)}"
    )


# ============================================================
# ЗАПУСК БОТА
# ============================================================

def main():

    if BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_БОТА":

        print(
            "❌ Ошибка: вставь токен бота "
            "в переменную BOT_TOKEN"
        )

        return

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Команды
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("number", number)
    )

    app.add_handler(
        CommandHandler("count", count)
    )

    print("================================")
    print("🤖 Бот запущен!")
    print("================================")

    app.run_polling()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
