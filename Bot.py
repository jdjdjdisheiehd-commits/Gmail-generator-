# bot.py (РАБОЧАЯ ВЕРСИЯ ДЛЯ RENDER)
import asyncio
import re
import time
import random
import string
import requests
import os
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# === КОНФИГ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден!")
    sys.exit(1)

MAIL_TM_API = "https://api.mail.tm"
user_sessions = {}

# === РАБОТА С MAIL.TM ===
def create_mail_tm_account():
    try:
        domains_resp = requests.get(f"{MAIL_TM_API}/domains", timeout=10)
        domains = domains_resp.json()
        domain = domains['hydra:member'][0]['domain']
        
        local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{local}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        resp = requests.post(f"{MAIL_TM_API}/accounts", json={"address": email, "password": password}, timeout=10)
        if resp.status_code != 201:
            raise Exception(f"Ошибка: {resp.text}")
        
        return {"email": email, "password": password, "id": resp.json()['id']}
    except Exception as e:
        print(f"❌ Ошибка mail.tm: {e}")
        raise

def get_latest_code(email, password):
    try:
        resp = requests.post(f"{MAIL_TM_API}/token", json={"address": email, "password": password}, timeout=10)
        token = resp.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        
        resp = requests.get(f"{MAIL_TM_API}/messages", headers=headers, timeout=10)
        messages = resp.json().get('hydra:member', [])
        if not messages:
            return None
        
        latest = messages[-1]
        resp = requests.get(f"{MAIL_TM_API}/messages/{latest['id']}", headers=headers, timeout=10)
        content = resp.json().get('html', [{}])[0].get('body', '')
        
        match = re.search(r'\b(\d{6})\b', content)
        return match.group(1) if match else None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

# === БОТ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Бот для временной почты mail.tm\n\n"
        "/gen — создать почту\n"
        "/code — получить код\n"
        "/info — текущая почта\n"
        "/clear — удалить сессию"
    )

@dp.message(Command("gen"))
async def gen(message: Message):
    user_id = message.from_user.id
    try:
        mail = create_mail_tm_account()
        user_sessions[user_id] = mail
        await message.answer(
            f"✅ Почта создана!\n\n"
            f"📧 {mail['email']}\n"
            f"🔑 Пароль: {mail['password']}\n\n"
            f"💡 Используйте /code для получения кода"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("code"))
async def code(message: Message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.answer("❌ Сначала создайте почту: /gen")
        return
    
    mail = user_sessions[user_id]
    await message.answer(f"🔍 Ищу код для {mail['email']}...")
    
    code = get_latest_code(mail['email'], mail['password'])
    if code:
        await message.answer(f"✅ Код: {code}")
    else:
        await message.answer(f"❌ Код не найден. Проверьте почту через 10 секунд.")

@dp.message(Command("info"))
async def info(message: Message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.answer("❌ Нет активной почты.")
        return
    
    mail = user_sessions[user_id]
    await message.answer(f"📧 {mail['email']}")

@dp.message(Command("clear"))
async def clear(message: Message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
        await message.answer("🗑️ Сессия удалена.")

# === ЗАПУСК ===
async def main():
    print("🚀 Бот запущен на Render!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
