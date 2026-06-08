import os
import json
import time
from flask import Flask, request
import telebot
from telebot import types

# Инициализация Flask и Бота
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Файл для вечного хранения статистики, админов и банов
STATS_FILE = "/tmp/stats.json"

# Твой личный Telegram ID (Главный админ / Создатель)
CREATOR_ID = 6624873620

# Очередь поиска: [user_id1, user_id2, ...]
search_queue = []

# Активные диалоги: {user_id: partner_id}
active_chats = {}

# Глобальные словари
user_stats = {}
last_partners = {}
temporary_admins = {} # {admin_id: timestamp_expire}
banned_users = []     # Список забаненных ID пользователей
states = {}           # {user_id: {'step': '...', 'target_id': ...}}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ (JSON) ---

def load_stats():
    """Загрузка всей базы данных при старте бота"""
    global user_stats, temporary_admins, banned_users
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_stats = data.get("user_stats", {})
                user_stats = {int(k): v for k, v in raw_stats.items()}
                
                raw_admins = data.get("temporary_admins", {})
                temporary_admins = {int(k): v for k, v in raw_admins.items()}
                
                banned_users = data.get("banned_users", [])
        except Exception as e:
            print(f"Ошибка загрузки базы данных: {e}")
    check_expired_admins()

def save_stats():
    """Сохранение всей базы данных при любых изменениях"""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            full_data = {
                "user_stats": user_stats,
                "temporary_admins": temporary_admins,
                "banned_users": banned_users
            }
            json.dump(full_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения базы данных: {e}")

def check_expired_admins():
    """Автоматическое удаление админов, у которых вышло время"""
    global temporary_admins
    current_time = time.time()
    expired = [uid for uid, expire_time in temporary_admins.items() if current_time > expire_time]
    
    if expired:
        for uid in expired:
            del temporary_admins[uid]
            try:
                bot.send_message(uid, "🛑 Срок действия ваших админ-прав истек.")
            except:
                pass
        save_stats()

def is_admin(user_id):
    check_expired_admins()
    return user_id == CREATOR_ID or user_id in temporary_admins

def init_user_stats(user_id):
    if user_id not in user_stats:
        user_stats[user_id] = {'chats_count': 0, 'likes': 0, 'dislikes': 0}
        save_stats()

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
    markup.add(types.KeyboardButton("🚨 Пожаловаться")) # Новая кнопка жалобы
    return markup

def get_rating_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("👍 Понравился"), types.KeyboardButton("👎 Скучный"))
    markup.add(types.KeyboardButton("🔄 Главное меню"))
    return markup

def get_admin_menu(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Статистика и Онлайн", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 Сделать рассылку (Реклама)", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("🔨 Забанить юзера", callback_data="admin_ban"))
    markup.add(types.InlineKeyboardButton("🔓 Разбанить юзера", callback_data="admin_unban"))
    
    if user_id == CREATOR_ID:
        markup.add(types.InlineKeyboardButton("➕ Назначить временного админа", callback_data="admin_add"))
        markup.add(types.InlineKeyboardButton("❌ Разжаловать админа", callback_data="admin_remove"))
    return markup


# --- СЕКРЕТНАЯ АДМИН-ПАНЕЛЬ ---

