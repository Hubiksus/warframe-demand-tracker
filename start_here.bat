@echo off
setlocal
set "ROOT=%~dp0"
set "APP_DIR=%ROOT%wf_tracker"

if not exist "%APP_DIR%\main.py" (
    echo Nie znaleziono katalogu aplikacji.
    echo Rozpakuj ZIP do folderu i uruchom ten skrypt z poziomu folderu z projektem.
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
python main.py

pause
