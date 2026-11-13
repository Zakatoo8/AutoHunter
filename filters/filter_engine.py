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

    COUNTRY_BRANDS = {
        "china": ["chery", "haval", "geely", "changan", "omoda", "jaecoo", "exeed", "jetour", "tank", "zeekr", "lixiang", "li auto", "voyah", "faw", "dongfeng", "gac", "baic", "kaiyi", "livan", "belgee"],
        "russia": ["lada", "ваз", "уаз", "газ", "москвич", "granta", "vesta", "niva", "priora", "kalina", "largus"],
        "germany": ["bmw", "mercedes", "audi", "volkswagen", "porsche", "opel"],
        "japan": ["toyota", "nissan", "mazda", "honda", "mitsubishi", "subaru", "lexus", "infiniti", "suzuki"],
        "korea": ["kia", "hyundai", "genesis", "ssangyong"],
        "usa": ["ford", "chevrolet", "cadillac", "jeep", "dodge", "tesla", "chrysler"],
        "france": ["renault", "peugeot", "citroen"]
    }

    BODY_TYPE_KEYWORDS = {
        "sedan": ["седан", "sedan"],
        "suv": ["внедорожник", "кроссовер", "suv", "джип", "4x4"],
        "hatchback": ["хэтчбек", "хэтч", "hatchback"],
        "wagon": ["универсал", "wagon", "touring", "avant", "estate"],
        "coupe": ["купе", "coupe"],
        "liftback": ["лифтбек", "liftback"]
    }

    @classmethod
    def matches_task(cls, car: Dict[str, Any], task: SearchTask) -> Tuple[bool, str]:
        text_corpus = f"{car.get('title', '')} {car.get('description', '')}".lower()
        car_brand = (car.get("brand") or "").lower()
        car_model = (car.get("model") or "").lower()

        # 1. Platform check
        if task.platform != "all" and task.platform.lower() != car.get("platform", "").lower():
            return False, "Не совпадает платформа"

        # 2. Exclude Countries
        if task.exclude_countries:
            countries = [c.strip().lower() for c in task.exclude_countries.split(",") if c.strip()]
            for country in countries:
                b_list = cls.COUNTRY_BRANDS.get(country, [])
                for b in b_list:
                    if b in text_corpus or b in car_brand:
                        return False, f"Исключена страна производителя ({country})"

        # 3. Exclude Specific Brands / Models
        if task.exclude_brands_models:
            excluded_items = [b.strip().lower() for b in task.exclude_brands_models.split(",") if b.strip()]
            for exc in excluded_items:
                if exc in text_corpus or exc in car_brand or exc in car_model:
                    return False, f"Исключенная марка/модель ({exc})"

        # 4. Target Brand check
        if task.brand and task.brand.lower() != "любая":
            task_brand = task.brand.lower().strip()
            if task_brand not in car_brand and task_brand not in text_corpus:
                return False, f"Бренд не подходит ({task.brand})"

        # 5. Target Model check
        if task.model and task.model.lower() != "любая":
            task_model = task.model.lower().strip()
            if task_model not in car_model and task_model not in text_corpus:
                return False, f"Модель не подходит ({task.model})"

        # 6. Body Type check
        if task.body_type and task.body_type != "any":
            keywords = cls.BODY_TYPE_KEYWORDS.get(task.body_type, [task.body_type])
            if not any(k in text_corpus for k in keywords):
                return False, f"Тип кузова не соответствует ({task.body_type})"

        # 7. Year range
        car_year = car.get("year")
        if car_year:
            if task.year_min and car_year < task.year_min:
                return False, f"Год меньше мин. ({car_year} < {task.year_min})"
            if task.year_max and car_year > task.year_max:
                return False, f"Год больше макс. ({car_year} > {task.year_max})"

        # 8. Price range
        price = car.get("price") or 0
        if price > 0:
            if task.price_min and price < task.price_min:
                return False, f"Цена ниже мин. ({price} < {task.price_min})"
            if task.price_max and price > task.price_max:
                return False, f"Цена выше макс. ({price} > {task.price_max})"

        # 9. Mileage
        car_mileage = car.get("mileage")
        if car_mileage and task.mileage_max:
            if car_mileage > task.mileage_max:
                return False, f"Пробег больше макс. ({car_mileage} > {task.mileage_max})"

        # 10. Owners count
        car_owners = car.get("owners_count")
        if car_owners and task.owners_max:
            if car_owners > task.owners_max:
                return False, f"Владельцев больше макс. ({car_owners} > {task.owners_max})"

        # 11. PTS Type Check
        if task.pts_type and task.pts_type != "any":
            if "дубликат" in text_corpus:
                return False, "Отклонен дубликат ПТС"
            if task.pts_type == "original" and "дубликат" in text_corpus:
                return False, "Требуется оригинал ПТС"

        # 12. Transmission Check
        if task.transmission and task.transmission != "any":
            is_auto = any(w in text_corpus for w in ["акпп", "автомат", "робот", "вариатор", "cvt", "at", "dsg", "dct"])
            is_manual = any(w in text_corpus for w in ["мкпп", "механик", "mt"])
            if task.transmission == "auto" and is_manual and not is_auto:
                return False, "Нужен автомат, а в объявлении механика"
            if task.transmission == "manual" and is_auto and not is_manual:
                return False, "Нужна механика, а в объявлении автомат"

        # 13. Drive Type Check
        if task.drive_type and task.drive_type != "any":
            if task.drive_type == "4wd":
                if not any(w in text_corpus for w in ["4wd", "полный", "awd", "4x4", "quattro", "xdrive", "4matic"]):
                    return False, "Требуется полный привод (4WD)"
            elif task.drive_type == "fwd":
                if "полный" in text_corpus or "4wd" in text_corpus or "задний" in text_corpus:
                    return False, "Требуется передний привод"

        # 14. Steering Wheel Check
        if task.steering_wheel == "left" and "правый руль" in text_corpus:
            return False, "Исключен правый руль"

        # 15. Dealer exclusion
        if task.exclude_dealers and car.get("is_dealer"):
            return False, "Исключен автосалон / дилер"

        # 16. Damaged exclusion
        if task.exclude_damaged:
            for kw in cls.DAMAGED_KEYWORDS:
                if re.search(r"\b" + re.escape(kw), text_corpus):
                    return False, f"Исключено битое/аварийное авто ({kw})"

        # 17. Stop words
        all_stop_words = list(cls.DEFAULT_STOP_WORDS)
        if task.stop_words:
            custom_words = [w.strip().lower() for w in task.stop_words.split(",") if w.strip()]
            all_stop_words.extend(custom_words)

        for word in all_stop_words:
            if word in text_corpus:
                return False, f"Найдено стоп-слово: '{word}'"

        return True, "Подходит"
