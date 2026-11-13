import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, BigInteger
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
    
    year_min = Column(Integer, nullable=True)
    year_max = Column(Integer, nullable=True)
    
    price_min = Column(Integer, nullable=True)
    price_max = Column(Integer, nullable=True)
    
    mileage_max = Column(Integer, nullable=True)
    owners_max = Column(Integer, nullable=True)
    
    exclude_dealers = Column(Boolean, default=True)
    exclude_damaged = Column(Boolean, default=True)
    stop_words = Column(Text, default="")  # comma separated
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "brand": self.brand,
            "model": self.model,
            "year_min": self.year_min,
            "year_max": self.year_max,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "mileage_max": self.mileage_max,
            "owners_max": self.owners_max,
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
    platform = Column(String(50), nullable=False)  # 'drom', 'avito', 'autoru'
    url = Column(String(500), nullable=False)
    
    title = Column(String(255), nullable=False)
    brand = Column(String(100), default="")
    model = Column(String(100), default="")
    year = Column(Integer, nullable=True)
    
    price = Column(Integer, nullable=False)
    mileage = Column(Integer, nullable=True)
    owners_count = Column(Integer, nullable=True)
    
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
