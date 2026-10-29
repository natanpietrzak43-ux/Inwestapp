@echo off
setlocal
cd /d "%~dp0"
py -3 tools\configure_coingecko.py
if errorlevel 1 echo Konfiguracja nie zostala potwierdzona.
pause
