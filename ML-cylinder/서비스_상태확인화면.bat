@echo off
chcp 65001 >nul
mode con cols=95 lines=22 >nul
cd /d "%~dp0"
python tools\local_service_status_demo.py
pause
