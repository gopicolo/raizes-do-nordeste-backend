@echo off
set PYTHONPATH=.
call .venv\Scripts\activate.bat
pytest -q
pause
