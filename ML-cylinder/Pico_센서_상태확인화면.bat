@echo off
chcp 65001 >nul
mode con cols=105 lines=22 >nul
cd /d "%~dp0"
python tools\local_pico_sensor_demo.py
pause
