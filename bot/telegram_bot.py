import logging
import re
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.db_manager import (
    get_active_tasks, get_recent_cars, create_task, delete_task
)
from checkers.vin_decoder import VinDecoder

logger = logging.getLogger("AutoHunterBot")

bot: Optional[Bot] = None
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def get_bot() -> Optional[Bot]:
    global bot
    if not bot and settings.TG_BOT_TOKEN:
        bot = Bot(token=settings.TG_BOT_TOKEN)
    return bot


# FSM States for Full Setup Wizard
class FilterSetupState(StatesGroup):
    waiting_brand = State()
    waiting_model = State()
    waiting_years = State()
    waiting_price = State()
    waiting_mileage = State()
    waiting_owners = State()
    waiting_dealers = State()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    tasks = await get_active_tasks()
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Настроить фильтр поиска")],
            [KeyboardButton(text="📋 Мои фильтры"), KeyboardButton(text="🗑 Удалить все фильтры")]
        ],
        resize_keyboard=True
    )

    if not tasks:
        text = (
            "👋 <b>Добро пожаловать в AutoHunter!</b>\n\n"
            "⚠️ <b>Сейчас поиск остановлен</b>, так как нет активных фильтров.\n"
            "Давай сначала <b>полностью настроим критерии</b> нужной машины, и только после этого начнется мониторинг эфира Drom, Auto.ru и Avito.\n\n"
            "Нажми кнопку ниже или отправь <b>/new</b> для настройки."
        )
    else:
        text = (
            f"🎯 <b>AutoHunter в работе!</b>\n"
            f"Активных фильтров: <b>{len(tasks)}</b>\n\n"
            f"Используй кнопки ниже для управления."
        )

    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@dp.message(F.text == "➕ Настроить фильтр поиска")
@dp.message(Command("new"))
async def start_filter_wizard(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(FilterSetupState.waiting_brand)
    
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "🛠 <b>НАСТРОЙКА ФИЛЬТРА [Шаг 1 из 7]</b>\n\n"
        "Какую <b>марку</b> авто ищем?\n"
        "<i>Например: Toyota, BMW, Kia, Lada (или напиши '-', если любая):</i>",
        reply_markup=cancel_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_brand)
