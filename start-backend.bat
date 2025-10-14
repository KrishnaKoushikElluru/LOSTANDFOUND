@echo off
echo Starting LostNFound Backend...

cd /d "C:\Users\koush\Downloads\lostnfound_ml"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start backend in background
start /B python -m uvicorn src.api:app --host 0.0.0.0 --port 8000

REM Wait for backend to start
timeout /t 5

REM Start tunnel with fixed subdomain
lt --port 8000 --subdomain lostnfound-permanent-api

pause
