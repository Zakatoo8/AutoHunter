import logging
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import settings
from database.db_manager import (
    get_active_tasks, get_recent_cars, create_task, delete_task
)
from checkers.vin_decoder import VinDecoder

logger = logging.getLogger("AutoHunterBot")

bot: Optional[Bot] = None
dp = Dispatcher()


def get_bot() -> Optional[Bot]:
    global bot
    if not bot and settings.TG_BOT_TOKEN:
        bot = Bot(token=settings.TG_BOT_TOKEN)
    return bot


# --- Handler for Telegram Mini App Data ---
@dp.message(F.web_app_data)
async def handle_miniapp_data(message: types.Message):
    try:
        import json
        payload = json.loads(message.web_app_data.data)

        # Clean old tasks
        existing = await get_active_tasks()
        for t in existing:
            await delete_task(t.id)

        new_task = await create_task(payload)

        p_str = f"{new_task.price_min or 0:,} — {new_task.price_max or '∞':,} ₽".replace(",", " ")
        pts_label = "Только оригинал" if new_task.pts_type == "original" else "Без дубликатов" if new_task.pts_type == "no_duplicate" else "Любой"
        trans_label = "Автомат" if new_task.transmission == "auto" else "Механика" if new_task.transmission == "manual" else "Любая"

        text = (
            "🚀 <b>ФИЛЬТР УСПЕШНО СОХРАНЕН ЧЕРЕЗ MINI APP!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚘 <b>Марка:</b> {new_task.brand or 'Любая'}\n"
            f"🚫 <b>Исключено:</b> {new_task.exclude_brands_models or 'Нет'}\n"
            f"💰 <b>Бюджет:</b> {p_str}\n"
            f"📅 <b>Год:</b> от {new_task.year_min or 'любого'}\n"
            f"⏱ <b>Пробег:</b> {f'до {new_task.mileage_max:,} км' if new_task.mileage_max else 'любой'}\n"
            f"👥 <b>Владельцев:</b> {f'до {new_task.owners_max}' if new_task.owners_max else 'любое'}\n"
            f"📄 <b>ПТС:</b> {pts_label}\n"
            f"🕹 <b>КПП:</b> {trans_label}\n"
            f"👤 <b>Продавец:</b> {'Только собственники' if new_task.exclude_dealers else 'Все'}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡️ <b>МОНИТОРИНГ ЗАПУЩЕН!</b> Чекер слушает Drom, Auto.ru и Avito."
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎛 Открыть MiniApp заново", web_app=types.WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton(text="🗑 Остановить поиск", callback_data="reset_tasks")]
        ])

        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error handling web_app_data: {e}")
        await message.answer(f"Ошибка сохранения: {e}")
default_config = {
    "brand": "Любая",
    "exclude_china": True,
    "exclude_vaz": False,
    "price_label": "1 — 2.2 млн ₽",
    "price_min": 1000000,
    "price_max": 2200000,
    "year_label": "от 2015 г.",
    "year_min": 2015,
    "year_max": None,
    "mileage_label": "до 150 000 км",
    "mileage_max": 150000,
    "owners_label": "до 2 владельцев",
    "owners_max": 2,
    "pts_type": "no_duplicate",      # "original", "no_duplicate", "any"
    "transmission": "auto",          # "auto", "manual", "any"
    "exclude_dealers": True          # True = только собственники
}

# In-memory storage for user configuration drafts
user_configs: Dict[int, dict] = {}


def get_user_cfg(user_id: int) -> dict:
    if user_id not in user_configs:
        user_configs[user_id] = dict(default_config)
    return user_configs[user_id]


