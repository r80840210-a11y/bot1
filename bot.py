import os
import json
from flask import Flask, request
import telebot
from telebot import types

# Инициализация Flask и Бота
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Файл для вечного хранения статистики
STATS_FILE = "stats.json"

# Очередь поиска: [user_id1, user_id2, ...]
search_queue = []

# Активные диалоги: {user_id: partner_id}
active_chats = {}

# Глобальный словарь статистики и оценок
user_stats = {}
last_partners = {}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ (JSON) ---

def load_stats():
    """Загрузка статистики из файла при старте бота"""
    global user_stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                # Превращаем ключи обратно в инты (в JSON они всегда строки)
                data = json.load(f)
                user_stats = {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"Ошибка загрузки базы данных: {e}")
            user_stats = {}
    else:
        user_stats = {}

def save_stats():
    """Сохранение статистики в файл при любом изменении"""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения базы данных: {e}")

def init_user_stats(user_id):
    """Создание пустого профиля, если юзер зашел впервые"""
    if user_id not in user_stats:
        user_stats[user_id] = {'chats_count': 0, 'likes': 0, 'dislikes': 0}
        save_stats()

# Загружаем базу данных сразу при запуске скрипта
load_stats()


# --- КЛАВИАТУРЫ ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Искать собеседника"))
    markup.add(types.KeyboardButton("📊 Мой профиль"))
    return markup

def get_search_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отменить поиск"))
    return markup

def get_chat_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛑 Завершить диалог"))
    return markup

def get_rating_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("👍 Понравился"), types.KeyboardButton("👎 Скучный"))
    markup.add(types.KeyboardButton("🔄 Главное меню"))
    return markup


# --- ОБРАБОТЧИКИ КОМАНД И КНОПОК ---

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    init_user_stats(user_id)
    
    welcome_text = (
        "👋 Привет в Анонимном Чат-Рулетке!\n\n"
        "Здесь ты можешь найти случайного собеседника и пообщаться на любые темы.\n"
        "Твой профиль сохраняется автоматически!"
    )
    bot.send_message(user_id, welcome_text, reply_markup=get_main_menu())

# Кнопка "📊 Мой профиль"
@bot.message_handler(func=lambda message: message.text == "📊 Мой профиль")
def show_profile(message):
    user_id = message.chat.id
    init_user_stats(user_id)
    
    stats = user_stats[user_id]
    chats = stats['chats_count']
    likes = stats['likes']
    dislikes = stats['dislikes']
    karma = likes - dislikes
    
    profile_text = (
        "📊 *Ваш профиль в Чат-Рулетке*\n\n"
        f"🗣 Всего собеседников: {chats}\n"
        f"❤️ Лайки: {likes}\n"
        f"💩 Дизлайки: {dislikes}\n"
        f"✨ Репутация (Карма): {karma}\n"
    )
    bot.send_message(user_id, profile_text, parse_mode="Markdown", reply_markup=get_main_menu())

# Кнопка "🔍 Искать собеседника"
@bot.message_handler(func=lambda message: message.text in ["🔍 Искать собеседника", "🔄 Главное меню"])
def start_search(message):
    user_id = message.chat.id
    init_user_stats(user_id)
    
    if user_id in active_chats:
        bot.send_message(user_id, "Вы уже находитесь в диалоге!", reply_markup=get_chat_menu())
        return
        
    if user_id in search_queue:
        bot.send_message(user_id, "Вы уже ищете собеседника.", reply_markup=get_search_menu())
        return

    # Если в очереди кто-то есть — соединяем
    if search_queue:
        partner_id = search_queue.pop(0)
        
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        
        # Обновляем "вечную" статистику чатов
        user_stats[user_id]['chats_count'] += 1
        user_stats[partner_id]['chats_count'] += 1
        save_stats() # Сохраняем в JSON файл
        
        # Запоминаем для системы лайков
        last_partners[user_id] = partner_id
        last_partners[partner_id] = user_id
        
        bot.send_message(user_id, "🎉 Собеседник найден! Приятного общения.\nЧтобы прервать чат, нажмите кнопку ниже.", reply_markup=get_chat_menu())
        bot.send_message(partner_id, "🎉 Собеседник найден! Приятного общения.\nЧтобы прервать чат, нажмите кнопку ниже.", reply_markup=get_chat_menu())
    else:
        # Если никого нет — встаем в очередь
        search_queue.append(user_id)
        bot.send_message(user_id, "🔍 Ищу собеседника... Пожалуйста, подождите.", reply_markup=get_search_menu())