async def process_brand(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    brand = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(brand=brand)
    await state.set_state(FilterSetupState.waiting_model)

    await message.answer(
        f"✅ Марка: <b>{brand or 'Любая'}</b>\n\n"
        "🛠 <b>[Шаг 2 из 7]</b>\n"
        "Какая <b>модель</b>?\n"
        "<i>Например: Camry, X5, Rio, Vesta (или '-', если любая):</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_model)
async def process_model(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    model = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(model=model)
    await state.set_state(FilterSetupState.waiting_years)

    await message.answer(
        f"✅ Модель: <b>{model or 'Любая'}</b>\n\n"
        "🛠 <b>[Шаг 3 из 7]</b>\n"
        "Укажи <b>диапазон годов выпуска</b>:\n"
        "<i>Например: <code>2013-2018</code> или <code>от 2015</code> или '-', если любой:</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_years)
async def process_years(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    text = message.text.strip()
    year_min, year_max = None, None
    if text != "-":
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
        if len(years) == 1:
            if "до" in text.lower():
                year_max = int(years[0])
            else:
                year_min = int(years[0])
        elif len(years) >= 2:
            year_min = min(int(years[0]), int(years[1]))
            year_max = max(int(years[0]), int(years[1]))

    await state.update_data(year_min=year_min, year_max=year_max)
    await state.set_state(FilterSetupState.waiting_price)

    await message.answer(
        f"✅ Года: <b>{year_min or '—'} - {year_max or '—'}</b>\n\n"
        "🛠 <b>[Шаг 4 из 7]</b>\n"
        "Какой <b>бюджет (цена)</b>?\n"
        "<i>Например: <code>1000000-1800000</code> или <code>до 2000000</code> (или '-'):</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_price)
async def process_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    text = message.text.replace(" ", "").replace("к", "000").replace("кк", "000000").replace("м", "000000")
    price_min, price_max = None, None
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if len(numbers) == 1:
        if "от" in message.text.lower():
            price_min = numbers[0]
        else:
            price_max = numbers[0]
    elif len(numbers) >= 2:
        price_min = min(numbers[0], numbers[1])
        price_max = max(numbers[0], numbers[1])

    await state.update_data(price_min=price_min, price_max=price_max)
    await state.set_state(FilterSetupState.waiting_mileage)

    await message.answer(
        f"✅ Бюджет: <b>{price_min or 0:,} - {price_max or '∞':,} ₽</b>\n\n"
        "🛠 <b>[Шаг 5 из 7]</b>\n"
        "<b>Максимальный пробег</b> (в км)?\n"
        "<i>Например: <code>150000</code> или '-', если любой:</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    digits = re.sub(r"[^\d]", "", message.text)
    mileage_max = int(digits) if digits else None

    await state.update_data(mileage_max=mileage_max)
    await state.set_state(FilterSetupState.waiting_owners)

    await message.answer(
        f"✅ Пробег: <b>до {mileage_max:,} км</b>\n\n"
        "🛠 <b>[Шаг 6 из 7]</b>\n"
        "<b>Максимальное число владельцев</b> по ПТС?\n"
        "<i>Например: <code>1</code>, <code>2</code> или '-', если любое:</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_owners)
async def process_owners(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    digits = re.sub(r"[^\d]", "", message.text)
    owners_max = int(digits) if digits else None

    await state.update_data(owners_max=owners_max)
    await state.set_state(FilterSetupState.waiting_dealers)

    dealers_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Только собственники (без салонов)")],
            [KeyboardButton(text="🏢 Все (включая салоны и дилеров)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Владельцев: <b>до {owners_max or 'любое'}</b>\n\n"
        "🛠 <b>[Шаг 7 из 7]</b>\n"
        "Исключать автосалоны, дилеров и площадки?\n"
        "<i>Выбери вариант кнопкой ниже:</i>",
        reply_markup=dealers_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(FilterSetupState.waiting_dealers)
async def process_dealers(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    exclude_dealers = "Только собственники" in message.text
    data = await state.get_data()
    await state.clear()

    brand = data.get("brand", "")
    model = data.get("model", "")
    name = f"{brand} {model}".strip() or "Поиск авто"

    # Create task in DB
    task_payload = {
        "name": name,
        "platform": "all",
        "brand": brand,
        "model": model,
        "year_min": data.get("year_min"),
        "year_max": data.get("year_max"),
        "price_min": data.get("price_min"),
        "price_max": data.get("price_max"),
        "mileage_max": data.get("mileage_max"),
        "owners_max": data.get("owners_max"),
        "exclude_dealers": exclude_dealers,
        "exclude_damaged": True,
        "stop_words": "запрет, арест, без доков, залог"
    }

    new_task = await create_task(task_payload)

    main_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Настроить фильтр поиска")],
            [KeyboardButton(text="📋 Мои фильтры"), KeyboardButton(text="🗑 Удалить все фильтры")]
        ],
        resize_keyboard=True
    )

    summary = (
        "🚀 <b>ФИЛЬТР УСПЕШНО СОЗДАН И АКТИВИРОВАН!</b>\n\n"
        f"🚘 <b>Автомобиль:</b> {brand or 'Любая'} {model or ''}\n"
        f"📅 <b>Года:</b> {new_task.year_min or '—'} - {new_task.year_max or '—'}\n"
        f"💰 <b>Бюджет:</b> {new_task.price_min or 0:,} - {new_task.price_max or '∞':,} ₽\n"
        f"⏱ <b>Пробег:</b> {f'до {new_task.mileage_max:,} км' if new_task.mileage_max else 'любой'}\n"
        f"👥 <b>Владельцев:</b> {f'до {new_task.owners_max}' if new_task.owners_max else 'любое'}\n"
        f"👤 <b>Продавцы:</b> {'Только частники' if new_task.exclude_dealers else 'Все'}\n"
        f"🛡 <b>Исключение битых/арестов:</b> Включено\n\n"
        "⚡️ <b>СКАНИРОВАНИЕ ЗАПУЩЕНО!</b> Как только на Drom, Auto.ru или Avito появится подходящая машина — карточка сразу прилетит сюда."
    )

    await message.answer(summary, reply_markup=main_kb, parse_mode=ParseMode.HTML)


@dp.message(F.text == "📋 Мои фильтры")
@dp.message(Command("filters"))
async def show_filters(message: types.Message):
    tasks = await get_active_tasks()
    if not tasks:
        await message.answer("⚠️ Нет активных фильтров. Нажми <b>➕ Настроить фильтр поиска</b>, чтобы добавить.")
        return

    text = "📋 <b>Активные фильтры поиска:</b>\n\n"
    for i, t in enumerate(tasks, 1):
        price_str = f"{t.price_min or 0:,} - {t.price_max or '∞':,} ₽".replace(",", " ")
        years = f"{t.year_min or '—'} - {t.year_max or '—'}"
        text += (
            f"<b>{i}. {t.name}</b>\n"
            f"🚗 {t.brand or 'Любая'} {t.model or ''}\n"
            f"💵 {price_str} | 📅 {years} г.\n"
            f"⏱ Пробег: {f'до {t.mileage_max:,} км' if t.mileage_max else 'любой'}\n"
            f"👤 {'Только собственники' if t.exclude_dealers else 'Все'}\n\n"
        )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(F.text == "🗑 Удалить все фильтры")
async def clear_all_filters(message: types.Message):
    tasks = await get_active_tasks()
    for t in tasks:
        await delete_task(t.id)
    await message.answer("🗑 Все фильтры удалены. Поиск остановлен.")


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
