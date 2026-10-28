@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0tools\Scan-WithDefender.ps1"
pause
