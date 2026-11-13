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
        # 1. Platform check
        if task.platform != "all" and task.platform.lower() != car.get("platform", "").lower():
            return False, "Не совпадает платформа"

        # 2. Brand & Model check
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

        # 3. Year range
        car_year = car.get("year")
        if car_year:
            if task.year_min and car_year < task.year_min:
                return False, f"Год меньше мин. ({car_year} < {task.year_min})"
            if task.year_max and car_year > task.year_max:
                return False, f"Год больше макс. ({car_year} > {task.year_max})"

        # 4. Price range
        price = car.get("price") or 0
        if price > 0:
            if task.price_min and price < task.price_min:
                return False, f"Цена ниже мин. ({price} < {task.price_min})"
            if task.price_max and price > task.price_max:
                return False, f"Цена выше макс. ({price} > {task.price_max})"

        # 5. Mileage
        car_mileage = car.get("mileage")
        if car_mileage and task.mileage_max:
            if car_mileage > task.mileage_max:
                return False, f"Пробег больше макс. ({car_mileage} > {task.mileage_max})"

        # 6. Owners count
        car_owners = car.get("owners_count")
        if car_owners and task.owners_max:
            if car_owners > task.owners_max:
                return False, f"Владельцев больше макс. ({car_owners} > {task.owners_max})"

        # 7. Dealer exclusion
        if task.exclude_dealers and car.get("is_dealer"):
            return False, "Исключен автосалон / дилер"

        # 8. Damaged exclusion
        text_corpus = f"{car.get('title', '')} {car.get('description', '')}".lower()
        if task.exclude_damaged:
            for kw in cls.DAMAGED_KEYWORDS:
                if re.search(r"\b" + re.escape(kw), text_corpus):
                    return False, f"Исключено битое/аварийное авто ({kw})"

        # 9. Stop words
        all_stop_words = list(cls.DEFAULT_STOP_WORDS)
        if task.stop_words:
            custom_words = [w.strip().lower() for w in task.stop_words.split(",") if w.strip()]
            all_stop_words.extend(custom_words)

        for word in all_stop_words:
            if word in text_corpus:
                return False, f"Найдено стоп-слово: '{word}'"

        return True, "Подходит"
