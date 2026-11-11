@echo off
rem Poacher Guard - write the sensor node program to an ESP32 plugged in by USB (about 30 seconds).
rem The SMS numbers are set on the dashboard afterwards; nothing to type here.
title Poacher Guard - set up the ESP32 node
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install Poacher Guard first: double-click INSTALL.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "tools\flash_node.py"
echo.
pause
