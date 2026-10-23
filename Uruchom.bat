@echo off
setlocal
cd /d "%~dp0"
echo Inwestapp v1.8.0
echo Pozostaw to okno otwarte podczas korzystania z aplikacji.
echo Domyslny adres w przegladarce: http://127.0.0.1:8000
echo.
if not exist launch.py (
    echo Brak launch.py. Rozpakuj CALY ZIP do nowego folderu.
    pause
    exit /b 2
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 launch.py %*
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Zainstaluj Python 3.10 lub nowszy z python.org i zaznacz Add Python to PATH.
    ) else (
        python launch.py %*
    )
)
echo.
pause
