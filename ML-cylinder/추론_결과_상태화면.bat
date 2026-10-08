@echo off
chcp 65001 >nul
mode con cols=125 lines=34 >nul
cd /d "%~dp0"
python tools\local_inference_detail_demo.py
pause
