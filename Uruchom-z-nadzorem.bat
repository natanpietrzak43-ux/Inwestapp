@echo off
setlocal
cd /d "%~dp0"
py -3 launch.py --check-installation
if errorlevel 1 (
    pause
    exit /b 2
)
echo Pozostaw oba okna otwarte. Komputer nie moze przejsc w uspienie.
echo Watchdog wykrywa awarie, a nadzorca restartuje serwer po bledzie.
start "Inwestapp Watchdog" py -3 tools\watchdog.py
py -3 tools\run_service.py --open-browser
pause
