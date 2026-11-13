import logging
from typing import Dict, Any, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command

from config import settings
from database.db_manager import get_active_tasks, get_recent_cars
from checkers.vin_decoder import VinDecoder

logger = logging.getLogger("AutoHunterBot")

bot: Optional[Bot] = None
dp = Dispatcher()


def get_bot() -> Optional[Bot]:
    global bot
    if not bot and settings.TG_BOT_TOKEN:
        bot = Bot(token=settings.TG_BOT_TOKEN)
    return bot


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    text = (
        f"🎯 <b>AutoHunter Bot активирован!</b>\n\n"
        f"Твой Chat ID: <code>{user_id}</code>\n"
        f"Статус: <i>Слушает эфир Drom, Auto.ru, Avito</i>\n\n"
        f"Команды:\n"
        f"/filters — Активные фильтры поиска\n"
        f"/last — Последние 5 найденных авто\n"
        f"/status — Состояние мониторинга"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    tasks = await get_active_tasks()
    text = (
        f"⚡️ <b>Статус системы AutoHunter:</b>\n"
        f"• Активных задач: <b>{len(tasks)}</b>\n"
        f"• Проверка каждые: <b>{settings.CHECK_INTERVAL_SECONDS} сек.</b>\n"
        f"• Доступные площадки: <b>Drom.ru, Auto.ru, Avito</b>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("filters"))
async def cmd_filters(message: types.Message):
    tasks = await get_active_tasks()
    if not tasks:
        await message.answer("⚠️ Нет активных фильтров поиска. Настрой их в веб-панели или конфиге.")
        return

    text = "📋 <b>Активные фильтры мониторинга:</b>\n\n"
    for i, t in enumerate(tasks, 1):
        price_str = f"{t.price_min or 0:,} - {t.price_max or '∞':,} ₽".replace(",", " ")
        years = f"{t.year_min or '—'} - {t.year_max or '—'}"
        text += (
            f"<b>{i}. {t.name}</b> [{t.platform.upper()}]\n"
            f"🚗 {t.brand or 'Любая'} {t.model or ''}\n"
            f"💵 {price_str} | 📅 {years} г.\n"
            f"👤 {'Только частники' if t.exclude_dealers else 'Все'}\n\n"
        )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("last"))
async def cmd_last(message: types.Message):
    cars = await get_recent_cars(limit=5)
    if not cars:
        await message.answer("Пока нет найденных автомобилей.")
        return

    for car in cars:
        await send_car_notification(car.to_dict(), task_name="История", is_update=False)


async def send_car_notification(car: Dict[str, Any], task_name: str, is_update: bool = False, old_price: Optional[int] = None):
    b = get_bot()
    chat_id = settings.TG_CHAT_ID
    if not b or not chat_id:
        return

    price_str = f"{car.get('price', 0):,} ₽".replace(",", " ")
    
    if is_update and old_price:
        diff = car.get("price", 0) - old_price
        sign = "+" if diff > 0 else ""
        diff_str = f"({sign}{diff:,} ₽)".replace(",", " ")
        header = f"📉 <b>ИЗМЕНЕНИЕ ЦЕНЫ!</b>\n"
        price_line = f"💰 Цена: <s>{old_price:,} ₽</s> ➡️ <b>{price_str}</b> <i>{diff_str}</i>\n".replace(",", " ")
    else:
        header = f"🔥 <b>НАЙДЕН АВТОМОБИЛЬ!</b>\n"
        price_line = f"💰 Цена: <b>{price_str}</b>\n"

    seller_type = "🏢 Салон / Дилер" if car.get("is_dealer") else "👤 Собственник"
    mileage_str = f"{car.get('mileage', 0):,} км".replace(",", " ") if car.get("mileage") else "Не указан"
    owners_str = f"{car.get('owners_count')} вл." if car.get("owners_count") else "Н/Д"

    caption = (
        f"{header}"
        f"🚘 <b>{car.get('title', 'Автомобиль')}</b>\n"
        f"{price_line}"
        f"📍 Город: <b>{car.get('city') or 'Не указан'}</b>\n"
        f"⏱ Пробег: <b>{mileage_str}</b> | 📅 Год: <b>{car.get('year') or 'Н/Д'}</b>\n"
        f"👥 Владельцы: <b>{owners_str}</b>\n"
        f"📌 Продавец: <b>{seller_type}</b>\n"
        f"🏷 Площадка: <b>{car.get('platform', '').upper()}</b>\n"
        f"🎯 Фильтр: <i>{task_name}</i>\n"
    )

    if car.get("nomerogram_url"):
        caption += f"\n📸 <b>Номерограм:</b> найдено {car.get('nomerogram_photos_count', 0)} архивных фото!"

    if car.get("vin"):
        caption += f"\n🔢 VIN: <code>{car.get('vin')}</code>"

    # Buttons
    buttons = [
        [InlineKeyboardButton(text="↗️ Открыть объявление", url=car["url"])]
    ]
    extra_row = []
    if car.get("nomerogram_url"):
        extra_row.append(InlineKeyboardButton(text="📸 Номерограм", url=car["nomerogram_url"]))
    
    links = VinDecoder.get_free_check_links(vin=car.get("vin"), plate=car.get("license_plate"))
    if "ГИБДД" in links:
        extra_row.append(InlineKeyboardButton(text="🛡 ГИБДД", url=links["ГИБДД"]))

    if extra_row:
        buttons.append(extra_row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        photo = car.get("photo_url")
        if photo and photo.startswith("http"):
            await b.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        else:
            await b.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=False
            )
    except Exception as e:
        logger.error(f"Failed to send telegram notification: {e}")
