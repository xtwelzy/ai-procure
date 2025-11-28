import os
import requests
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

BACKEND_URL = "http://127.0.0.1:8000"

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))

dp = Dispatcher()
router = Router()
dp.include_router(router)


# -----------------------
# /start
# -----------------------
@router.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "🤖 *AI-Procure — Telegram бот*\n\n"
        "Команды:\n"
        "/upload_tenders — загрузить CSV тендеров\n"
        "/upload_suppliers — загрузить CSV поставщиков\n"
        "/tender <id> — отчёт по тендеру\n"
        "/risks <id> — риски\n"
        "/suppliers <id> — подходящие поставщики\n"
    )
    await message.answer(text)


# -----------------------
# /tender
# -----------------------
@router.message(Command("tender"))
async def tender_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Пример: `/tender 5`")
        return

    tender_id = parts[1]
    r = requests.get(f"{BACKEND_URL}/tenders/{tender_id}/report")

    if r.status_code != 200:
        await message.answer("⚠ Тендер не найден.")
        return

    data = r.json()

    t = data["tender"]

    txt = (
        f"📄 *Отчёт по тендеру {tender_id}*\n\n"
        f"*Предмет:* {t.get('subject')}\n"
        f"*Цена:* {t.get('price_amount')} ₸\n"
        f"*Категория:* {t.get('category')}\n"
        f"*Регион:* {t.get('region')}\n"
        f"*Платформа:* {t.get('platform')}\n"
    )

    await message.answer(txt)


# -----------------------
# Риски тендера
# -----------------------
@router.message(Command("risks"))
async def risks_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Пример: `/risks 5`")
        return

    tender_id = parts[1]
    r = requests.get(f"{BACKEND_URL}/tenders/{tender_id}/report")

    if r.status_code != 200:
        await message.answer("⚠ Тендер не найден.")
        return

    flags = r.json()["risk_flags"]

    if not flags:
        await message.answer("✔ Риски не обнаружены.")
        return

    txt = f"⚠ *Риски по тендеру {tender_id}:*\n\n"
    for f in flags:
        txt += f"• ({f['code']}) {f['description']} — вес {f['weight']}\n"

    await message.answer(txt)


# -----------------------
# Поставщики
# -----------------------
@router.message(Command("suppliers"))
async def suppliers_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Пример: `/suppliers 5`")
        return

    tender_id = parts[1]
    r = requests.get(f"{BACKEND_URL}/tenders/{tender_id}/report")

    if r.status_code != 200:
        await message.answer("⚠ Тендер не найден.")
        return

    suppliers = r.json()["suppliers"]
    if not suppliers:
        await message.answer("Нет подходящих поставщиков.")
        return

    txt = f"📦 *Поставщики (тендер {tender_id}):*\n\n"
    for s in suppliers:
        txt += (
            f"• {s['name']} — match: {round(s['match_score'] * 100)}%\n"
            f"  Регион: {s['region']}\n\n"
        )

    await message.answer(txt)


# -----------------------
# upload_tenders
# -----------------------
@router.message(Command("upload_tenders"))
async def upload_tenders(message: Message):
    await message.answer("📎 Отправь CSV тендеров.")


# -----------------------
# upload_suppliers
# -----------------------
@router.message(Command("upload_suppliers"))
async def upload_suppliers(message: Message):
    await message.answer("📎 Отправь CSV поставщиков.")


# -----------------------
# handle CSV uploads
# -----------------------
@router.message(F.document)
async def handle_file(message: Message):
    filename = message.document.file_name.lower()

    file_info = await bot.get_file(message.document.file_id)
    dest = f"temp/{filename}"
    os.makedirs("temp", exist_ok=True)
    await bot.download_file(file_info.file_path, dest)

    if "tender" in filename:
        url = f"{BACKEND_URL}/tenders/ingest_csv"
    elif "supplier" in filename:
        url = f"{BACKEND_URL}/suppliers/ingest_csv"
    else:
        await message.answer("❗ Имя файла должно содержать 'tender' или 'supplier'")
        return

    files = {"file": open(dest, "rb")}
    r = requests.post(url, files=files)

    if r.status_code == 200:
        await message.answer("✅ Файл успешно обработан.")
    else:
        await message.answer("⚠ Ошибка обработки файла.")

    os.remove(dest)


# -----------------------
# run bot
# -----------------------
async def main():
    print("🚀 Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
