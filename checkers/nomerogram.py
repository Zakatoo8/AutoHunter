import re
from typing import Optional, Dict
from curl_cffi.requests import AsyncSession


class NomerogramChecker:
    BASE_URL = "https://nomerogram.ru"

    @staticmethod
    def normalize_plate(plate: str) -> Optional[str]:
        if not plate:
            return None
        # Clean plate: uppercase, remove spaces, cyrillic/latin normalization if needed
        clean = re.sub(r"[^А-ЯA-Z0-9]", "", plate.upper())
        # Example pattern for Russian standard: А123АА77 or А123АА777
        match = re.search(r"([А-ЯA-Z]\d{3}[А-ЯA-Z]{2})(\d{2,3})", clean)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        return clean if len(clean) >= 6 else None

    @classmethod
    async def check_plate(cls, plate: str) -> Optional[Dict]:
        normalized = cls.normalize_plate(plate)
        if not normalized:
            return None

        target_url = f"{cls.BASE_URL}/n/{normalized}/"
        try:
            async with AsyncSession(impersonate="chrome120", timeout=10) as session:
                resp = await session.get(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                })
                if resp.status_code == 200:
                    html = resp.text
                    # Check if photos exist on page
                    photos = re.findall(r'https://[^"]+images\.nomerogram\.ru[^"]+', html)
                    return {
                        "plate": normalized,
                        "url": target_url,
                        "photos_count": len(photos),
                        "preview_photo": photos[0] if photos else None
                    }
                elif resp.status_code == 404:
                    return {
                        "plate": normalized,
                        "url": target_url,
                        "photos_count": 0,
                        "preview_photo": None
                    }
        except Exception:
            pass

        return {
            "plate": normalized,
            "url": target_url,
            "photos_count": 0,
            "preview_photo": None
        }
