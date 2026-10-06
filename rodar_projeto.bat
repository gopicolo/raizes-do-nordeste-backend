@echo off
set PYTHONPATH=.
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
alembic upgrade head
python scripts\seed.py
start "Raizes API" cmd /k "set PYTHONPATH=.&& uvicorn app.main:app --reload"
echo Swagger: http://127.0.0.1:8000/docs
