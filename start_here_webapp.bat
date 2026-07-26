@echo off
setlocal
set "APP_DIR=%~dp0"

if not exist "%APP_DIR%main.py" (
    echo Nie znaleziono main.py w tym folderze.
    echo Uruchom ten skrypt z poziomu folderu wf_tracker.
    pause
    exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
    echo Nie znaleziono Python 3. Zainstaluj Python 3.10+ i uruchom ten skrypt ponownie.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if not exist ".venv" (
    echo Tworze wirtualne srodowisko...
    py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Uruchamiam webapp na http://localhost:8000 ...
echo Otworz ten adres w przegladarce. Zamknij to okno, zeby zatrzymac serwer.
echo.

start "" "http://localhost:8000"
python webapp.py

pause
