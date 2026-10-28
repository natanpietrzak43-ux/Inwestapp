@echo off
setlocal
cd /d "%~dp0"
py -3 tools\security_check.py
if errorlevel 1 echo Kontrola nie zostala potwierdzona. Pobierz i rozpakuj ponownie caly ZIP.
pause
