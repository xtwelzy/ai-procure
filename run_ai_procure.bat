@echo off
title AI-Procure Runner

echo ===============================
echo   Запуск проекта AI-Procure
echo ===============================

echo Активируем виртуальное окружение...
call venv\Scripts\activate

echo Запуск backend (FastAPI)...
start cmd /k "uvicorn backend.main:app --reload"

echo Запуск UI (Streamlit)...
start cmd /k "streamlit run ui/app.py"

echo -------------------------------
echo Backend:   http://127.0.0.1:8000
echo UI:        http://localhost:8501
echo -------------------------------

pause
