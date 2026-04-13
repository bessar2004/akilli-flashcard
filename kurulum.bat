@echo off
echo Kurulum basliyor...

python --version
IF %ERRORLEVEL% NEQ 0 (
    echo Python bulunamadi! Lutfen Python yukle.
    pause
    exit
)

echo Sanal ortam olusturuluyor...
python -m venv .venv

call .venv\Scripts\activate

echo Pip guncelleniyor...
python -m pip install --upgrade pip

echo Paketler yukleniyor...
pip install -r requirements.txt

echo Kurulum tamamlandi!
pause