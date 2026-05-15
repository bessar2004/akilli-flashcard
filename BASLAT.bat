@echo off
title Smart Flashcard - Baslatiliyor

echo ============================
echo Ortam kontrol ediliyor...
echo ============================

IF NOT EXIST .venv\Scripts\python.exe (
    echo .venv bulunamadi veya eksik, kurulum baslatiliyor...
    call kurulum.bat
)

.venv\Scripts\python.exe --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo .venv bozuk gorunuyor, yeniden kuruluyor...
    rmdir /s /q .venv
    call kurulum.bat
)

echo .
echo Ortam aktif ediliyor...
call .venv\Scripts\activate.bat

echo .
echo Backend baslatiliyor...
cd backend
start http://localhost:8000
uvicorn main:app --reload --port 8000

pause
