@echo off
setlocal
cd /d "%~dp0"
py -3 tools\configure_alerts.py
pause
