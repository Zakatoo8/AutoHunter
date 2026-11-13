import re
from typing import Dict, Any, Tuple
from database.models import SearchTask


class FilterEngine:
    DEFAULT_STOP_WORDS = [
        "запрет", "арест", "ограничени", "без птс", "без док", "на запчаст", 
        "не растамож", "вечный учет", "армян", "абхаз", "двойник", "в залог"
    ]

    DAMAGED_KEYWORDS = [
        "битый", "битая", "после дтп", "не на ходу", "аварийный", "аварийная",
        "под восстановление", "требует ремонта кузова", "геометрия"
    ]

    @classmethod
    def matches_task(cls, car: Dict[str, Any], task: SearchTask) -> Tuple[bool, str]:
        """
        Returns (is_match, reason)
        """
        text_corpus = f"{car.get('title', '')} {car.get('description', '')}".lower()

        # 1. Platform check
        if task.platform != "all" and task.platform.lower() != car.get("platform", "").lower():
            return False, "Не совпадает платформа"

        # 2. Excluded Brands / Models (Blacklist)
        if task.exclude_brands_models:
            excluded_items = [b.strip().lower() for b in task.exclude_brands_models.split(",") if b.strip()]
            for exc in excluded_items:
                if exc in text_corpus or exc in (car.get("brand") or "").lower() or exc in (car.get("model") or "").lower():
                    return False, f"Исключенная марка/модель ({exc})"

        # 3. Brand & Model check (Whitelist)
        if task.brand:
            car_brand = (car.get("brand") or "").lower()
            car_title = (car.get("title") or "").lower()
            task_brand = task.brand.lower().strip()
            if task_brand not in car_brand and task_brand not in car_title:
                return False, f"Бренд не подходит ({task.brand})"

        if task.model:
            car_model = (car.get("model") or "").lower()
            car_title = (car.get("title") or "").lower()
            task_model = task.model.lower().strip()
            if task_model not in car_model and task_model not in car_title:
                return False, f"Модель не подходит ({task.model})"

        # 4. Year range
        car_year = car.get("year")
        if car_year:
            if task.year_min and car_year < task.year_min:
                return False, f"Год меньше мин. ({car_year} < {task.year_min})"
            if task.year_max and car_year > task.year_max:
                return False, f"Год больше макс. ({car_year} > {task.year_max})"

        # 5. Price range
        price = car.get("price") or 0
        if price > 0:
            if task.price_min and price < task.price_min:
                return False, f"Цена ниже мин. ({price} < {task.price_min})"
            if task.price_max and price > task.price_max:
                return False, f"Цена выше макс. ({price} > {task.price_max})"

        # 6. Mileage
        car_mileage = car.get("mileage")
        if car_mileage and task.mileage_max:
            if car_mileage > task.mileage_max:
                return False, f"Пробег больше макс. ({car_mileage} > {task.mileage_max})"

        # 7. Owners count
        car_owners = car.get("owners_count")
        if car_owners and task.owners_max:
            if car_owners > task.owners_max:
                return False, f"Владельцев больше макс. ({car_owners} > {task.owners_max})"

        # 8. PTS Type Check ("any", "original", "electronic", "no_duplicate")
        if task.pts_type and task.pts_type != "any":
            if "дубликат" in text_corpus:
                return False, "Отклонен дубликат ПТС"
            if task.pts_type == "original":
                # If explicit mention of duplicate -> rejected. If required strictly original
                if "дубликат" in text_corpus:
                    return False, "Требуется оригинал ПТС (найден дубликат)"
            elif task.pts_type == "electronic":
                if "эптс" not in text_corpus and "электрон" not in text_corpus:
                    # In some listings it might not say explicitly, but if required strictly electronic
                    pass

        # 9. Transmission Check ("any", "auto", "manual")
        if task.transmission and task.transmission != "any":
            is_auto = any(w in text_corpus for w in ["акпп", "автомат", "робот", "вариатор", "cvt", "at", "dsg", "dct"])
            is_manual = any(w in text_corpus for w in ["мкпп", "механик", "mt"])
            if task.transmission == "auto" and is_manual and not is_auto:
                return False, "Нужен автомат, а в объявлении механика"
            if task.transmission == "manual" and is_auto and not is_manual:
                return False, "Нужна механика, а в объявлении автомат"

        # 10. Drive Type Check ("any", "4wd", "fwd", "rwd")
        if task.drive_type and task.drive_type != "any":
            if task.drive_type == "4wd":
                if not any(w in text_corpus for w in ["4wd", "полный", "awd", "4x4", "quattro", "xdrive", "4matic"]):
                    return False, "Требуется полный привод (4WD)"
            elif task.drive_type == "fwd":
                if "полный" in text_corpus or "4wd" in text_corpus or "задний" in text_corpus:
                    return False, "Требуется передний привод"

        # 11. Dealer exclusion
        if task.exclude_dealers and car.get("is_dealer"):
            return False, "Исключен автосалон / дилер"

        # 12. Damaged exclusion
        if task.exclude_damaged:
            for kw in cls.DAMAGED_KEYWORDS:
                if re.search(r"\b" + re.escape(kw), text_corpus):
                    return False, f"Исключено битое/аварийное авто ({kw})"

        # 13. Stop words
        all_stop_words = list(cls.DEFAULT_STOP_WORDS)
        if task.stop_words:
            custom_words = [w.strip().lower() for w in task.stop_words.split(",") if w.strip()]
            all_stop_words.extend(custom_words)

        for word in all_stop_words:
            if word in text_corpus:
                return False, f"Найдено стоп-слово: '{word}'"

        return True, "Подходит"