def build_config_text(cfg: dict) -> str:
    pts_map = {
        "original": "📄 Только оригинал",
        "no_duplicate": "🚫 Без дубликатов (Оригинал/ЭПТС)",
        "any": "📑 Любой (включая дубликаты)"
    }
    trans_map = {
        "auto": "🕹 Только автомат (АКПП/Робот)",
        "manual": "🕹 Только механика",
        "any": "⚙️ Любая коробка"
    }
    dealers_str = "👤 Только собственники" if cfg["exclude_dealers"] else "🏢 Все (включая салоны)"

    excluded = []
    if cfg["exclude_china"]:
        excluded.append("Китайцы (Chery/Haval/Geely/Changan)")
    if cfg["exclude_vaz"]:
        excluded.append("АвтоВАЗ / Lada")
    excluded_str = ", ".join(excluded) if excluded else "Нет"

    text = (
        "🎛 <b>КОНФИГУРАТОР ФИЛЬТРОВ ПОИСКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚗 <b>Марка:</b> {cfg['brand']}\n"
        f"🚫 <b>Исключить:</b> {excluded_str}\n"
        f"💰 <b>Бюджет:</b> {cfg['price_label']}\n"
        f"📅 <b>Года выпуска:</b> {cfg['year_label']}\n"
        f"⏱ <b>Пробег:</b> {cfg['mileage_label']}\n"
        f"👥 <b>Владельцев по ПТС:</b> {cfg['owners_label']}\n"
        f"📄 <b>Тип ПТС:</b> {pts_map.get(cfg['pts_type'])}\n"
        f"🕹 <b>Коробка (КПП):</b> {trans_map.get(cfg['transmission'])}\n"
        f"👤 <b>Продавец:</b> {dealers_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Нажимай кнопки ниже, чтобы моментально изменить любой параметр:</i>"
    )
    return text


def build_main_keyboard(cfg: dict) -> InlineKeyboardMarkup:
    pts_short = "Оригинал" if cfg["pts_type"] == "original" else "Без дублей" if cfg["pts_type"] == "no_duplicate" else "Любой"
    trans_short = "АКПП" if cfg["transmission"] == "auto" else "МКПП" if cfg["transmission"] == "manual" else "Любая"
    dealers_short = "Частники" if cfg["exclude_dealers"] else "Все продавцы"

    china_btn = "✅ Без Китая" if cfg["exclude_china"] else "⚪️ Включая Китай"
    vaz_btn = "✅ Без ВАЗ" if cfg["exclude_vaz"] else "⚪️ Включая ВАЗ"

    kb = [
        [
            InlineKeyboardButton(text=f"🚗 Марка: {cfg['brand']}", callback_data="menu_brand"),
            InlineKeyboardButton(text=f"💰 Цена: {cfg['price_label']}", callback_data="menu_price")
        ],
        [
            InlineKeyboardButton(text=f"📅 Год: {cfg['year_label']}", callback_data="menu_year"),
            InlineKeyboardButton(text=f"⏱ Пробег: {cfg['mileage_label']}", callback_data="menu_mileage")
        ],
        [
            InlineKeyboardButton(text=f"👥 Владельцы: {cfg['owners_label']}", callback_data="menu_owners"),
            InlineKeyboardButton(text=f"📄 ПТС: {pts_short}", callback_data="menu_pts")
        ],
        [
            InlineKeyboardButton(text=f"🕹 КПП: {trans_short}", callback_data="menu_trans"),
            InlineKeyboardButton(text=f"👤 Продавец: {dealers_short}", callback_data="toggle_dealers")
        ],
        [
            InlineKeyboardButton(text=china_btn, callback_data="toggle_china"),
            InlineKeyboardButton(text=vaz_btn, callback_data="toggle_vaz")
        ],
        [
            InlineKeyboardButton(text="🚀 ЗАПУСТИТЬ ОХОТУ ПО ЭТИМ ФИЛЬТРАМ 🚀", callback_data="save_and_hunt")
        ],
        [
            InlineKeyboardButton(text="📋 Мои активные задачи", callback_data="show_tasks"),
            InlineKeyboardButton(text="🗑 Сбросить фильтр", callback_data="reset_tasks")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
@dp.message(Command("filter"))
@dp.message(F.text)
async def cmd_start(message: types.Message):
    cfg = get_user_cfg(message.from_user.id)
    text = build_config_text(cfg)
    kb = build_main_keyboard(cfg)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- Callback Handlers for Quick Button Toggles ---

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: types.CallbackQuery):
    cfg = get_user_cfg(call.from_user.id)
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


@dp.callback_query(F.data == "toggle_dealers")
async def cb_toggle_dealers(call: types.CallbackQuery):
    cfg = get_user_cfg(call.from_user.id)
    cfg["exclude_dealers"] = not cfg["exclude_dealers"]
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


@dp.callback_query(F.data == "toggle_china")
async def cb_toggle_china(call: types.CallbackQuery):
    cfg = get_user_cfg(call.from_user.id)
    cfg["exclude_china"] = not cfg["exclude_china"]
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


@dp.callback_query(F.data == "toggle_vaz")
async def cb_toggle_vaz(call: types.CallbackQuery):
    cfg = get_user_cfg(call.from_user.id)
    cfg["exclude_vaz"] = not cfg["exclude_vaz"]
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: Brand selection ---
@dp.callback_query(F.data == "menu_brand")
async def cb_menu_brand(call: types.CallbackQuery):
    brands = [
        ["Любая марка", "Toyota", "BMW"],
        ["Mercedes-Benz", "Audi", "Volkswagen"],
        ["Kia", "Hyundai", "Skoda"],
        ["Nissan", "Mazda", "Lada (ВАЗ)"]
    ]
    kb = []
    for row in brands:
        kb.append([InlineKeyboardButton(text=b, callback_data=f"set_brand_{b}") for b in row])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")])

    await call.message.edit_text(
        "🚗 <b>ВЫБЕРИ МАРКУ АВТОМОБИЛЯ:</b>\n<i>Нажми кнопку нужной марки:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_brand_"))
