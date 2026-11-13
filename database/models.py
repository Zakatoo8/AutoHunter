import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SearchTask(Base):
    __tablename__ = "search_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    platform = Column(String(50), default="all")  # 'all', 'drom', 'avito', 'autoru'
    
    brand = Column(String(100), default="")
    model = Column(String(100), default="")
    exclude_brands_models = Column(Text, default="")
    exclude_countries = Column(Text, default="")  # e.g. "china, russia"
    
    body_type = Column(String(50), default="any")  # "any", "sedan", "suv", "hatchback", "wagon", "coupe", "liftback"
    engine_type = Column(String(50), default="any")  # "any", "petrol", "diesel", "hybrid", "electro"
    engine_volume_min = Column(Float, nullable=True)
    engine_volume_max = Column(Float, nullable=True)
    
    year_min = Column(Integer, nullable=True)
    year_max = Column(Integer, nullable=True)
    
    price_min = Column(Integer, nullable=True)
    price_max = Column(Integer, nullable=True)
    
    mileage_max = Column(Integer, nullable=True)
    owners_max = Column(Integer, nullable=True)
    
    pts_type = Column(String(50), default="any")  # "any", "original", "electronic", "no_duplicate"
    transmission = Column(String(50), default="any")  # "any", "auto", "manual"
    drive_type = Column(String(50), default="any")  # "any", "4wd", "fwd", "rwd"
    steering_wheel = Column(String(50), default="any")  # "any", "left", "right"
    
    exclude_dealers = Column(Boolean, default=True)
    exclude_damaged = Column(Boolean, default=True)
    stop_words = Column(Text, default="")
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "brand": self.brand,
            "model": self.model,
            "exclude_brands_models": self.exclude_brands_models,
            "exclude_countries": self.exclude_countries,
            "body_type": self.body_type,
            "engine_type": self.engine_type,
            "engine_volume_min": self.engine_volume_min,
            "engine_volume_max": self.engine_volume_max,
            "year_min": self.year_min,
            "year_max": self.year_max,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "mileage_max": self.mileage_max,
            "owners_max": self.owners_max,
            "pts_type": self.pts_type,
            "transmission": self.transmission,
            "drive_type": self.drive_type,
            "steering_wheel": self.steering_wheel,
            "exclude_dealers": self.exclude_dealers,
            "exclude_damaged": self.exclude_damaged,
            "stop_words": self.stop_words,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""
        }


class CarListing(Base):
    __tablename__ = "car_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), unique=True, index=True, nullable=False)
    platform = Column(String(50), nullable=False)
    url = Column(String(500), nullable=False)
    
    title = Column(String(255), nullable=False)
    brand = Column(String(100), default="")
    model = Column(String(100), default="")
    year = Column(Integer, nullable=True)
    
    price = Column(Integer, nullable=False)
    mileage = Column(Integer, nullable=True)
    owners_count = Column(Integer, nullable=True)
    
    body_type = Column(String(50), default="")
    engine_type = Column(String(50), default="")
    engine_volume = Column(Float, nullable=True)
    
    pts_type = Column(String(50), default="")
    transmission = Column(String(50), default="")
    drive_type = Column(String(50), default="")
    steering_wheel = Column(String(50), default="")
    
    seller_name = Column(String(150), default="")
    is_dealer = Column(Boolean, default=False)
    city = Column(String(100), default="")
    
    vin = Column(String(50), nullable=True)
    license_plate = Column(String(20), nullable=True)
    
    photo_url = Column(String(500), default="")
    photos_json = Column(Text, default="[]")
    description = Column(Text, default="")
    
    nomerogram_url = Column(String(500), nullable=True)
    nomerogram_photos_count = Column(Integer, default=0)
    
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_notified = Column(Boolean, default=False)

    price_history = relationship("PriceHistory", back_populates="car", cascade="all, delete-orphan")

    def to_dict(self):
        photos = []
        if self.photos_json:
            try:
                photos = json.loads(self.photos_json)
            except Exception:
                photos = []
        return {
            "id": self.id,
            "external_id": self.external_id,
            "platform": self.platform,
            "url": self.url,
            "title": self.title,
            "brand": self.brand,
            "model": self.model,
            "year": self.year,
            "price": self.price,
            "mileage": self.mileage,
            "owners_count": self.owners_count,
            "body_type": self.body_type,
            "engine_type": self.engine_type,
            "engine_volume": self.engine_volume,
            "pts_type": self.pts_type,
            "transmission": self.transmission,
            "drive_type": self.drive_type,
            "steering_wheel": self.steering_wheel,
            "seller_name": self.seller_name,
            "is_dealer": self.is_dealer,
            "city": self.city,
            "vin": self.vin,
            "license_plate": self.license_plate,
            "photo_url": self.photo_url,
            "photos": photos,
            "description": self.description,
            "nomerogram_url": self.nomerogram_url,
            "nomerogram_photos_count": self.nomerogram_photos_count,
            "first_seen_at": self.first_seen_at.strftime("%d.%m %H:%M") if self.first_seen_at else "",
            "is_notified": self.is_notified
        }


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    car_id = Column(Integer, ForeignKey("car_listings.id"), nullable=False)
    old_price = Column(Integer, nullable=False)
    new_price = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    car = relationship("CarListing", back_populates="price_history")
