@echo off
chcp 65001 > nul
echo ========================================================
echo               AutoHunter - Web Dashboard
echo ========================================================
echo Запуск локального сервера...
start http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m uvicorn web.app:app --host 127.0.0.1 --port 8000
pause
