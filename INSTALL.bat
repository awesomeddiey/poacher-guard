@echo off
rem Poacher Guard - one-click install. Double-click this file.
rem Installs Python, the packages and desktop shortcuts, then starts Poacher Guard. Needs internet once.
title Poacher Guard - install
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" %*
echo.
pause
