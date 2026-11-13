@echo off
chcp 65001 > nul
title AutoHunter - Car Monitoring Engine
echo ========================================================
echo           AutoHunter: Автоматический Чекер Машин
echo   Площадки: Drom.ru, Auto.ru, Avito (Playwright Stealth)
echo ========================================================
echo.
.\.venv\Scripts\python.exe main.py
pause
