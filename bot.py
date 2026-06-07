import telebot
from telebot import types
import os
from flask import Flask
from threading import Thread

token = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(token)
app = Flask('')

# База данных в памяти сервера
in_search = []  # Список ID тех, кто ищет собеседника
active_chats = {}  # Словарь пар вида {ID_1: ID_2, ID_2: ID_1}

@app.route('/')
def home():
    return "Чат-рулетка активна и работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Главное меню с кнопками
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Найти собеседника"))
    return markup

def stop_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛑 Завершить диалог"))
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    # Если пользователь был в чате, убираем его оттуда
    if chat_id in active_chats:
        bot.send_message(active_chats[chat_id], "🔴 Собеседник покинул чат.", reply_markup=main_menu())
        del active_chats[active_chats[chat_id]]
        del active_chats[chat_id]
    if chat_id in in_search:
        in_search.remove(chat_id)
        
    bot.send_message(
        chat_id, 
        "👋 Добро пожаловать в Анонимную Чат-Рулетку!\n\n"
        "Нажми кнопку ниже, чтобы найти случайного собеседника. Все диалоги полностью анонимны.", 
        reply_markup=main_menu()
    )

# Обработка текстовых кнопок и сообщений
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'voice', 'sticker'])
def handle_message(message):
    chat_id = message.chat.id
    text = message.text

    # --- КНОПКА: НАЙТИ СОБЕСЕДНИКА ---
    if text == "🔍 Найти собеседника":
        if chat_id in active_chats:
            bot.send_message(chat_id, "⚠️ Вы уже находитесь в активном диалоге!")
            return
        if chat_id in in_search:
            bot.send_message(chat_id, "⏳ Вы уже ищете собеседника...")
            return

        # Если в очереди кто-то есть, соединяем
        if in_search:
            companion_id = in_search.pop(0)
            active_chats[chat_id] = companion_id
            active_chats[companion_id] = chat_id
            
            bot.send_message(chat_id, "🎉 Собеседник найден! Приятного общения. Напиши 'Привет' 👋", reply_markup=stop_menu())
            bot.send_message(companion_id, "🎉 Собеседник найден! Приятного общения. Напиши 'Привет' 👋", reply_markup=stop_menu())
        else:
            # Если никого нет, встаем в очередь
            in_search.append(chat_id)
            bot.send_message(chat_id, "🔍 Ищу собеседника... Пожалуйста, подожди.", reply_markup=types.ReplyKeyboardRemove())

    # --- КНОПКА: ЗАВЕРШИТЬ ДИАЛОГ ---
    elif text == "🛑 Завершить диалог":
        if chat_id in active_chats:
            companion_id = active_chats[chat_id]
            
            bot.send_message(chat_id, "🛑 Вы завершили диалог.", reply_markup=main_menu())
            bot.send_message(companion_id, "🔴 Собеседник завершил диалог.", reply_markup=main_menu())
            
            # Удаляем пару из активных чатов
            del active_chats[chat_id]
            del active_chats[companion_id]
        elif chat_id in in_search:
            in_search.remove(chat_id)
            bot.send_message(chat_id, "❌ Поиск отменен.", reply_markup=main_menu())
        else:
            bot.send_message(chat_id, "Вы не находитесь в диалоге.", reply_markup=main_menu())

    # --- ПЕРЕСЫЛКА СООБЩЕНИЙ СОБЕСЕДНИКУ ---
    else:
        if chat_id in active_chats:
            companion_id = active_chats[chat_id]
            
            # Пересылаем текст, фото, голос или стикеры
            if message.content_type == 'text':
                bot.send_message(companion_id, message.text)
            elif message.content_type == 'photo':
                bot.send_photo(companion_id, message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'voice':
                bot.send_voice(companion_id, message.voice.file_id)
            elif message.content_type == 'sticker':
                bot.send_sticker(companion_id, message.sticker.file_id)
        else:
            bot.send_message(chat_id, "📋 Чтобы начать общение, нажми кнопку «🔍 Найти собеседника»", reply_markup=main_menu())

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
