import asyncio
import random
import logging
from typing import List, Dict, Any

from config import settings
from database.db_manager import (
    get_active_tasks, save_or_update_car, mark_car_notified
)
from filters.filter_engine import FilterEngine
from checkers.nomerogram import NomerogramChecker
from scrapers.drom import DromScraper
from scrapers.autoru import AutoRuScraper
from scrapers.avito import AvitoScraper
from bot.telegram_bot import send_car_notification

logger = logging.getLogger("HunterEngine")


class HunterEngine:
    def __init__(self):
        self.drom_scraper = DromScraper()
        self.autoru_scraper = AutoRuScraper()
        self.avito_scraper = AvitoScraper()
        self.is_running = False

    async def scan_for_task(self, task) -> List[Dict[str, Any]]:
        results = []
        platform = (task.platform or "all").lower()

        # Drom
        if platform in ["all", "drom"]:
            try:
                drom_items = await self.drom_scraper.fetch_recent_listings(
                    brand=task.brand, model=task.model
                )
                results.extend(drom_items)
            except Exception as e:
                logger.error(f"Error fetching Drom for task {task.name}: {e}")

        # Auto.ru
        if platform in ["all", "autoru"]:
            try:
                autoru_items = await self.autoru_scraper.fetch_recent_listings(
                    brand=task.brand, model=task.model
                )
                results.extend(autoru_items)
            except Exception as e:
                logger.error(f"Error fetching Auto.ru for task {task.name}: {e}")

        # Avito
        if platform in ["all", "avito"]:
            try:
                avito_items = await self.avito_scraper.fetch_recent_listings(
                    brand=task.brand, model=task.model
                )
                results.extend(avito_items)
            except Exception as e:
                logger.error(f"Error fetching Avito for task {task.name}: {e}")

        return results

    async def run_single_cycle(self):
        tasks = await get_active_tasks()
        if not tasks:
            logger.info("No active search tasks configured.")
            return

        logger.info(f"Starting hunter cycle for {len(tasks)} active tasks...")
        for task in tasks:
            raw_cars = await self.scan_for_task(task)
            logger.info(f"Scraped {len(raw_cars)} cars for task '{task.name}'")

            for car_data in raw_cars:
                is_match, reason = FilterEngine.matches_task(car_data, task)
                if not is_match:
                    continue

                # Check license plate on Nomerogram if plate exists
                if car_data.get("license_plate"):
                    nomer_info = await NomerogramChecker.check_plate(car_data["license_plate"])
                    if nomer_info:
                        car_data["nomerogram_url"] = nomer_info["url"]
                        car_data["nomerogram_photos_count"] = nomer_info["photos_count"]

                # Save or update in database
                car_obj, is_new, price_changed, old_price = await save_or_update_car(car_data)

                # Send Telegram alert
                if is_new:
                    logger.info(f"🔥 NEW MATCH: {car_obj.title} ({car_obj.price} RUB) -> Sending to TG")
                    await send_car_notification(car_obj.to_dict(), task_name=task.name, is_update=False)
                    await mark_car_notified(car_obj.id)
                elif price_changed:
                    logger.info(f"📉 PRICE CHANGE: {car_obj.title} ({old_price} -> {car_obj.price}) -> Sending to TG")
                    await send_car_notification(car_obj.to_dict(), task_name=task.name, is_update=True, old_price=old_price)

            # Polite pause between different tasks
            await asyncio.sleep(2)

    async def start(self):
        self.is_running = True
        logger.info("AutoHunter Background Engine STARTED.")
        while self.is_running:
            try:
                await self.run_single_cycle()
            except Exception as e:
                logger.error(f"Error in hunt cycle: {e}")

            # Sleep with jitter
            delay = settings.CHECK_INTERVAL_SECONDS + random.randint(3, settings.JITTER_SECONDS)
            logger.info(f"Waiting {delay}s until next hunt scan...")
            await asyncio.sleep(delay)

    def stop(self):
        self.is_running = False
