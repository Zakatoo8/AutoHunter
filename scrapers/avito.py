import re
import urllib.parse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper


class AvitoScraper(BaseScraper):
    def __init__(self):
        super().__init__("avito")

    async def fetch_recent_listings(self, brand: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        listings = []
        
        # Build Avito search URL
        # Format: https://www.avito.ru/all/avtomobili?s=104&q=toyota+camry
        query_parts = []
        if brand:
            query_parts.append(brand)
        if model:
            query_parts.append(model)

        if query_parts:
            q = urllib.parse.quote_plus(" ".join(query_parts))
            url = f"https://www.avito.ru/all/avtomobili?s=104&q={q}"
        else:
            url = "https://www.avito.ru/all/avtomobili?s=104"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800}
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(2500)
                content = await page.content()
                await browser.close()

            soup = BeautifulSoup(content, "html.parser")
            items = soup.find_all("div", attrs={"data-marker": "item"})

            seen_ids = set()
            for it in items:
                title_tag = it.find("a", attrs={"data-marker": "item-title"})
                if not title_tag:
                    continue

                raw_href = title_tag.get("href", "")
                clean_href = raw_href.split("?")[0]
                if not clean_href.startswith("http"):
                    clean_href = "https://www.avito.ru" + clean_href

                id_match = re.search(r"_(\d+)$", clean_href)
                if not id_match:
                    continue

                raw_id = id_match.group(1)
                ext_id = f"avito_{raw_id}"
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                title_text = title_tag.get_text(strip=True)

                # Price
                price = 0
                price_tag = it.find("meta", attrs={"itemprop": "price"})
                if price_tag and price_tag.get("content"):
                    try:
                        price = int(price_tag["content"])
                    except ValueError:
                        price = 0

                # Year
                year = None
                year_match = re.search(r",\s*(19\d{2}|20\d{2})", title_text)
                if year_match:
                    year = int(year_match.group(1))

                # Image
                img_tag = it.find("img")
                photo_url = ""
                if img_tag:
                    photo_url = img_tag.get("src") or img_tag.get("data-src") or ""

                full_text = it.get_text(separator=" | ", strip=True)

                # Mileage
                mileage = None
                mileage_match = re.search(r"(\d[\d\s\xa0]+)\s*км", full_text)
                if mileage_match:
                    digits = re.sub(r"[^\d]", "", mileage_match.group(1))
                    if digits:
                        mileage = int(digits)

                # Dealer detection
                is_dealer = False
                dealer_keywords = ["автодилер", "дилер", "автосалон", "компания", "официальный"]
                for kw in dealer_keywords:
                    if kw in full_text.lower():
                        is_dealer = True
                        break

                # City extraction
                geo_tag = it.find("div", attrs={"data-marker": "item-line"})
                city = geo_tag.get_text(strip=True) if geo_tag else ""

                listings.append({
                    "external_id": ext_id,
                    "platform": "avito",
                    "url": clean_href,
                    "title": title_text,
                    "brand": brand or "",
                    "model": model or "",
                    "year": year,
                    "price": price,
                    "mileage": mileage,
                    "owners_count": None,
                    "seller_name": "Дилер / Компания" if is_dealer else "Собственник",
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
            print(f"[AvitoScraper] Error: {e}")
            return []
