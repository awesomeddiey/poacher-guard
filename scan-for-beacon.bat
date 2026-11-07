@echo off
cd /d "%~dp0"
title Find my ranger beacon
if not exist ".venv\Scripts\python.exe" ( echo Run run-poacher-guard.bat once first to install. & pause & exit /b 1 )
".venv\Scripts\python.exe" check_setup.py --ble
pause
