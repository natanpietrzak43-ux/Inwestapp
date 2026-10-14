@echo off
setlocal
cd /d "%~dp0"
echo Inwestapp v1.2
echo Pozostaw to okno otwarte podczas korzystania z aplikacji.
echo Adres w przegladarce: http://127.0.0.1:8000
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 server.py --open-browser
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Zainstaluj Python 3.10 lub nowszy z python.org i zaznacz Add Python to PATH.
    ) else (
        python server.py --open-browser
    )
)
echo.
pause