async def cb_set_brand(call: types.CallbackQuery):
    brand = call.data.replace("set_brand_", "")
    cfg = get_user_cfg(call.from_user.id)
    cfg["brand"] = brand
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer(f"Выбрана марка: {brand}")


# --- Sub-menu: Price selection ---
@dp.callback_query(F.data == "menu_price")
async def cb_menu_price(call: types.CallbackQuery):
    prices = [
        ("До 700 000 ₽", 0, 700000),
        ("700к — 1.3 млн ₽", 700000, 1300000),
        ("1.3 — 2.2 млн ₽", 1300000, 2200000),
        ("2.2 — 3.5 млн ₽", 2200000, 3500000),
        ("3.5 — 6.0 млн ₽", 3500000, 6000000),
        ("Любой бюджет", 0, None)
    ]
    kb = []
    for label, p_min, p_max in prices:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"set_price_{p_min}_{p_max}_{label}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")])

    await call.message.edit_text(
        "💰 <b>ВЫБЕРИ ДИАПАЗОН БЮДЖЕТА (ЦЕНЫ):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_price_"))
async def cb_set_price(call: types.CallbackQuery):
    parts = call.data.replace("set_price_", "").split("_")
    p_min = int(parts[0]) if parts[0] != "0" else None
    p_max = int(parts[1]) if parts[1] != "None" else None
    label = parts[2]

    cfg = get_user_cfg(call.from_user.id)
    cfg["price_min"] = p_min
    cfg["price_max"] = p_max
    cfg["price_label"] = label

    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: Year selection ---
@dp.callback_query(F.data == "menu_year")
async def cb_menu_year(call: types.CallbackQuery):
    years = [
        ("от 2010 г.", 2010),
        ("от 2014 г.", 2014),
        ("от 2017 г.", 2017),
        ("от 2020 г.", 2020),
        ("от 2022 г. (Свежие)", 2022),
        ("Любой год", None)
    ]
    kb = []
    for label, y_min in years:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"set_year_{y_min}_{label}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")])

    await call.message.edit_text(
        "📅 <b>ВЫБЕРИ ГОДА ВЫПУСКА:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_year_"))
async def cb_set_year(call: types.CallbackQuery):
    parts = call.data.replace("set_year_", "").split("_")
    y_min = int(parts[0]) if parts[0] != "None" else None
    label = parts[1]

    cfg = get_user_cfg(call.from_user.id)
    cfg["year_min"] = y_min
    cfg["year_label"] = label

    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: Mileage selection ---
@dp.callback_query(F.data == "menu_mileage")
async def cb_menu_mileage(call: types.CallbackQuery):
    mileages = [
        ("до 60 000 км", 60000),
        ("до 110 000 км", 110000),
        ("до 150 000 км", 150000),
        ("до 200 000 км", 200000),
        ("Любой пробег", None)
    ]
    kb = []
    for label, m_max in mileages:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"set_mileage_{m_max}_{label}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")])

    await call.message.edit_text(
        "⏱ <b>ВЫБЕРИ МАКСИМАЛЬНЫЙ ПРОБЕГ:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_mileage_"))
