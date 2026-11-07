@echo off
rem Poacher Guard - download and install on a new computer. This is the only file you need to send someone.
rem It downloads the project from GitHub into %USERPROFILE%\poacher-guard and runs INSTALL.bat.
title Poacher Guard - download and install
setlocal
set "DEST=%USERPROFILE%\poacher-guard"
if exist "%DEST%\INSTALL.bat" goto install
echo Downloading Poacher Guard (about 80 MB)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol='Tls12'; $z=Join-Path $env:TEMP 'poacher-guard.zip'; $t=Join-Path $env:TEMP 'poacher-guard-unzip';" ^
  "try { Invoke-WebRequest 'https://github.com/awesomeddiey/poacher-guard/archive/refs/heads/main.zip' -OutFile $z -UseBasicParsing } catch { Write-Host 'Download failed:' $_.Exception.Message; exit 1 };" ^
  "if (Test-Path $t) { Remove-Item $t -Recurse -Force }; Expand-Archive $z $t -Force;" ^
  "Move-Item (Get-ChildItem $t -Directory | Select-Object -First 1).FullName '%DEST%'"
if not exist "%DEST%\INSTALL.bat" (
  echo.
  echo Could not download the project. Check the internet connection. If the GitHub repository is private,
  echo ask its owner for the project folder instead and double-click INSTALL.bat inside it.
  pause
  exit /b 1
)
:install
call "%DEST%\INSTALL.bat"
