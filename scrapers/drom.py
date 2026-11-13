import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper


class DromScraper(BaseScraper):
    def __init__(self):
        super().__init__("drom")

    async def fetch_recent_listings(self, brand: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        listings = []
        
        # Build search URL
        # Drom URL format: https://auto.drom.ru/{brand}/{model}/?order=date or /all/?order=date
        url = "https://auto.drom.ru/all/?order=date"
        if brand:
            clean_brand = brand.lower().replace(" ", "_").strip()
            if model:
                clean_model = model.lower().replace(" ", "_").strip()
                url = f"https://auto.drom.ru/{clean_brand}/{clean_model}/?order=date"
            else:
                url = f"https://auto.drom.ru/{clean_brand}/?order=date"

        session = await self.create_session()
        try:
            resp = await session.get(url)
            if resp.status_code != 200:
                return listings

            resp.encoding = "windows-1251"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Find all car links excluding promotional widgets
            main_links = [
                a for a in soup.find_all("a", href=re.compile(r"drom\.ru/.+/\d+\.html"))
                if "widget" not in a.get("href", "") and a.get_text(strip=True)
            ]

            seen_ids = set()
            for a in main_links:
                href = a["href"].split("?")[0].split("#")[0]
                id_match = re.search(r"/(\d+)\.html", href)
                if not id_match:
                    continue
                ext_id = f"drom_{id_match.group(1)}"
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                title_text = a.get_text(strip=True)
                # Parse title like "Toyota Camry, 2015"
                year = None
                year_match = re.search(r",\s*(\d{4})", title_text)
                if year_match:
                    year = int(year_match.group(1))

                # Parse brand & model
                clean_title = re.sub(r",\s*\d{4}", "", title_text).strip()
                parts = clean_title.split(" ", 1)
                car_brand = parts[0] if len(parts) > 0 else ""
                car_model = parts[1] if len(parts) > 1 else ""

                # Card container
                parent = a
                for _ in range(3):
                    if parent.parent:
                        parent = parent.parent

                full_text = parent.get_text(separator=" | ", strip=True)
                
                # Extract price: e.g. "1 999 000 | ₽"
                price = 0
                price_match = re.search(r"(\d[\d\s\xa0]+)\s*\|\s*₽", full_text)
                if price_match:
                    price_digits = re.sub(r"[^\d]", "", price_match.group(1))
                    if price_digits:
                        price = int(price_digits)

                # Extract mileage: e.g. "118 000 км"
                mileage = None
                mileage_match = re.search(r"(\d[\d\s\xa0]+)\s*км", full_text)
                if mileage_match:
                    mileage_digits = re.sub(r"[^\d]", "", mileage_match.group(1))
                    if mileage_digits:
                        mileage = int(mileage_digits)
                elif "новый" in full_text.lower():
                    mileage = 0

                # Extract city: usually one of the segments after price/specs
                city = ""
                segments = [s.strip() for s in full_text.split("|") if s.strip()]
                for s in reversed(segments):
                    if "назад" in s or "₽" in s or "цена" in s or "км" in s:
                        continue
                    if len(s) > 2 and not any(ch.isdigit() for ch in s):
                        city = s
                        break

                # Extract image
                img_tag = parent.find("img")
                photo_url = ""
                if img_tag:
                    photo_url = img_tag.get("src") or img_tag.get("data-src") or ""

                # Dealer detection heuristics
                is_dealer = False
                dealer_keywords = ["моторс", "дилер", "автосалон", "авторай", "автомобили с пробегом", "рольф", "major", "verra", "луна авто", "trade-in"]
                for kw in dealer_keywords:
                    if kw in full_text.lower():
                        is_dealer = True
                        break

                listings.append({
                    "external_id": ext_id,
                    "platform": "drom",
                    "url": href,
                    "title": title_text,
                    "brand": car_brand,
                    "model": car_model,
                    "year": year,
                    "price": price,
                    "mileage": mileage,
                    "owners_count": None,
                    "seller_name": "Дилер / Салон" if is_dealer else "Собственник",
                    "is_dealer": is_dealer,
                    "city": city,
                    "vin": None,
                    "license_plate": None,
                    "photo_url": photo_url,
                    "photos": [photo_url] if photo_url else [],
                    "description": full_text[:400]
                })

            return listings
        except Exception as e:
            print(f"[DromScraper] Error: {e}")
            return []
        finally:
            await session.close()
