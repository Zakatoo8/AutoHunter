import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper


class AutoRuScraper(BaseScraper):
    def __init__(self):
        super().__init__("autoru")

    async def fetch_recent_listings(self, brand: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        listings = []
        
        # Build URL: e.g. https://auto.ru/cars/{brand}/{model}/all/?sort=cr_date-desc
        if brand:
            clean_brand = brand.lower().replace(" ", "_").strip()
            if model:
                clean_model = model.lower().replace(" ", "_").strip()
                url = f"https://auto.ru/cars/{clean_brand}/{clean_model}/all/?sort=cr_date-desc"
            else:
                url = f"https://auto.ru/cars/{clean_brand}/all/?sort=cr_date-desc"
        else:
            url = "https://auto.ru/cars/all/?sort=cr_date-desc"

        session = await self.create_session()
        try:
            resp = await session.get(url)
            if resp.status_code != 200:
                return listings

            soup = BeautifulSoup(resp.text, "html.parser")
            sale_links = soup.find_all("a", href=re.compile(r"auto\.ru/cars/used/sale/"))

            seen_ids = set()
            for a in sale_links:
                href = a.get("href", "").split("?")[0]
                match = re.search(r"/sale/([^/]+)/([^/]+)/(\d+-[a-f0-9]+)/?", href)
                if not match:
                    continue
                
                car_brand_url = match.group(1).replace("_", " ").title()
                car_model_url = match.group(2).replace("_", " ").title()
                raw_id = match.group(3)
                ext_id = f"autoru_{raw_id}"

                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                # Card container
                parent = a
                for _ in range(5):
                    if parent.parent:
                        parent = parent.parent

                full_text = parent.get_text(separator=" | ", strip=True)

                # Extract title from link or container
                title = f"{car_brand_url} {car_model_url}"
                for line in full_text.split("|"):
                    line_s = line.strip()
                    if car_brand_url.lower() in line_s.lower():
                        title = line_s
                        break

                # Extract year
                year = None
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", full_text)
                if year_match:
                    year = int(year_match.group(1))

                # Extract price: e.g. "1 680 000 ₽"
                price = 0
                price_match = re.search(r"(\d[\d\s\xa0]+)\s*₽", full_text)
                if price_match:
                    price_digits = re.sub(r"[^\d]", "", price_match.group(1))
                    if price_digits:
                        price = int(price_digits)

                # Extract mileage: e.g. "74 000 км"
                mileage = None
                mileage_match = re.search(r"(\d[\d\s\xa0]+)\s*км", full_text)
                if mileage_match:
                    mileage_digits = re.sub(r"[^\d]", "", mileage_match.group(1))
                    if mileage_digits:
                        mileage = int(mileage_digits)

                # Extract photo
                img = parent.find("img")
                photo_url = ""
                if img:
                    raw_src = img.get("src") or img.get("data-src") or ""
                    if raw_src.startswith("//"):
                        photo_url = "https:" + raw_src
                    elif raw_src.startswith("http"):
                        photo_url = raw_src

                # Dealer detection
                is_dealer = False
                dealer_keywords = ["дилер", "автосалон", "рольф", "major", "автомир", "ключ авто", "официальный", "trade-in"]
                for kw in dealer_keywords:
                    if kw in full_text.lower():
                        is_dealer = True
                        break

                listings.append({
                    "external_id": ext_id,
                    "platform": "autoru",
                    "url": href,
                    "title": title,
                    "brand": car_brand_url,
                    "model": car_model_url,
                    "year": year,
                    "price": price,
                    "mileage": mileage,
                    "owners_count": None,
                    "seller_name": "Дилер" if is_dealer else "Собственник",
                    "is_dealer": is_dealer,
                    "city": "",
                    "vin": None,
                    "license_plate": None,
                    "photo_url": photo_url,
                    "photos": [photo_url] if photo_url else [],
                    "description": full_text[:400]
                })

            return listings
        except Exception as e:
            print(f"[AutoRuScraper] Error: {e}")
            return []
        finally:
            await session.close()
