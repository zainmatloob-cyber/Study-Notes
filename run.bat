@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - open it and set GROQ_API_KEY, then run this again.
  notepad .env
  exit /b
)
start "" http://localhost:8000
uvicorn app.main:app --port 8000
