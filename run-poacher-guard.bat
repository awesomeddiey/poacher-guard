@echo off
setlocal
cd /d "%~dp0"
title Poacher Guard
echo ==================================================
echo   POACHER GUARD  -  starting
echo ==================================================

rem ---- 1. First run on this PC: install everything (Python, packages, shortcuts) ----
if not exist ".venv\Scripts\python.exe" (
  echo First run: installing. This needs internet and takes about 10 minutes...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" -Unattended -NoStart
  if not exist ".venv\Scripts\python.exe" goto :fail
)

rem ---- 2. Update to the newest version from GitHub (skipped quietly when offline) ----
if exist "tools\update.py" ".venv\Scripts\python.exe" "tools\update.py" --skip run-poacher-guard.bat

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