async def cb_set_mileage(call: types.CallbackQuery):
    parts = call.data.replace("set_mileage_", "").split("_")
    m_max = int(parts[0]) if parts[0] != "None" else None
    label = parts[1]

    cfg = get_user_cfg(call.from_user.id)
    cfg["mileage_max"] = m_max
    cfg["mileage_label"] = label

    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: Owners selection ---
@dp.callback_query(F.data == "menu_owners")
async def cb_menu_owners(call: types.CallbackQuery):
    owners = [
        ("1️⃣ Только 1 владелец", 1, "1 владелец"),
        ("2️⃣ До 2 владельцев", 2, "до 2 владельцев"),
        ("3️⃣ До 3 владельцев", 3, "до 3 владельцев"),
        ("♾ Любое количество", None, "любое количество")
    ]
    kb = []
    for label, count, short in owners:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"set_owners_{count}_{short}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")])

    await call.message.edit_text(
        "👥 <b>СКОЛЬКО МАКСИМУМ ВЛАДЕЛЬЦЕВ ПО ПТС:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_owners_"))
async def cb_set_owners(call: types.CallbackQuery):
    parts = call.data.replace("set_owners_", "").split("_")
    o_max = int(parts[0]) if parts[0] != "None" else None
    label = parts[1]

    cfg = get_user_cfg(call.from_user.id)
    cfg["owners_max"] = o_max
    cfg["owners_label"] = label

    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: PTS selection ---
@dp.callback_query(F.data == "menu_pts")
async def cb_menu_pts(call: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="📄 Только оригинал ПТС", callback_data="set_pts_original")],
        [InlineKeyboardButton(text="🚫 Без дубликатов (Оригинал или ЭПТС)", callback_data="set_pts_no_duplicate")],
        [InlineKeyboardButton(text="📑 Любой ПТС (включая дубликаты)", callback_data="set_pts_any")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")]
    ]
    await call.message.edit_text(
        "📄 <b>ВЫБЕРИ ТРЕБОВАНИЯ К ПТС:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_pts_"))
async def cb_set_pts(call: types.CallbackQuery):
    pts = call.data.replace("set_pts_", "")
    cfg = get_user_cfg(call.from_user.id)
    cfg["pts_type"] = pts
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Sub-menu: Transmission selection ---
@dp.callback_query(F.data == "menu_trans")
async def cb_menu_trans(call: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🕹 Только автомат (АКПП, Робот, Вариатор)", callback_data="set_trans_auto")],
        [InlineKeyboardButton(text="🕹 Только механика (МКПП)", callback_data="set_trans_manual")],
        [InlineKeyboardButton(text="⚙️ Любая коробка передач", callback_data="set_trans_any")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")]
    ]
    await call.message.edit_text(
        "🕹 <b>ВЫБЕРИ КОРОБКУ ПЕРЕДАЧ (КПП):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_trans_"))
async def cb_set_trans(call: types.CallbackQuery):
    trans = call.data.replace("set_trans_", "")
    cfg = get_user_cfg(call.from_user.id)
    cfg["transmission"] = trans
    await call.message.edit_text(build_config_text(cfg), reply_markup=build_main_keyboard(cfg), parse_mode=ParseMode.HTML)
    await call.answer()


