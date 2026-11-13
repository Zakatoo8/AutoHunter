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


class DetailedFilterState(StatesGroup):
    waiting_brand_model = State()
    waiting_excluded = State()
    waiting_price = State()
    waiting_years = State()
    waiting_mileage = State()
    waiting_owners = State()
    waiting_pts = State()
    waiting_transmission = State()
    waiting_dealers = State()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    tasks = await get_active_tasks()
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 НАСТРОИТЬ ПОИСК АВТО (ПОЛНОСТЬЮ)")],
            [KeyboardButton(text="📋 Активные фильтры"), KeyboardButton(text="🗑 Сбросить фильтры")]
        ],
        resize_keyboard=True
    )

    if not tasks:
        text = (
            "👋 <b>Добро пожаловать в AutoHunter!</b>\n\n"
            "Сейчас мониторинг <b>остановлен</b>, так как нет активных фильтров.\n\n"
            "Нажми кнопку ниже <b>«🎯 НАСТРОИТЬ ПОИСК АВТО»</b> — мы пошагово настроим:\n"
            "• Марку / модель (и какие исключить)\n"
            "• Цену от и до\n"
            "• Количество владельцев\n"
            "• Тип ПТС (оригинал, ЭПТС, без дубликатов)\n"
            "• Коробку (автомат/механика)\n"
            "• Отсев салонов и перекупов"
        )
    else:
        text = (
            f"🎯 <b>AutoHunter в активном поиске!</b>\n"
            f"Активных фильтров: <b>{len(tasks)}</b>\n\n"
            f"Площадки: Drom.ru, Auto.ru, Avito (Playwright)\n"
            f"Как только появится подходящая тачка — она сразу прилетит сюда."
        )

    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@dp.message(F.text == "🎯 НАСТРОИТЬ ПОИСК АВТО (ПОЛНОСТЬЮ)")
