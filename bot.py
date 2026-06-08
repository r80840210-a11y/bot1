import os
import json
from flask import Flask, request
import telebot
from telebot import types

# Инициализация Flask и Бота
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Файл для вечного хранения статистики и списка админов
STATS_FILE = "/tmp/stats.json"

# Твой личный Telegram ID (Главный админ / Создатель)
CREATOR_ID = 6624873620

# Очередь поиска: [user_id1, user_id2, ...]
search_queue = []

# Активные диалоги: {user_id: partner_id}
active_chats = {}

# Глобальные словари (загружаются из файла)
user_stats = {}
last_partners = {}
admins_list = [] # Список ID дополнительных админов
states = {}      # Для отслеживания шагов рассылки или добавления админов

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ (JSON) ---

def load_stats():
    """Загрузка всей базы данных при старте бота"""
    global user_stats, admins_list
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Извлекаем статистику пользователей
                raw_stats = data.get("user_stats", {})
                user_stats = {int(k): v for k, v in raw_stats.items()}
                # Извлекаем список дополнительных админов
                admins_list = data.get("admins_list", [])
        except Exception as e:
            print(f"Ошибка загрузки базы данных: {e}")
            user_stats = {}
            admins_list = []
    else:
        user_stats = {}
        admins_list = []

def save_stats():
    """Сохранение всей базы данных при любых изменениях"""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            full_data = {
                "user_stats": user_stats,
                "admins_list": admins_list
            }
            json.dump(full_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения базы данных: {e}")

def init_user_stats(user_id):
    """Создание профиля для нового юзера"""
    if user_id not in user_stats:
        user_stats[user_id] = {'chats_count': 0, 'likes': 0, 'dislikes': 0}
        save_stats()

def is_admin(user_id):
    """Проверка, является ли юзер админом"""
    return user_id == CREATOR_ID or user_id in admins_list

# Загружаем базу данных сразу
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

def get_admin_menu():
    """Инлайн-клавиатура для секретной админки"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Статистика и Онлайн", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 Сделать рассылку (Реклама)", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add"))
    return markup


# --- СЕКРЕТНАЯ АДМИН-ПАНЕЛЬ ---

@bot.message_handler(commands=['secretpanel'])
def admin_panel(message):
    user_id = message.chat.id
    if is_admin(user_id):
        bot.send_message(user_id, "⚙️ *Добро пожаловать в секретную админ-панель:*", parse_mode="Markdown", reply_markup=get_admin_menu())
    else:
        # Если пишет чужой — притворяемся, что такой команды нет
        bot.send_message(user_id, "У вас нет активного диалога. Нажмите кнопку ниже, чтобы найти собеседника.", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callbacks(call):
    user_id = call.message.chat.id
    if not is_admin(user_id):
        return

    if call.data == "admin_stats":
        total_users = len(user_stats)
        in_queue = len(search_queue)
        in_chat = len(active_chats) // 2 # Делим на 2, так как в одном чате двое
        
        stats_msg = (
            "📊 *АКТУАЛЬНАЯ СТАТИСТИКА БОТА*\n\n"
            f"👥 Всего юзеров в базе (JSON): {total_users}\n"
            f"⏳ Людей в очереди поиска: {in_queue}\n"
            f"💬 Общаются прямо сейчас (Онлайн): {in_chat} пар(ы)\n"
            f"👑 Дополнительных админов: {len(admins_list)}"
        )
        bot.send_message(user_id, stats_msg, parse_mode="Markdown", reply_markup=get_admin_menu())

    elif call.data == "admin_broadcast":
        states[user_id] = "waiting_for_broadcast_text"
        bot.send_message(user_id, "📢 Введите текст рекламы/сообщения, которое увидят ВСЕ пользователи бота:")

    elif call.data == "admin_add":
        if user_id != CREATOR_ID:
            bot.send_message(user_id, "❌ Только Создатель бота (главный админ) может назначать других админов!")
            return
        states[user_id] = "waiting_for_admin_id"
        bot.send_message(user_id, "➕ Введите Telegram ID пользователя, которого хотите сделать админом:")


# --- ОБРАБОТЧИКИ ОБЫЧНЫХ КОМАНД И КНОПОК ---

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

    if search_queue:
        partner_id = search_queue.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        
        user_stats[user_id]['chats_count'] += 1
        user_stats[partner_id]['chats_count'] += 1
        save_stats()
        
        last_partners[user_id] = partner_id
        last_partners[partner_id] = user_id
        
        bot.send_message(user_id, "🎉 Собеседник найден! Приятного общения.\nЧтобы прервать чат, нажмите кнопку ниже.", reply_markup=get_chat_menu())
        bot.send_message(partner_id, "🎉 Собеседник найден! Приятного общения.\nЧтобы прервать чат, нажмите кнопку ниже.", reply_markup=get_chat_menu())
    else:
        search_queue.append(user_id)
        bot.send_message(user_id, "🔍 Ищу собеседника... Пожалуйста, подождите.", reply_markup=get_search_menu())

@bot.message_handler(func=lambda message: message.text == "❌ Отменить поиск")
def cancel_search(message):
    user_id = message.chat.id
    if user_id in search_queue:
        search_queue.remove(user_id)
        bot.send_message(user_id, "❌ Поиск отменен.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы не находились в поиске.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "🛑 Завершить диалог")
def stop_chat(message):
    user_id = message.chat.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
            
        bot.send_message(user_id, "🛑 Вы завершили диалог. Оцените собеседника:", reply_markup=get_rating_menu())
        bot.send_message(partner_id, "🛑 Собеседник завершил диалог. Оцените собеседника:", reply_markup=get_rating_menu())
    else:
        bot.send_message(user_id, "Вы не находитесь в диалоге.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "👍 Понравился")
def handle_like(message):
    user_id = message.chat.id
    partner_id = last_partners.get(user_id)
    if partner_id:
        init_user_stats(partner_id)
        user_stats[partner_id]['likes'] += 1
        save_stats()
        del last_partners[user_id]
        bot.send_message(user_id, "❤️ Вы поставили лайк собеседнику!", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы уже оценили этого пользователя.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "👎 Скучный")
def handle_dislike(message):
    user_id = message.chat.id
    partner_id = last_partners.get(user_id)
    if partner_id:
        init_user_stats(partner_id)
        user_stats[partner_id]['dislikes'] += 1
        save_stats()
        del last_partners[user_id]
        bot.send_message(user_id, "👎 Вы поставили дизлайк собеседнику.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, "Вы уже оценили этого пользователя.", reply_markup=get_main_menu())


# --- ПЕРЕСЫЛКА И ШПИОНАЖ ЗА ПЕРЕПИСКАМИ ---

@bot.message_handler(content_types=['text', 'photo', 'sticker', 'voice', 'video', 'audio', 'animation', 'document'])
def echo_all(message):
    user_id = message.chat.id
    
    # 1. Проверяем текстовые шаги админки (Рассылка или добавление админа)
    if user_id in states:
        current_state = states[user_id]
        
        if current_state == "waiting_for_broadcast_text" and message.text:
            del states[user_id]
            text_to_send = message.text
            success_count = 0
            # Рассылаем всем из базы данных JSON
            for uid in list(user_stats.keys()):
                try:
                    bot.send_message(uid, text_to_send)
                    success_count += 1
                except:
                    pass
            bot.send_message(user_id, f"📢 Рассылка завершена! Успешно отправлено {success_count} пользователям.")
            return

        elif current_state == "waiting_for_admin_id" and message.text:
            del states[user_id]
            try:
                new_admin_id = int(message.text)
                if new_admin_id not in admins_list:
                    admins_list.append(new_admin_id)
                    save_stats()
                    bot.send_message(user_id, f"➕ Пользователь {new_admin_id} успешно добавлен в список админов!")
                else:
                    bot.send_message(user_id, "Этот пользователь уже есть в списке админов.")
            except ValueError:
                bot.send_message(user_id, "❌ Неверный формат ID. Должно быть только число.")
            return

    # 2. Пересылка сообщений внутри активного чата + Незаметный перехват в твою личку
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        spy_header = f"🕵️‍♂️ *[{user_id}] -> [{partner_id}]:*"
        
        try:
            if message.text:
                bot.send_message(partner_id, message.text)
                # Пересылаем текст тебе в личку (только если это пишешь не ты сам, чтобы не дублировать)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, f"{spy_header}\n{message.text}", parse_mode="Markdown")
                    
            elif message.photo:
                file_id = message.photo[-1].file_id
                bot.send_photo(partner_id, file_id, caption=message.caption)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_photo(CREATOR_ID, file_id, caption=message.caption)
                    
            elif message.sticker:
                file_id = message.sticker.file_id
                bot.send_sticker(partner_id, file_id)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_sticker(CREATOR_ID, file_id)
                    
            elif message.voice:
                file_id = message.voice.file_id
                bot.send_voice(partner_id, file_id)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_voice(CREATOR_ID, file_id)
                    
            elif message.video:
                file_id = message.video.file_id
                bot.send_video(partner_id, file_id, caption=message.caption)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_video(CREATOR_ID, file_id, caption=message.caption)
                    
            elif message.animation:
                file_id = message.animation.file_id
                bot.send_animation(partner_id, file_id)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_animation(CREATOR_ID, file_id)
                    
            elif message.audio:
                file_id = message.audio.file_id
                bot.send_audio(partner_id, file_id, caption=message.caption)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_audio(CREATOR_ID, file_id, caption=message.caption)
                    
            elif message.document:
                file_id = message.document.file_id
                bot.send_document(partner_id, file_id, caption=message.caption)
                if CREATOR_ID != user_id:
                    bot.send_message(CREATOR_ID, spy_header, parse_mode="Markdown")
                    bot.send_document(CREATOR_ID, file_id, caption=message.caption)
        except Exception as e:
            bot.send_message(user_id, "⚠️ Не удалось доставить сообщение. Возможно, собеседник покинул бота.")
    else:
        # Игнорируем нажатия кнопок меню, на обычный текст выводим подсказку
        if message.text not in ["🔍 Искать собеседника", "📊 Мой профиль", "❌ Отменить поиск", "🛑 Завершить диалог", "👍 Понравился", "👎 Скучный", "🔄 Главное меню"]:
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
    bot.set_webhook(url="https://bot1-bwal.onrender.com/" + TOKEN)
    return "Бот работает!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
