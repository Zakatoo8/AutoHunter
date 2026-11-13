from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from curl_cffi.requests import AsyncSession


class BaseScraper(ABC):
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

    async def create_session(self) -> AsyncSession:
        return AsyncSession(
            impersonate="chrome120",
            headers=self.default_headers,
            timeout=20
        )

    @abstractmethod
    async def fetch_recent_listings(self, brand: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches the latest car listings for a specific brand/model or general feed.
        Returns a list of standardized dicts:
        {
            "external_id": str,
            "platform": str,
            "url": str,
            "title": str,
            "brand": str,
            "model": str,
            "year": int,
            "price": int,
            "mileage": int or None,
            "owners_count": int or None,
            "seller_name": str,
            "is_dealer": bool,
            "city": str,
            "vin": str or None,
            "license_plate": str or None,
            "photo_url": str,
            "photos": List[str],
            "description": str
        }
        """
        pass
