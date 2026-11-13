import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, Union


class Settings(BaseSettings):
    TG_BOT_TOKEN: str = ""
    TG_CHAT_ID: Optional[int] = None

    CHECK_INTERVAL_SECONDS: int = 60
    JITTER_SECONDS: int = 15

    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8000

    DATABASE_URL: str = "sqlite+aiosqlite:///autohunter.db"

    @field_validator("TG_CHAT_ID", mode="before")
    def parse_empty_chat_id(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        return int(v)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
