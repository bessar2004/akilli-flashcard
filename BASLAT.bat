@echo off
title Smart Flashcard - Baslatiliyor

echo ============================
echo Ortam kontrol ediliyor...
echo ============================

IF NOT EXIST .venv (
    echo .venv bulunamadi, kurulum baslatiliyor...
    call kurulum.bat
)

echo .
echo Ortam aktif ediliyor...
call .venv\Scripts\activate

echo .
echo Backend baslatiliyor...
cd backend
start http://localhost:8000
uvicorn main:app --reload --port 8000

pause