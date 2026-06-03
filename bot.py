import telebot
import os
import re
import time
from flask import Flask
from threading import Thread

token = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(token)
app = Flask('')

# Простой список матерных слов (дополняй своими)
BAD_WORDS = ['мат1', 'мат2', 'спамворд'] 

# База данных для варнов (предупреждений) в памяти
user_warnings = {}

@app.route('/')
def home():
    return "Супер-модератор активен!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Функция для расчета времени бана/мута
def parse_time(time_str):
    if not time_str:
        return None
    match = re.match(r'(\d+)([mhd])', time_str.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    if unit == 'm': return time.time() + amount * 60
    if unit == 'h': return time.time() + amount * 3600
    if unit == 'd': return time.time() + amount * 86400
    return None

# --- ПРИВЕТСТВИЕ И ПРАВИЛА ---
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        # Проверяем, что это не сам бот
        if new_user.id == bot.get_me().id:
            continue
            
        rules_text = (
            f"👋 **Привет, {new_user.first_name}!** Добро пожаловать в наш чат!\n\n"
            f"📜 **Пожалуйста, соблюдай наши правила:**\n"
            f"1️⃣ Никакого спама и сторонних ссылок (бот удалит автоматически).\n"
            f"2️⃣ Общайся без мата и оскорблений (за 3 предупреждения — бан).\n"
            f"3️⃣ Не пиши сообщения КАПСОМ.\n"
            f"4️⃣ Уважай других участников чата.\n\n"
            f"Приятного общения! Нарушителей порядка ловит наш бот-шериф 👮‍♂️"
        )
        bot.send_message(message.chat.id, rules_text, parse_mode="Markdown")

# --- КОМАНДЫ АДМИНИСТРАТОРА (!бан, !мут, !кик, !варн) ---

@bot.message_handler(func=lambda message: message.text and message.text.startswith(('!бан', '!мут', '!кик', '!варн')))
def admin_commands(message):
    # Проверяем, админ ли тот, кто пишет команду
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in ['administrator', 'creator']:
        return

    # Должен быть ответ на сообщение
    if not message.reply_to_message:
        bot.reply_to_message(message, "⚠️ Эту команду нужно писать в ответ на сообщение нарушителя!")
        return

    target_user = message.reply_to_message.from_user
    args = message.text.split()
    command = args[0].lower()

    # --- КОМАНДА !БАН ---
    if command == '!бан':
        until_date = parse_time(args[1]) if len(args) > 1 else None
        time_text = f"на {args[1]}" if until_date else "навсегда"
        try:
            bot.ban_chat_member(message.chat.id, target_user.id, until_date=until_date)
            bot.send_message(message.chat.id, f"🚫 {target_user.first_name} заблокирован {time_text}!")
        except Exception as e:
            bot.reply_to_message(message, f"Ошибка: {e}")

    # --- КОМАНДА !МУТ (Запрет писать сообщения) ---
    elif command == '!мут':
        duration = args[1] if len(args) > 1 else "10m" # По умолчанию 10 минут
        until_date = parse_time(duration)
        try:
            # Забираем права на отправку сообщений
            bot.restrict_chat_member(
                message.chat.id, target_user.id, until_date=until_date,
                can_send_messages=False, can_send_media_messages=False,
                can_send_polls=False, can_send_other_messages=False
            )
            bot.send_message(message.chat.id, f"🤫 {target_user.first_name} отправлен в мут на {duration}!")
        except Exception as e:
            bot.reply_to_message(message, f"Ошибка: {e}")

    # --- КОМАНДА !КИК (Выгнать из чата) ---
    elif command == '!кик':
        try:
            bot.ban_chat_member(message.chat.id, target_user.id)
            bot.unban_chat_member(message.chat.id, target_user.id) # Сразу разбаниваем, чтобы мог войти обратно
            bot.send_message(message.chat.id, f"💨 {target_user.first_name} был вышвырнут из чата!")
        except Exception as e:
            bot.reply_to_message(message, f"Ошибка: {e}")

    # --- КОМАНДА !ВАРН (Предупреждение) ---
    elif command == '!варн':
        user_id = target_user.id
        user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
        count = user_warnings[user_id]
        
        if count >= 3:
            try:
                bot.ban_chat_member(message.chat.id, user_id, until_date=time.time() + 86400) # Бан на 1 день за 3 варна
                bot.send_message(message.chat.id, f"💥 {target_user.first_name} получил 3-е предупреждение и отправляется в бан на 24 часа!")
                user_warnings[user_id] = 0 # Сбрасываем счетчик
            except Exception as e:
                bot.reply_to_message(message, f"Ошибка: {e}")
        else:
            bot.send_message(message.chat.id, f"⚠️ {target_user.first_name}, тебе выдано предупреждение ({count}/3)! Веди себя прилично.")

# --- АВТО-УДАЛЕНИЕ МАТА, ССЫЛОК И КАПСА ---
@bot.message_handler(func=lambda message: True)
def moderate_chat(message):
    # Админов не трогаем
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in ['administrator', 'creator']:
        return

    text = message.text if message.text else ""
    
    # 1. Ссылки
    if re.search(r'(https?://\S+|t\.me/\S+)', text.lower()):
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, f"⚠️ {message.from_user.first_name}, ссылки запрещены!")
            return
        except: pass

    # 2. Мат
    for word in BAD_WORDS:
        if word in text.lower():
            try:
                bot.delete_message(message.chat.id, message.message_id)
                bot.send_message(message.chat.id, f"🤬 {message.from_user.first_name}, маты запрещены!")
                return
            except: pass

    # 3. Анти-Капс (Если в тексте больше 5 букв и они ВСЕ заглавные)
    if text.isupper() and len(text) > 5:
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, f" Нажми Caps Lock, {message.from_user.first_name}! Зачем так орать?")
            return
        except: pass

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)