# --- Action: Save and Start Hunting ---
@dp.callback_query(F.data == "save_and_hunt")
async def cb_save_and_hunt(call: types.CallbackQuery):
    cfg = get_user_cfg(call.from_user.id)

    # Clean old tasks first so user only hunts their desired car
    existing = await get_active_tasks()
    for t in existing:
        await delete_task(t.id)

    # Build excluded string
    excluded = []
    if cfg["exclude_china"]:
        excluded.extend(["chery", "haval", "geely", "changan", "omoda", "jaecoo", "exeed", "jetour", "faw", "dongfeng", "voyah"])
    if cfg["exclude_vaz"]:
        excluded.extend(["lada", "ваз", "granta", "vesta", "niva"])

    brand = "" if cfg["brand"] == "Любая марка" else cfg["brand"]

    task_payload = {
        "name": f"Охота: {cfg['brand']}",
        "platform": "all",
        "brand": brand,
        "model": "",
        "exclude_brands_models": ", ".join(excluded),
        "year_min": cfg.get("year_min"),
        "year_max": cfg.get("year_max"),
        "price_min": cfg.get("price_min"),
        "price_max": cfg.get("price_max"),
        "mileage_max": cfg.get("mileage_max"),
        "owners_max": cfg.get("owners_max"),
        "pts_type": cfg.get("pts_type", "any"),
        "transmission": cfg.get("transmission", "any"),
        "drive_type": "any",
        "exclude_dealers": cfg.get("exclude_dealers", True),
        "exclude_damaged": True,
        "stop_words": "запрет, арест, без доков, залог"
    }

    new_task = await create_task(task_payload)

    text = (
        "🚀 <b>ОХОТА УСПЕШНО ЗАПУЩЕНА!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚘 <b>Марка:</b> {cfg['brand']}\n"
        f"💰 <b>Бюджет:</b> {cfg['price_label']}\n"
        f"📅 <b>Год:</b> {cfg['year_label']}\n"
        f"⏱ <b>Пробег:</b> {cfg['mileage_label']}\n"
        f"👥 <b>Владельцев:</b> {cfg['owners_label']}\n"
        f"📄 <b>ПТС:</b> {'Только оригинал' if cfg['pts_type'] == 'original' else 'Без дубликатов' if cfg['pts_type'] == 'no_duplicate' else 'Любой'}\n"
        f"🕹 <b>КПП:</b> {'Автомат' if cfg['transmission'] == 'auto' else 'Механика' if cfg['transmission'] == 'manual' else 'Любая'}\n"
        f"👤 <b>Продавец:</b> {'Только собственники' if cfg['exclude_dealers'] else 'Все'}\n"
        f"🚫 <b>Исключения:</b> {', '.join(excluded) if excluded else 'Нет'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡️ <b>Чекер прямо сейчас слушает Drom, Auto.ru и Avito.</b>\n"
        "Как только появится тачка, идеально проходящая этот фильтр — карточка с фото сразу прилетит сюда."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Изменить фильтры", callback_data="main_menu")],
        [InlineKeyboardButton(text="🗑 Остановить поиск", callback_data="reset_tasks")]
    ])

    await call.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await call.answer("Охота запущена!")


@dp.callback_query(F.data == "reset_tasks")
async def cb_reset_tasks(call: types.CallbackQuery):
    tasks = await get_active_tasks()
    for t in tasks:
        await delete_task(t.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎛 Настроить фильтр кнопками", callback_data="main_menu")]
    ])
    await call.message.edit_text("🛑 <b>Поиск полностью остановлен.</b> Все фильтры сброшены.", reply_markup=kb, parse_mode=ParseMode.HTML)
    await call.answer("Поиск остановлен")


@dp.callback_query(F.data == "show_tasks")
async def cb_show_tasks(call: types.CallbackQuery):
    tasks = await get_active_tasks()
    if not tasks:
        text = "⚠️ <b>Сейчас нет активных фильтров.</b> Настрой их кнопками ниже:"
    else:
        text = "📋 <b>АКТИВНЫЙ ФИЛЬТР МОНИТОРИНГА:</b>\n\n"
        for t in tasks:
            p_str = f"{t.price_min or 0:,} — {t.price_max or '∞':,} ₽".replace(",", " ")
            text += (
                f"🚗 Марка: {t.brand or 'Любая'}\n"
                f"💰 Бюджет: {p_str}\n"
                f"📅 Год: от {t.year_min or 'любого'}\n"
                f"⏱ Пробег: {f'до {t.mileage_max:,} км' if t.mileage_max else 'любой'}\n"
                f"👥 Владельцев: {f'до {t.owners_max}' if t.owners_max else 'любое'}\n"
                f"👤 Продавец: {'Только собственники' if t.exclude_dealers else 'Все'}\n"
            )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎛 Изменить фильтр", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await call.answer()


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
