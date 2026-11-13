import re
from typing import Optional, Dict


class VinDecoder:
    @staticmethod
    def clean_vin(vin: Optional[str]) -> Optional[str]:
        if not vin:
            return None
        cleaned = re.sub(r"[^A-HJ-NPR-Z0-9]", "", vin.upper())
        if len(cleaned) == 17:
            return cleaned
        return None

    @classmethod
    def get_free_check_links(cls, vin: Optional[str] = None, plate: Optional[str] = None) -> Dict[str, str]:
        links = {}
        if vin:
            cleaned_vin = cls.clean_vin(vin)
            if cleaned_vin:
                links["ГИБДД"] = f"https://xn--b1afk4ade.xn--90adear.xn--p1ai/check/auto#{cleaned_vin}"
                links["Реестр залогов"] = f"https://www.reestr-zalogov.ru/search/index?vin={cleaned_vin}"
                links["VIN01"] = f"https://vin01.ru/?vin={cleaned_vin}"

        if plate:
            clean_plate = re.sub(r"[^А-ЯA-Z0-9]", "", plate.upper())
            links["Номерограм"] = f"https://nomerogram.ru/n/{clean_plate}/"
            links["Автокод (Мос)"] = f"https://avtokod.mos.ru/"

        return links
