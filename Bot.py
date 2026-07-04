# bot.py (FULLY WORKING VERSION FOR RENDER)
import asyncio
import re
import time
import random
import string
import requests
import os
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import Message
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

# === КОНФИГ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден!")
    sys.exit(1)

MAIL_TM_API = "https://api.mail.tm"

# Хранилище сессий пользователей (в памяти)
user_sessions = {}

# === РАБОТА С MAIL.TM ===
def create_mail_tm_account():
    """Создаёт временный почтовый ящик через mail.tm"""
    try:
        domains_resp = requests.get(f"{MAIL_TM_API}/domains", timeout=10)
        domains = domains_resp.json()
        domain = domains['hydra:member'][0]['domain']
        
        local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{local}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        payload = {"address": email, "password": password}
        resp = requests.post(f"{MAIL_TM_API}/accounts", json=payload, timeout=10)
        if resp.status_code != 201:
            raise Exception(f"Ошибка создания почты: {resp.text}")
        
        account_data = resp.json()
        return {
            "email": email,
            "password": password,
            "id": account_data['id']
        }
    except Exception as e:
        print(f"❌ Ошибка mail.tm: {e}")
        raise

def get_mail_tm_token(email, password):
    """Получает JWT токен для доступа к почтовому ящику"""
    resp = requests.post(f"{MAIL_TM_API}/token", json={
        "address": email,
        "password": password
    }, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"Ошибка получения токена: {resp.text}")
    return resp.json()['token']

def get_messages(token):
    """Получает список сообщений"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{MAIL_TM_API}/messages", headers=headers, timeout=10)
    if resp.status_code != 200:
        return []
    return resp.json().get('hydra:member', [])

def get_message_content(token, message_id):
    """Получает содержимое сообщения"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{MAIL_TM_API}/messages/{message_id}", headers=headers, timeout=10)
    if resp.status_code != 200:
        return ""
    data = resp.json()
    parts=[]
    for key in ("text","intro","subject"):
        if data.get(key):
            parts.append(str(data[key]))
    html=data.get("html")
    if html:
        if isinstance(html,list):
            parts.extend(map(str,html))
        else:
            parts.append(str(html))
    return "\n".join(parts)

def extract_code_from_html(html_content):
    """Извлекает 6-значный код из письма"""
    if not html_content:
        return None
    
    match = re.search(r'\b(\d{4,8})\b', html_content)
    if match:
        return match.group(1)
    
    match = re.search(r'(?:code|код|verification|confirm)\s*[:;]\s*(\d{6})', html_content, re.IGNORECASE)
    return match.group(1) if match else None

def get_latest_code(email, password):
    """Получает последний код из почтового ящика"""
    try:
        token = get_mail_tm_token(email, password)
        messages = get_messages(token)
        if not messages:
            return None
        
        latest = messages[-1]
        content = get_message_content(token, latest['id'])
        code = extract_code_from_html(content)
        return code
    except Exception as e:
        print(f"Ошибка при получении кода: {e}")
        return None

# === ОБРАБОТЧИКИ КОМАНД ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для работы с временной почтой mail.tm\n\n"
        "📧 /gen — создать новую временную почту\n"
        "🔑 /code — получить код подтверждения из последнего письма\n"
        "ℹ️ /info — показать текущую почту\n"
        "🗑️ /clear — удалить текущую сессию"
    )

@dp.message_handler(commands=['gen'])
async def cmd_gen(message: types.Message):
    user_id = message.from_user.id
    
    try:
        mail_data = create_mail_tm_account()
        
        user_sessions[user_id] = {
            "email": mail_data["email"],
            "password": mail_data["password"],
            "id": mail_data["id"],
            "created_at": time.time()
        }
        
        await message.answer(
            f"✅ Временная почта создана!\n\n"
            f"📧 {mail_data['email']}\n"
            f"🔑 Пароль: {mail_data['password']}\n\n"
            f"💡 Используйте /code для получения кода из письма\n"
            f"⏳ Письмо обычно приходит в течение 10-30 секунд"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании почты: {str(e)}")

@dp.message_handler(commands=['code'])
async def cmd_code(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await message.answer(
            "❌ У вас нет активной почты.\n"
            "Используйте /gen для создания новой."
        )
        return
    
    session = user_sessions[user_id]
    email = session["email"]
    password = session["password"]
    
    try:
        await message.answer(f"🔍 Ищу код для {email}...")
        
        code = get_latest_code(email, password)
        
        if code:
            await message.answer(
                f"✅ Код подтверждения найден!\n\n"
                f"🔑 {code}\n\n"
                f"📧 Почта: {email}"
            )
        else:
            await message.answer(
                f"❌ Код не найден.\n"
                f"📧 Почта: {email}\n\n"
                f"💡 Возможные причины:\n"
                f"• Письмо ещё не пришло (подождите 10-30 секунд)\n"
                f"• Письмо пришло в спам\n"
                f"• Нет новых писем\n\n"
                f"Попробуйте ещё раз через 15 секунд."
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении кода: {str(e)}")

@dp.message_handler(commands=['info'])
async def cmd_info(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await message.answer("❌ У вас нет активной почты. Используйте /gen.")
        return
    
    session = user_sessions[user_id]
    await message.answer(
        f"📧 Текущая почта: {session['email']}\n"
        f"🆔 ID: {session['id']}\n"
        f"⏱️ Создана: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['created_at']))}"
    )

@dp.message_handler(commands=['clear'])
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        del user_sessions[user_id]
        await message.answer("🗑️ Сессия очищена. Почта удалена из памяти.")
    else:
        await message.answer("❌ У вас нет активной сессии.")

# === ЗАПУСК БОТА ===
if __name__ == "__main__":
    print("🚀 Telegram-бот запущен на Render!")
    print("=" * 50)
    executor.start_polling(dp, skip_updates=True)
