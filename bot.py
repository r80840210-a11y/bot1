import telebot
import os
import re
from flask import Flask
from threading import Thread

# Инициализация бота и веб-сервера для Render
token = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(token)
app = Flask('')

# Простой список матерных слов (можно дополнять через запятую)
BAD_WORDS = ['мат1', 'мат2', 'спамворд'] 

@app.route('/')
def home():
    return "Бот-модератор запущен и активен!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Логика модерации ---

@bot.message_handler(func=lambda message: True)
def moderate_chat(message):
    # Игнорируем проверку, если пишет администратор чата
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in ['administrator', 'creator']:
        return

    text = message.text.lower() if message.text else ""

    # 1. Защита от ссылок (удаляет сообщения со ссылками http/https/t.me)
    if re.search(r'(https?://\S+|t\.me/\S+)', text):
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, f"⚠️ {message.from_user.first_name}, ссылки в этом чате запрещены!")
            return
        except Exception as e:
            print(f"Ошибка при удалении ссылки: {e}")

    # 2. Защита от мата
    for word in BAD_WORDS:
        if word in text:
            try:
                bot.delete_message(message.chat.id, message.message_id)
                bot.send_message(message.chat.id, f"🤬 {message.from_user.first_name}, соблюдайте цензуру! Вы получаете предупреждение.")
                return
            except Exception as e:
                print(f"Ошибка при удалении мата: {e}")

# Запуск
if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
