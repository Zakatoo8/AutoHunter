import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

from config import settings
from database.db_manager import (
    init_db, get_all_tasks, get_active_tasks, create_task, toggle_task,
    delete_task, get_recent_cars, save_or_update_car
)
from database.models import SearchTask, CarListing

app = FastAPI(title="AutoHunter Core")


class TaskCreateSchema(BaseModel):
    name: str
    platform: str = "all"
    brand: Optional[str] = ""
    model: Optional[str] = ""
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    mileage_max: Optional[int] = None
    owners_max: Optional[int] = None
    exclude_dealers: bool = True
    exclude_damaged: bool = True
    stop_words: Optional[str] = ""


class SettingsUpdateSchema(BaseModel):
    TG_BOT_TOKEN: str
    TG_CHAT_ID: Optional[int] = None


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def get_index():
    path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/tasks")
async def list_tasks():
    tasks = await get_all_tasks()
    return [t.to_dict() for t in tasks]


@app.post("/api/tasks")
async def add_task(payload: TaskCreateSchema):
    task = await create_task(payload.dict())
    return task.to_dict()


@app.post("/api/tasks/{task_id}/toggle")
async def toggle_task_state(task_id: int):
    new_state = await toggle_task(task_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"id": task_id, "is_active": new_state}


@app.delete("/api/tasks/{task_id}")
async def remove_task(task_id: int):
    success = await delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True}


@app.get("/api/cars")
async def list_cars():
    cars = await get_recent_cars(limit=50)
    return [c.to_dict() for c in cars]


@app.get("/api/stats")
async def get_stats():
    tasks = await get_all_tasks()
    cars = await get_recent_cars(limit=200)
    active_count = sum(1 for t in tasks if t.is_active)
    return {
        "total_tasks": len(tasks),
        "active_tasks": active_count,
        "total_cars": len(cars)
    }


@app.get("/api/settings")
async def get_app_settings():
    return {
        "TG_BOT_TOKEN": settings.TG_BOT_TOKEN,
        "TG_CHAT_ID": settings.TG_CHAT_ID
    }


@app.post("/api/settings")
async def update_app_settings(payload: SettingsUpdateSchema):
    settings.TG_BOT_TOKEN = payload.TG_BOT_TOKEN
    settings.TG_CHAT_ID = payload.TG_CHAT_ID
    # Save to .env
    with open(".env", "w", encoding="utf-8") as f:
        f.write(f"TG_BOT_TOKEN={settings.TG_BOT_TOKEN}\n")
        f.write(f"TG_CHAT_ID={settings.TG_CHAT_ID or ''}\n")
    return {"status": "ok"}
