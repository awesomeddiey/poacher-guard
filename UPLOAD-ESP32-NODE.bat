@echo off
rem Poacher Guard - program the ESP32 flame + SMS node. Plug the ESP32 in by USB, then double-click this file.
title Poacher Guard - program the ESP32 node
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\upload_node.ps1"
echo.
pause