# Кнопка "❌ Отменить поиск"
@bot.message_handler(func=lambda message: message.text == "❌ Отменить поиск")
def cancel_search(message):
    user_id = message.chat.id
    if user_id in search_queue:
        search_queue.remove(user_id)
        bot.send_message(user_id, "❌ Поиск отменен.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы не находились в поиске.", reply_markup=get_main_menu())

# Кнопка "🛑 Завершить диалог"
@bot.message_handler(func=lambda message: message.text == "🛑 Завершить диалог")
def stop_chat(message):
    user_id = message.chat.id
    
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        
        # Удаляем их из активных чатов
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
            
        # Отправляем меню оценки
        bot.send_message(user_id, "🛑 Вы завершили диалог. Оцените собеседника:", reply_markup=get_rating_menu())
        bot.send_message(partner_id, "🛑 Собеседник завершил диалог. Оцените собеседника:", reply_markup=get_rating_menu())
    else:
        bot.send_message(user_id, "Вы не находитесь в диалоге.", reply_markup=get_main_menu())

# Обработка кнопки "👍 Понравился"
@bot.message_handler(func=lambda message: message.text == "👍 Понравился")
def handle_like(message):
    user_id = message.chat.id
    partner_id = last_partners.get(user_id)
    
    if partner_id:
        init_user_stats(partner_id)
        user_stats[partner_id]['likes'] += 1
        save_stats() # Сохраняем лайк
        del last_partners[user_id]
        bot.send_message(user_id, "❤️ Вы поставили лайк собеседнику! Спасибо за оценку.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы уже оценили этого пользователя или еще ни с кем не общались.", reply_markup=get_main_menu())

# Обработка кнопки "👎 Скучный"
@bot.message_handler(func=lambda message: message.text == "👎 Скучный")
def handle_dislike(message):
    user_id = message.chat.id
    partner_id = last_partners.get(user_id)
    
    if partner_id:
        init_user_stats(partner_id)
        user_stats[partner_id]['dislikes'] += 1
        save_stats() # Сохраняем дизлайк
        del last_partners[user_id]
        bot.send_message(user_id, "👎 Вы поставили дизлайк собеседнику.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы уже оценили этого пользователя или еще ни с кем не общались.", reply_markup=get_main_menu())


# --- ПЕРЕСЫЛКА СООБЩЕНИЙ В ЧАТЕ ---

@bot.message_handler(content_types=['text', 'photo', 'sticker', 'voice', 'video', 'audio', 'animation', 'document'])
def echo_all(message):
    user_id = message.chat.id
    
    # Если юзер в активном чате — пересылаем его сообщение собеседнику
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        
        try:
            if message.text:
                bot.send_message(partner_id, message.text)
            elif message.photo:
                bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
            elif message.sticker:
                bot.send_sticker(partner_id, message.sticker.file_id)
            elif message.voice:
                bot.send_voice(partner_id, message.voice.file_id)
            elif message.video:
                bot.send_video(partner_id, message.video.file_id, caption=message.caption)
            elif message.animation:
                bot.send_animation(partner_id, message.animation.file_id)
            elif message.audio:
                bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)
            elif message.document:
                bot.send_document(partner_id, message.document.file_id, caption=message.caption)
        except Exception as e:
            # Если сообщение не дошло (например, партнер заблокировал бота)
            bot.send_message(user_id, "⚠️ Не удалось доставить сообщение. Возможно, собеседник покинул бота.")
    else:
        # Если юзер просто пишет текст вне чата и это не кнопка меню
        bot.send_message(user_id, "У вас нет активного диалога. Нажмите кнопку ниже, чтобы найти собеседника.", reply_markup=get_main_menu())


# --- НАСТРОЙКИ FLASK ДЛЯ RENDER ---

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://your-render-app-name.onrender.com/" + TOKEN) # На Render это подхватится автоматически
    return "Бот работает!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
