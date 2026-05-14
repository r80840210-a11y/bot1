import telebot
from telebot import types
import requests
import os
from flask import Flask
from threading import Thread

# Инициализация бота и веб-сервера
token = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(token)
app = Flask('')

# --- Секция Веб-сервера для Render ---
@app.route('/')
def home():
    return "Бот запущен и работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Секция Бота ---

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    btn_api = types.InlineKeyboardButton("🔑 API Ключ", callback_data="tutorial")
    btn_help = types.InlineKeyboardButton("📖 Как пользоваться", url="https://bot1-bwal.onrender.com/")
    btn_input = types.InlineKeyboardButton("🟡 Ввести API Ключ", callback_data="input_api")
    
    markup.add(btn_api, btn_help, btn_input)
    
    bot.send_message(
        message.chat.id, 
        "👋 Привет! Я бот для генерации картинок через Stability AI.\n\n"
        "1. Нажми 'API Ключ', чтобы узнать как его получить.\n"
        "2. Нажми 'Ввести API Ключ', чтобы привязать его.\n"
        "3. Кнопка 'Как пользоваться' откроет страницу проверки статуса.",
        reply_markup=markup
    )

# Обработка кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "tutorial":
        text = (
            "Как получить API Ключ:\n"
            "1. Зайди на сайт https://platform.stability.ai/account/keys"
            "2. Создай аккаунт и зайди в Profile.\n"
            "3. Скопируй свой API Key и вернись сюда."
        )
        bot.send_message(call.message.chat.id, text)
        
    elif call.data == "input_api":
        sent = bot.send_message(call.message.chat.id, "Отправь мне свой API ключ одним сообщением:")
        bot.register_next_step_handler(sent, save_api_key)

# Сохранение ключа (в памяти на время работы сессии)
user_keys = {}

def save_api_key(message):
    user_keys[message.from_user.id] = message.text
    bot.send_message(message.chat.id, "✅ Ключ успешно привязан! Теперь просто напиши, что хочешь нарисовать (на английском).")

# Генерация изображения
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    api_key = user_keys.get(message.from_user.id)
    
    if not api_key:
        bot.send_message(message.chat.id, "❌ Сначала привяжи API ключ через меню!")
        return

    bot.send_message(message.chat.id, "🎨 Начинаю генерацию, подожди немного...")
    
    try:
        response = requests.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "text_prompts": [{"text": message.text}],
                "cfg_scale": 7,
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 30,
            },
        )

        if response.status_code == 200:
            import base64
            data = response.json()
            for i, image in enumerate(data["artifacts"]):
                image_data = base64.b64decode(image["base64"])
                bot.send_photo(message.chat.id, image_data)
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка API: {response.text}")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Произошла ошибка: {str(e)}")

# Запуск
if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