@bot.message_handler(commands=['secretpanel'])
def admin_panel(message):
    user_id = message.chat.id
    if is_admin(user_id):
        bot.send_message(user_id, "⚙️ *Добро пожаловать в секретную админ-панель:*", parse_mode="Markdown", reply_markup=get_admin_menu(user_id))
    else:
        bot.send_message(user_id, "У вас нет активного диалога. Нажмите кнопку ниже.", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callbacks(call):
    user_id = call.message.chat.id
    if not is_admin(user_id):
        return

    if call.data == "admin_stats":
        total_users = len(user_stats)
        in_queue = len(search_queue)
        in_chat = len(active_chats) // 2
        
        stats_msg = (
            "📊 *АКТУАЛЬНАЯ СТАТИСТИКА БОТА*\n\n"
            f"👥 Всего юзеров в базе (JSON): {total_users}\n"
            f"⏳ Людей в очереди поиска: {in_queue}\n"
            f"💬 Общаются прямо сейчас (Онлайн): {in_chat} пар(ы)\n"
            f"🚫 Забаненных пользователей: {len(banned_users)}\n"
            f"👑 Активных временных админов: {len(temporary_admins)}"
        )
        bot.send_message(user_id, stats_msg, parse_mode="Markdown", reply_markup=get_admin_menu(user_id))

    elif call.data == "admin_broadcast":
        states[user_id] = {'step': "waiting_for_broadcast_text"}
        bot.send_message(user_id, "📢 Введите текст рекламы/сообщения, которое увидят ВСЕ пользователи бота:")

    elif call.data == "admin_ban":
        states[user_id] = {'step': "waiting_for_ban_id"}
        bot.send_message(user_id, "🔨 Введите Telegram ID нарушителя, которого нужно забанить:")

    elif call.data == "admin_unban":
        states[user_id] = {'step': "waiting_for_unban_id"}
        bot.send_message(user_id, "🔓 Введите Telegram ID пользователя для разблокировки:")

    elif call.data == "admin_add":
        if user_id != CREATOR_ID: return
        states[user_id] = {'step': "waiting_for_admin_id"}
        bot.send_message(user_id, "➕ Введите Telegram ID пользователя, которого хотите сделать админом:")

    elif call.data == "admin_remove":
        if user_id != CREATOR_ID: return
        if not temporary_admins:
            bot.send_message(user_id, "Список дополнительных админов сейчас пуст.", reply_markup=get_admin_menu(user_id))
            return
        msg = "📋 *Список текущих админов:*\n"
        for adv_id, expire in temporary_admins.items():
            remains = int((expire - time.time()) / 3600)
            msg += f"• ID: `{adv_id}` (Осталось: ~{remains} ч.)\n"
        msg += "\nВведите ID админа, которого хотите убрать:"
        states[user_id] = {'step': "waiting_for_remove_id"}
        bot.send_message(user_id, msg, parse_mode="Markdown")


# --- ОБРАБОТЧИКИ ОБЫЧНЫХ КОМАНД И КНОПОК ---

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    if user_id in banned_users:
        bot.send_message(user_id, "❌ Вы заблокированы администрацией бота за нарушение правил.")
        return
        
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
    if user_id in banned_users: return
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
    if user_id in banned_users:
        bot.send_message(user_id, "❌ Вы заблокированы и не можете искать собеседников.")
        return
        
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

# Кнопка "🚨 Пожаловаться"
@bot.message_handler(func=lambda message: message.text == "🚨 Пожаловаться")
def report_user(message):
    user_id = message.chat.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        
        # Оповещаем создателя бота и всех админов из списка
        report_text = f"🚨 *ПОСТУПИЛА ЖАЛОБА!*\n\nПользователь `{user_id}` пожаловался на своего собеседника: `{partner_id}`."
        try:
            bot.send_message(CREATOR_ID, report_text, parse_mode="Markdown")
        except: pass
        for adm in temporary_admins.keys():
            try: bot.send_message(adm, report_text, parse_mode="Markdown")
            except: pass
            
        bot.send_message(user_id, "✅ Ваша жалоба отправлена администрации. Спасибо за бдительность!")
    else:
        bot.send_message(user_id, "Вы не находитесь в диалоге.")

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


# --- ОБРАБОТКА ТЕКСТА И ФАЙЛОВ / ЧАТ ---

@bot.message_handler(content_types=['text', 'photo', 'sticker', 'voice', 'video', 'audio', 'animation', 'document'])
def echo_all(message):
    user_id = message.chat.id
    if user_id in banned_users: return

    # Обработка шагов админки
    if user_id in states:
        user_state = states[user_id]
        step = user_state['step']
        
        if step == "waiting_for_broadcast_text" and message.text:
            del states[user_id]
            text_to_send = message.text
            success_count = 0
            for uid in list(user_stats.keys()):
                try:
                    bot.send_message(uid, text_to_send)
                    success_count += 1
                except: pass
            bot.send_message(user_id, f"📢 Рассылка завершена! Отправлено {success_count} пользователям.", reply_markup=get_admin_menu(user_id))
            return

        elif step == "waiting_for_ban_id" and message.text:
            del states[user_id]
            try:
                target_id = int(message.text)
                if target_id == CREATOR_ID:
                    bot.send_message(user_id, "❌ Нельзя забанить создателя бота!")
                    return
                if target_id not in banned_users:
                    banned_users.append(target_id)
                    # Если нарушитель в чате — отключаем его
                    if target_id in active_chats:
                        p_id = active_chats[target_id]
                        del active_chats[target_id]
                        if p_id in active_chats: del active_chats[p_id]
                        try: bot.send_message(p_id, "🛑 Ваш собеседник был заблокирован администратором.", reply_markup=get_main_menu())
                        except: pass
                    save_stats()
                    bot.send_message(user_id, f"🔨 Пользователь `{target_id}` успешно забанен.", parse_mode="Markdown", reply_markup=get_admin_menu(user_id))
                    try: bot.send_message(target_id, "❌ Вы были заблокированы администрацией бота за нарушение правил.")
                    except: pass
                else:
                    bot.send_message(user_id, "Этот юзер уже в бане.")
            except ValueError:
                bot.send_message(user_id, "❌ Неверный формат ID.")
            return

        elif step == "waiting_for_unban_id" and message.text:
            del states[user_id]
            try:
                target_id = int(message.text)
                if target_id in banned_users:
                    banned_users.remove(target_id)
                    save_stats()
                    bot.send_message(user_id, f"🔓 Пользователь `{target_id}` успешно разбанен.", parse_mode="Markdown", reply_markup=get_admin_menu(user_id))
                    try: bot.send_message(target_id, "🎉 Вы были разблокированы администрацией и снова можете общаться!")
                    except: pass
                else:
                    bot.send_message(user_id, "Данный ID не найден в черном списке.")
            except ValueError:
                bot.send_message(user_id, "❌ Неверный формат ID.")
            return

        elif step == "waiting_for_admin_id" and message.text:
            try:
                target_id = int(message.text)
                states[user_id] = {'step': "waiting_for_admin_time", 'target_id': target_id}
                bot.send_message(user_id, f"⏱ На сколько ЧАСОВ вы хотите выдать админку пользователю `{target_id}`?:", parse_mode="Markdown")
            except ValueError:
                bot.send_message(user_id, "❌ Введите число.")
            return

        elif step == "waiting_for_admin_time" and message.text:
            try:
                hours = int(message.text)
                target_id = states[user_id]['target_id']
                del states[user_id]
                
                expire_timestamp = time.time() + (hours * 3600)
                temporary_admins[target_id] = expire_timestamp
                save_stats()
                
                bot.send_message(user_id, f"✅ Пользователь `{target_id}` стал админом на {hours} ч.", parse_mode="Markdown", reply_markup=get_admin_menu(user_id))
                try: bot.send_message(target_id, f"👑 Вам выдали админ-права на {hours} часов! Доступ: /secretpanel")
                except: pass
            except ValueError:
                bot.send_message(user_id, "❌ Введите целое число.")
            return

        elif step == "waiting_for_remove_id" and message.text:
            try:
                target_id = int(message.text)
                del states[user_id]
                if target_id in temporary_admins:
                    del temporary_admins[target_id]
                    save_stats()
                    bot.send_message(user_id, f"❌ Пользователь `{target_id}` разжалован.", parse_mode="Markdown", reply_markup=get_admin_menu(user_id))
                else:
                    bot.send_message(user_id, "ID не найден в списке.", reply_markup=get_admin_menu(user_id))
            except ValueError:
                bot.send_message(user_id, "❌ Неверный формат ID.")
            return

    # Пересылка внутри чата БЕЗ СЛИВА СООБЩЕНИЙ АДМИНУ
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        try:
            if message.text: bot.send_message(partner_id, message.text)
            elif message.photo: bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
            elif message.sticker: bot.send_sticker(partner_id, message.sticker.file_id)
            elif message.voice: bot.send_voice(partner_id, message.voice.file_id)
            elif message.video: bot.send_video(partner_id, message.video.file_id, caption=message.caption)
            elif message.animation: bot.send_animation(partner_id, message.animation.file_id)
            elif message.audio: bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)
            elif message.document: bot.send_document(partner_id, message.document.file_id, caption=message.caption)
        except Exception as e:
            bot.send_message(user_id, "⚠️ Не удалось доставить сообщение. Возможно, собеседник покинул бота.")
    else:
        if message.text not in ["🔍 Искать собеседника", "📊 Мой профиль", "❌ Отменить поиск", "🛑 Завершить диалог", "🚨 Пожаловаться", "👍 Понравился", "👎 Скучный", "🔄 Главное меню"]:
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
