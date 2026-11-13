import json
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, desc

from config import settings
from database.models import Base, SearchTask, CarListing, PriceHistory

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_active_tasks() -> List[SearchTask]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SearchTask).where(SearchTask.is_active == True)
        )
        return list(result.scalars().all())


async def get_all_tasks() -> List[SearchTask]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SearchTask).order_by(desc(SearchTask.id))
        )
        return list(result.scalars().all())


async def create_task(data: dict) -> SearchTask:
    async with AsyncSessionLocal() as session:
        task = SearchTask(
            name=data.get("name", "Поиск"),
            platform=data.get("platform", "all"),
            brand=data.get("brand", "").strip(),
            model=data.get("model", "").strip(),
            exclude_brands_models=data.get("exclude_brands_models", "").strip(),
            year_min=int(data["year_min"]) if data.get("year_min") else None,
            year_max=int(data["year_max"]) if data.get("year_max") else None,
            price_min=int(data["price_min"]) if data.get("price_min") else None,
            price_max=int(data["price_max"]) if data.get("price_max") else None,
            mileage_max=int(data["mileage_max"]) if data.get("mileage_max") else None,
            owners_max=int(data["owners_max"]) if data.get("owners_max") else None,
            pts_type=data.get("pts_type", "any"),
            transmission=data.get("transmission", "any"),
            drive_type=data.get("drive_type", "any"),
            exclude_dealers=bool(data.get("exclude_dealers", True)),
            exclude_damaged=bool(data.get("exclude_damaged", True)),
            stop_words=data.get("stop_words", ""),
            is_active=True
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def toggle_task(task_id: int) -> Optional[bool]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SearchTask).where(SearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            task.is_active = not task.is_active
            await session.commit()
            return task.is_active
        return None


async def delete_task(task_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SearchTask).where(SearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            await session.delete(task)
            await session.commit()
            return True
        return False


async def save_or_update_car(data: dict) -> Tuple[CarListing, bool, bool, Optional[int]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CarListing).where(CarListing.external_id == data["external_id"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            car = CarListing(
                external_id=data["external_id"],
                platform=data["platform"],
                url=data["url"],
                title=data["title"],
                brand=data.get("brand", ""),
                model=data.get("model", ""),
                year=data.get("year"),
                price=int(data.get("price", 0)),
                mileage=data.get("mileage"),
                owners_count=data.get("owners_count"),
                pts_type=data.get("pts_type", ""),
                transmission=data.get("transmission", ""),
                drive_type=data.get("drive_type", ""),
                seller_name=data.get("seller_name", ""),
                is_dealer=bool(data.get("is_dealer", False)),
                city=data.get("city", ""),
                vin=data.get("vin"),
                license_plate=data.get("license_plate"),
                photo_url=data.get("photo_url", ""),
                photos_json=json.dumps(data.get("photos", [])),
                description=data.get("description", ""),
                nomerogram_url=data.get("nomerogram_url"),
                nomerogram_photos_count=data.get("nomerogram_photos_count", 0),
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                is_notified=False
            )
            session.add(car)
            await session.commit()
            await session.refresh(car)
            return car, True, False, None
        else:
            price_changed = False
            old_price = None
            new_price = int(data.get("price", 0))

            if new_price > 0 and existing.price != new_price:
                price_changed = True
                old_price = existing.price
                hist = PriceHistory(
                    car_id=existing.id,
                    old_price=existing.price,
                    new_price=new_price,
                    recorded_at=datetime.utcnow()
                )
                session.add(hist)
                existing.price = new_price

            existing.last_seen_at = datetime.utcnow()
            if data.get("nomerogram_url"):
                existing.nomerogram_url = data["nomerogram_url"]
                existing.nomerogram_photos_count = data.get("nomerogram_photos_count", 0)

            await session.commit()
            await session.refresh(existing)
            return existing, False, price_changed, old_price


async def mark_car_notified(car_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(CarListing).where(CarListing.id == car_id).values(is_notified=True)
        )
        await session.commit()


async def get_recent_cars(limit: int = 50) -> List[CarListing]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CarListing).order_by(desc(CarListing.first_seen_at)).limit(limit)
        )
        return list(result.scalars().all())
