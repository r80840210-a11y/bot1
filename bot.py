import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Укажи токен своего бота
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"
# Ваш Telegram ID (первоначальный суперадмин)
SUPERADMIN_ID = 123456789  # Замени на свой real ID!

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    # Таблица админов
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    # Таблица треков
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, file_id TEXT)''')
    
    # Добавляем суперадмина по умолчанию
    cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (SUPERADMIN_ID,))
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- FSM (СОСТОЯНИЯ) ---
class AdminStates(StatesGroup):
    add_admin = State()
    delete_admin = State()
    track_title = State()
    track_file = State()
    broadcast_msg = State()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard(user_id: int):
    kb = [
        [InlineKeyboardButton(text="🎵 Треки", callback_data="list_tracks")]
    ]
    if is_admin(user_id):
        kb.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Запостить трек", callback_data="add_track")],
        [InlineKeyboardButton(text="👑 Добавить админа", callback_data="add_admin_start")],
        [InlineKeyboardButton(text="❌ Удалить админа", callback_data="del_admin_start")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Регистрируем пользователя для рассылки
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    conn.commit()
    conn.close()

    welcome_text = (
        "🎧 **Добро пожаловать в музыкальный бот!**\n\n"
        "Здесь вы можете послушать эксклюзивные треки.\n\n"
        "👤 **Создатель:** @beertimeold\n"
        "📢 **Наш канал:** https://t.me/beertimeoldben\n\n"
        "Выберите действие в меню ниже:"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(message.from_user.id))

@dp.callback_query(F.data == "main_menu")
async def back_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Главное меню:", reply_markup=get_main_keyboard(call.from_user.id))

# --- ПРОСЛУШИВАНИЕ ТРЕКОВ ---
@dp.callback_query(F.data == "list_tracks")
async def show_tracks(call: types.CallbackQuery):
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title FROM tracks')
    tracks = cursor.fetchall()
    conn.close()

    if not tracks:
        await call.answer("❌ Треков пока нет!", show_alert=True)
        return

    kb = []
    for track_id, title in tracks:
        kb.append([InlineKeyboardButton(text=f"🎶 {title}", callback_data=f"play_{track_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])

    await call.message.edit_text("🎼 **Выберите трек для прослушивания:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("play_"))
async def play_track(call: types.CallbackQuery):
    track_id = int(call.data.split("_")[1])
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title, file_id FROM tracks WHERE id = ?', (track_id,))
    track = cursor.fetchone()
    conn.close()

    if track:
        title, file_id = track
        caption = f"🎵 **{title}**\n\n👤 Автор: @beertimeold\n📢 Канал: https://t.me/beertimeoldben"
        await call.message.answer_audio(audio=file_id, caption=caption, parse_mode="Markdown")
        await call.answer()
    else:
        await call.answer("Трек не найден.", show_alert=True)

# --- АДМИН ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("У вас нет прав!", show_alert=True)
    
    await call.message.edit_text("⚙️ **Административная панель:**", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# Добавление трека
@dp.callback_query(F.data == "add_track")
async def add_track_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminStates.track_title)
    await call.message.answer("Введите название для нового трека:")
    await call.answer()

@dp.message(AdminStates.track_title)
async def process_track_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AdminStates.track_file)
    await message.answer("Отправьте аудиофайл (трек):")

@dp.message(AdminStates.track_file, F.audio)
async def process_track_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    file_id = message.audio.file_id

    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tracks (title, file_id) VALUES (?, ?)', (title, file_id))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Трек **«{title}»** успешно опубликован!", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# Добавление админа
@dp.callback_query(F.data == "add_admin_start")
async def add_admin_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminStates.add_admin)
    await call.message.answer("Пришлите **ID пользователя**, которого хотите сделать админом:")
    await call.answer()

@dp.message(AdminStates.add_admin)
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID должен состоять только из цифр. Попробуйте еще раз:")
    
    new_admin_id = int(message.text)
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (new_admin_id,))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Пользователь `{new_admin_id}` назначен админом!", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# Удаление админа
@dp.callback_query(F.data == "del_admin_start")
async def del_admin_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminStates.delete_admin)
    await call.message.answer("Пришлите **ID пользователя**, которого нужно удалить из админов:")
    await call.answer()

@dp.message(AdminStates.delete_admin)
async def process_del_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID должен состоять только из цифр. Попробуйте еще раз:")
    
    admin_id = int(message.text)
    if admin_id == SUPERADMIN_ID:
        await state.clear()
        return await message.answer("❌ Нельзя удалить главного админа!", reply_markup=get_admin_keyboard())

    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Пользователь `{admin_id}` удален из админов!", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# Рассылка
@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminStates.broadcast_msg)
    await call.message.answer("Напишите текст сообщения для рассылки всем пользователям:")
    await call.answer()

@dp.message(AdminStates.broadcast_msg)
async def process_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()

    count = 0
    await message.answer("🚀 Рассылка начата...")
    for user in users:
        try:
            await bot.send_message(chat_id=user[0], text=message.text)
            count += 1
            await asyncio.sleep(0.05)  # Защита от лимитов Telegram
        except Exception:
            pass  # Пользователь заблокировал бота

    await state.clear()
    await message.answer(f"✅ Рассылка завершена! Получили сообщение: {count} пользователей.", reply_markup=get_admin_keyboard())

# --- ЗАПУСК ---
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
