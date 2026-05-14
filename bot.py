import os
import requests
import time
import json
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ ---
# Код сам возьмет токен из настроек сервера Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
URL = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/'

user_keys = {}
user_states = {}

# Мини-сервер, чтобы Render не выключал бота
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def send_msg(chat_id, text, reply_markup=None):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    requests.post(f'{URL}sendMessage', data=data)

def get_menu():
    return {
        "keyboard": [[{"text": "🔑 Ввести API ключ"}, {"text": "📖 Туториал"}]],
        "resize_keyboard": True
    }

def generate_and_send(chat_id, prompt, api_key):
    api_host = 'https://api.stability.ai'
    engine_id = 'stable-diffusion-xl-1024-v1-0' 
    try:
        response = requests.post(
            f"{api_host}/v1/generation/{engine_id}/text-to-image",
            headers={
                "Content-Type": "application/json",
                "Accept": "image/png",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 30,
            },
            timeout=60
        )
        if response.status_code != 200:
            send_msg(chat_id, "❌ Ошибка ключа или баланса Stability AI.")
            return
        files = {'photo': ('result.png', response.content)}
        requests.post(f'{URL}sendPhoto', data={'chat_id': chat_id, 'caption': "Готово!"}, files=files)
    except Exception as e:
        send_msg(chat_id, f"❌ Ошибка: {e}")

def handle_update(update):
    msg = update.get("message")
    if not msg or "text" not in msg: return
    chat_id = msg["chat"]["id"]
    text = msg["text"]
    
    if text == "/start":
        user_states[chat_id] = None
        send_msg(chat_id, "👋 Привет! Я бот для генерации картинок.", get_menu())
    elif text == "📖 Туториал":
        send_msg(chat_id, "1. Получи ключ на platform.stability.ai\n2. Нажми 'Ввести API ключ'.")
    elif text == "🔑 Ввести API ключ":
        user_states[chat_id] = "waiting_key"
        send_msg(chat_id, "Жду твой ключ (начинается на sk-...).")
    elif user_states.get(chat_id) == "waiting_key":
        if text.startswith("sk-"):
            user_keys[chat_id] = text
            user_states[chat_id] = None
            send_msg(chat_id, "✅ Ключ привязан!", get_menu())
        else:
            send_msg(chat_id, "❌ Неверный формат ключа.")
    else:
        key = user_keys.get(chat_id)
        if not key:
            send_msg(chat_id, "⚠️ Сначала введи ключ!", get_menu())
        else:
            send_msg(chat_id, "🎨 Рисую...")
            generate_and_send(chat_id, text, key)

def main():
    offset = None
    while True:
        try:
            r = requests.get(f'{URL}getUpdates', params={'timeout': 30, 'offset': offset})
            data = r.json()
            if "result" in data:
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    handle_update(update)
            time.sleep(1)
        except:
            time.sleep(5)

if __name__ == '__main__':
    Thread(target=run_web).start()
    main()