@dp.message(Command("new"))
async def start_wizard(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(DetailedFilterState.waiting_brand_model)

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

    await message.answer(
        "🛠 <b>[Шаг 1 из 9] МАРКА И МОДЕЛЬ</b>\n\n"
        "Какую машину ищем?\n"
        "<i>Примеры:\n"
        "• <code>Toyota Camry</code>\n"
        "• <code>BMW 3-Series</code>\n"
        "• <code>Kia Rio</code>\n"
        "• или напиши <b>'-'</b> (прочерк), если подойдет ЛЮБАЯ марка:</i>",
        reply_markup=cancel_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_brand_model)
async def process_brand_model(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    text = message.text.strip()
    brand, model = "", ""
    if text != "-":
        parts = text.split(" ", 1)
        brand = parts[0]
        model = parts[1] if len(parts) > 1 else ""

    await state.update_data(brand=brand, model=model)
    await state.set_state(DetailedFilterState.waiting_excluded)

    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➡️ Пропустить (ничего не исключать)")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Ищем: <b>{brand or 'Любая марка'} {model or ''}</b>\n\n"
        "🛠 <b>[Шаг 2 из 9] КАКИЕ МАРКИ / МОДЕЛИ ИСКЛЮЧИТЬ?</b>\n"
        "<i>Напиши через запятую то, что тебе точно НЕ показывать.\n"
        "Например: <code>Lada, Chery, Haval, Geely, Daewoo</code>\n"
        "Или нажми «Пропустить» ниже:</i>",
        reply_markup=skip_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_excluded)
async def process_excluded(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    excluded = ""
    if "пропустить" not in message.text.lower() and message.text.strip() != "-":
        excluded = message.text.strip()

    await state.update_data(exclude_brands_models=excluded)
    await state.set_state(DetailedFilterState.waiting_price)

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Исключено: <b>{excluded or 'Нет'}</b>\n\n"
        "🛠 <b>[Шаг 3 из 9] ЦЕНА (БЮДЖЕТ)</b>\n"
        "Укажи диапазон цен от и до:\n"
        "<i>Примеры:\n"
        "• <code>1000000 - 1800000</code>\n"
        "• <code>до 2000000</code> (или <code>до 2м</code>)\n"
        "• <code>от 800к</code>\n"
        "• или <b>'-'</b> (любая цена)</i>",
        reply_markup=cancel_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_price)
async def process_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    text = message.text.lower().replace(" ", "").replace("кк", "000000").replace("м", "000000").replace("к", "000")
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
    await state.set_state(DetailedFilterState.waiting_years)

    p_str = f"{price_min or 0:,} — {price_max or '∞':,} ₽".replace(",", " ")
    await message.answer(
        f"✅ Бюджет: <b>{p_str}</b>\n\n"
        "🛠 <b>[Шаг 4 из 9] ГОДА ВЫПУСКА</b>\n"
        "<i>Примеры:\n"
        "• <code>2014 - 2019</code>\n"
        "• <code>от 2016</code>\n"
        "• <code>до 2021</code>\n"
        "• или <b>'-'</b> (любой год)</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_years)
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
    await state.set_state(DetailedFilterState.waiting_mileage)

    await message.answer(
        f"✅ Года: <b>{year_min or '—'} - {year_max or '—'}</b>\n\n"
        "🛠 <b>[Шаг 5 из 9] МАКСИМАЛЬНЫЙ ПРОБЕГ</b>\n"
        "<i>Например: <code>150000</code> (или <code>150к</code>) или <b>'-'</b> (любой пробег):</i>",
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    text = message.text.lower().replace("к", "000").replace(" ", "")
    digits = re.sub(r"[^\d]", "", text)
    mileage_max = int(digits) if digits else None

    await state.update_data(mileage_max=mileage_max)
    await state.set_state(DetailedFilterState.waiting_owners)

    owners_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1️⃣ Только 1 владелец"), KeyboardButton(text="2️⃣ До 2 владельцев")],
            [KeyboardButton(text="3️⃣ До 3 владельцев"), KeyboardButton(text="♾ Любое количество")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Пробег: <b>{f'до {mileage_max:,} км' if mileage_max else 'любой'}</b>\n\n"
        "🛠 <b>[Шаг 6 из 9] КОЛИЧЕСТВО ВЛАДЕЛЬЦЕВ ПО ПТС</b>\n"
        "<i>Выбери кнопкой ниже:</i>",
        reply_markup=owners_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_owners)
async def process_owners(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    owners_max = None
    if "1 владелец" in message.text or message.text.strip() == "1":
        owners_max = 1
    elif "2 владелец" in message.text or message.text.strip() == "2":
        owners_max = 2
    elif "3 владелец" in message.text or message.text.strip() == "3":
        owners_max = 3

    await state.update_data(owners_max=owners_max)
    await state.set_state(DetailedFilterState.waiting_pts)

    pts_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Только оригинал ПТС")],
            [KeyboardButton(text="🚫 Без дубликатов (Оригинал или ЭПТС)")],
            [KeyboardButton(text="📑 Любой ПТС (включая дубликаты)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Владельцев: <b>{f'до {owners_max}' if owners_max else 'любое'}</b>\n\n"
        "🛠 <b>[Шаг 7 из 9] ТИП ПТС</b>\n"
        "<i>Выбери вариант ПТС кнопкой:</i>",
        reply_markup=pts_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_pts)
async def process_pts(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    pts_type = "any"
    if "Только оригинал" in message.text:
        pts_type = "original"
    elif "Без дубликатов" in message.text:
        pts_type = "no_duplicate"

    await state.update_data(pts_type=pts_type)
    await state.set_state(DetailedFilterState.waiting_transmission)

    trans_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🕹 Только автомат (АКПП, Робот, Вариатор)")],
            [KeyboardButton(text="🕹 Только механика (МКПП)")],
            [KeyboardButton(text="⚙️ Любая коробка")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    pts_label = "Только оригинал" if pts_type == "original" else "Без дубликатов (Оригинал/ЭПТС)" if pts_type == "no_duplicate" else "Любой"
    await message.answer(
        f"✅ ПТС: <b>{pts_label}</b>\n\n"
        "🛠 <b>[Шаг 8 из 9] КОРОБКА ПЕРЕДАЧ (КПП)</b>\n"
        "<i>Выбери коробку передач:</i>",
        reply_markup=trans_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_transmission)
async def process_transmission(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    transmission = "any"
    if "автомат" in message.text.lower():
        transmission = "auto"
    elif "механика" in message.text.lower():
        transmission = "manual"

    await state.update_data(transmission=transmission)
    await state.set_state(DetailedFilterState.waiting_dealers)

    dealers_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Только собственники (без салонов и перекупов)")],
            [KeyboardButton(text="🏢 Все (включая автосалоны)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    trans_label = "Только автомат" if transmission == "auto" else "Только механика" if transmission == "manual" else "Любая"
    await message.answer(
        f"✅ КПП: <b>{trans_label}</b>\n\n"
        "🛠 <b>[Шаг 9 из 9] ПРОДАВЕЦ</b>\n"
        "<i>Исключать автосалоны, дилеров и перекупов?</i>",
        reply_markup=dealers_kb,
        parse_mode=ParseMode.HTML
    )


@dp.message(DetailedFilterState.waiting_dealers)
async def process_dealers(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await cmd_start(message, state)

    exclude_dealers = "Только собственники" in message.text
    data = await state.get_data()
    await state.clear()

    brand = data.get("brand", "")
    model = data.get("model", "")
    name = f"{brand} {model}".strip() or "Охота на авто"

    task_payload = {
        "name": name,
        "platform": "all",
        "brand": brand,
        "model": model,
        "exclude_brands_models": data.get("exclude_brands_models", ""),
        "year_min": data.get("year_min"),
        "year_max": data.get("year_max"),
        "price_min": data.get("price_min"),
        "price_max": data.get("price_max"),
        "mileage_max": data.get("mileage_max"),
        "owners_max": data.get("owners_max"),
        "pts_type": data.get("pts_type", "any"),
        "transmission": data.get("transmission", "any"),
        "drive_type": "any",
        "exclude_dealers": exclude_dealers,
        "exclude_damaged": True,
        "stop_words": "запрет, арест, без доков, залог"
    }

    new_task = await create_task(task_payload)

    main_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 НАСТРОИТЬ ПОИСК АВТО (ПОЛНОСТЬЮ)")],
            [KeyboardButton(text="📋 Активные фильтры"), KeyboardButton(text="🗑 Сбросить фильтры")]
        ],
        resize_keyboard=True
    )

    p_str = f"{new_task.price_min or 0:,} — {new_task.price_max or '∞':,} ₽".replace(",", " ")
    pts_label = "Только оригинал" if new_task.pts_type == "original" else "Без дубликатов (Оригинал/ЭПТС)" if new_task.pts_type == "no_duplicate" else "Любой"
    trans_label = "Только автомат" if new_task.transmission == "auto" else "Только механика" if new_task.transmission == "manual" else "Любая"

    summary = (
        "🚀 <b>ФИЛЬТР УСПЕШНО СОХРАНЕН И АКТИВИРОВАН!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚘 <b>Ищем:</b> {brand or 'Любая марка'} {model or ''}\n"
        f"🚫 <b>Исключено:</b> {new_task.exclude_brands_models or 'Ничего'}\n"
        f"💰 <b>Цена:</b> {p_str}\n"
        f"📅 <b>Года:</b> {new_task.year_min or '—'} - {new_task.year_max or '—'}\n"
        f"⏱ <b>Пробег:</b> {f'до {new_task.mileage_max:,} км' if new_task.mileage_max else 'любой'}\n"
        f"👥 <b>Владельцев:</b> {f'до {new_task.owners_max}' if new_task.owners_max else 'любое'}\n"
        f"📄 <b>Тип ПТС:</b> {pts_label}\n"
        f"🕹 <b>КПП:</b> {trans_label}\n"
        f"👤 <b>Продавец:</b> {'Только собственники' if new_task.exclude_dealers else 'Все'}\n"
        f"🛡 <b>Исключение битых/запретов:</b> Включено\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡️ <b>СКАНИРОВАНИЕ ЗАПУЩЕНО!</b> Как только на Drom, Auto.ru или Avito появится подходящая машина — карточка сразу прилетит сюда."
    )

    await message.answer(summary, reply_markup=main_kb, parse_mode=ParseMode.HTML)


@dp.message(F.text == "📋 Активные фильтры")
@dp.message(Command("filters"))
async def show_filters(message: types.Message):
    tasks = await get_active_tasks()
    if not tasks:
        await message.answer("⚠️ Нет активных фильтров. Нажми кнопку <b>🎯 НАСТРОИТЬ ПОИСК АВТО</b>.")
        return

    text = "📋 <b>АКТИВНЫЕ ФИЛЬТРЫ МОНИТОРИНГА:</b>\n\n"
    for i, t in enumerate(tasks, 1):
        price_str = f"{t.price_min or 0:,} — {t.price_max or '∞':,} ₽".replace(",", " ")
        years = f"{t.year_min or '—'} - {t.year_max or '—'}"
        pts_label = "Только оригинал" if t.pts_type == "original" else "Без дубликатов" if t.pts_type == "no_duplicate" else "Любой"
        trans_label = "Автомат" if t.transmission == "auto" else "Механика" if t.transmission == "manual" else "Любая"

        text += (
            f"<b>{i}. {t.name}</b>\n"
            f"🚘 Авто: {t.brand or 'Любая'} {t.model or ''}\n"
            f"🚫 Исключено: {t.exclude_brands_models or '—'}\n"
            f"💰 Цена: {price_str} | 📅 Год: {years}\n"
            f"⏱ Пробег: {f'до {t.mileage_max:,} км' if t.mileage_max else 'любой'}\n"
            f"👥 Владельцев: {f'до {t.owners_max}' if t.owners_max else 'любое'}\n"
            f"📄 ПТС: {pts_label} | 🕹 КПП: {trans_label}\n"
            f"👤 Продавец: {'Только собственники' if t.exclude_dealers else 'Все'}\n\n"
        )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(F.text == "🗑 Сбросить фильтры")
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
