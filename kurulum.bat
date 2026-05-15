@echo off
setlocal
echo Kurulum basliyor...

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python bulunamadi! Lutfen Python yukle.
    pause
    exit
)

IF EXIST .venv (
    echo Eski sanal ortam kaldiriliyor...
    rmdir /s /q .venv
)

echo Sanal ortam olusturuluyor...
python -m venv .venv

call .venv\Scripts\activate.bat

echo Pip guncelleniyor...
python -m pip install --upgrade pip

echo Paketler yukleniyor...
python -m pip install -r requirements.txt

echo Kurulum tamamlandi!
pause
