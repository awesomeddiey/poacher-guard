@echo off
setlocal
cd /d "%~dp0"
title Poacher Guard
echo ==================================================
echo   POACHER GUARD  -  starting
echo ==================================================

rem ---- 1. Python present? ----
where py >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python is not installed. Install Python 3.11 or 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer. Then double-click this file again.
  goto :end
)

rem ---- 2. First run: create environment and install packages (needs internet, once) ----
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo First run: installing packages. This needs internet and takes about 5 to 10 minutes. Please wait...
  py -3 -m venv .venv || goto :fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
  echo Packages installed.
)

rem ---- 3. Quick check (shows cameras and microphones; never blocks the start) ----
echo.
".venv\Scripts\python.exe" check_setup.py

rem ---- 4. Open the dashboard as soon as the server answers ----
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){try{Invoke-WebRequest http://localhost:8000/api/status -UseBasicParsing -TimeoutSec 1|Out-Null;Start-Process 'http://localhost:8000';break}catch{Start-Sleep 1}}"

rem ---- 5. Run (leave this window open; close it or press Ctrl+C to stop) ----
echo.
echo Starting the detectors and dashboard. First start takes about 20 seconds.
echo Dashboard: http://localhost:8000      (other devices on the same Wi-Fi: use this PC's IP address)
echo.
".venv\Scripts\python.exe" run.py
goto :end

:fail
echo.
echo Setup failed. Check your internet connection and run this file again. The error is shown above.

:end
echo.
pause
