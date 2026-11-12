@echo off
rem ============================================================================
rem  Poacher Guard - install the sensor node program on an ESP32 (one click).
rem  Plug the ESP32 in by USB, then double-click this file. Needs internet.
rem  Downloads Espressif's esptool and the latest node program from GitHub,
rem  finds the ESP32, writes it, and checks the node starts. No Python needed.
rem ============================================================================
title Poacher Guard - install the ESP32 node
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(Get-Content -LiteralPath '%~f0' -Raw) -split ('#PS'+'_START'); & ([scriptblock]::Create($s[1]))"
set ERR=%ERRORLEVEL%
echo.
pause
exit /b %ERR%
#PS_START
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dir = Join-Path $env:LOCALAPPDATA 'PoacherGuardFlasher'
New-Item -ItemType Directory -Force $dir | Out-Null
function Step($m) { Write-Host ''; Write-Host "==> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host ''; Write-Host "FAILED: $m" -ForegroundColor Red; exit 1 }

# 1. esptool (Espressif's official flashing tool, Windows build)
$exe = Get-ChildItem $dir -Recurse -Filter 'esptool.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $exe) {
    Step 'Downloading esptool, the ESP32 flashing tool (about 10 MB, first time only)'
    try {
        $rel = Invoke-RestMethod 'https://api.github.com/repos/espressif/esptool/releases/latest' -Headers @{ 'User-Agent' = 'poacher-guard-flasher' }
        $asset = $rel.assets | Where-Object { $_.name -match 'win' -and $_.name -match '64' -and $_.name -like '*.zip' } | Select-Object -First 1
        if (-not $asset) { Fail 'could not find the Windows download of esptool.' }
        $zip = Join-Path $dir 'esptool.zip'
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
        Expand-Archive $zip -DestinationPath $dir -Force
    } catch { Fail "could not download esptool ($($_.Exception.Message)). Check the internet connection." }
    $exe = Get-ChildItem $dir -Recurse -Filter 'esptool.exe' | Select-Object -First 1
    if (-not $exe) { Fail 'esptool.exe not found after download.' }
}
Write-Host "esptool: $($exe.FullName)"

# 2. the node program (built automatically on GitHub from firmware/flame_gsm_node)
Step 'Downloading the latest Poacher Guard node program (4 MB)'
$fw = Join-Path $dir 'flame_gsm_node.ino.merged.bin'
try { Invoke-WebRequest 'https://raw.githubusercontent.com/awesomeddiey/poacher-guard/main/firmware/build/flame_gsm_node.ino.merged.bin' -OutFile $fw -UseBasicParsing }
catch { if (-not (Test-Path $fw)) { Fail "could not download the node program ($($_.Exception.Message))." } else { Write-Host 'Offline: using the copy downloaded last time.' } }
if ((Get-Item $fw).Length -lt 1000000) { Fail 'the downloaded node program is incomplete. Try again.' }

# 3. find the ESP32's COM port
Step 'Looking for the ESP32 (plug it in with a USB DATA cable)'
$port = $null
for ($try = 0; $try -lt 10 -and -not $port; $try++) {
    $all = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match '\(COM\d+\)' })
    $esp = @($all | Where-Object { $_.Name -match 'CP210|CH340|CH341|CH910|CH343|CH9102|USB Serial|USB-SERIAL|FTDI|USB JTAG|UART' })
    if ($esp.Count -eq 1) { $port = [regex]::Match($esp[0].Name, 'COM\d+').Value }
    elseif ($esp.Count -gt 1) {
        $esp | ForEach-Object { Write-Host "   $($_.Name)" }
        $port = Read-Host 'Several boards found. Type the COM port of the ESP32 (e.g. COM5)'
    }
    if (-not $port) { Start-Sleep 3 }
}
if (-not $port) {
    if ($all.Count) { Write-Host 'Ports seen:'; $all | ForEach-Object { Write-Host "   $($_.Name)" } }
    Fail ('No ESP32 found. Use a USB DATA cable (charge-only cables do not work) and install the driver for the chip next to ' +
          'its USB socket: CP2102 -> search "Silicon Labs CP210x VCP driver", CH340 -> search "WCH CH341SER". Then run this again.')
}
Write-Host "ESP32 on $port"

# 4. write it (if it waits at Connecting, hold the BOOT button)
Step "Writing the node program to $port (about 1 minute; if it waits at 'Connecting...', hold the BOOT button on the ESP32)"
& $exe.FullName --chip esp32 --port $port --baud 460800 write_flash -z 0x0 $fw
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Retrying at a slower speed...' -ForegroundColor Yellow
    & $exe.FullName --chip esp32 --port $port --baud 115200 write_flash -z 0x0 $fw
    if ($LASTEXITCODE -ne 0) { Fail 'writing failed. Close the Arduino IDE / Serial Monitor, hold the BOOT button while it connects, try another cable or USB port.' }
}

# 5. check the node starts
Step 'Checking that the node starts'
$log = ''
try {
    $sp = New-Object System.IO.Ports.SerialPort $port, 115200
    $sp.DtrEnable = $false; $sp.RtsEnable = $false; $sp.ReadTimeout = 500
    $sp.Open()
    $sp.RtsEnable = $true; Start-Sleep -Milliseconds 150; $sp.RtsEnable = $false      # press EN (reset)
    $end = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $end -and $log -notmatch 'advertising as') { try { $log += $sp.ReadExisting() } catch {}; Start-Sleep -Milliseconds 200 }
    $sp.Close()
} catch { Write-Host "Could not read the node's start-up messages ($($_.Exception.Message))." }
$lines = ($log -split "`r?`n") | Where-Object { $_ -match 'POACHER|\[CFG\]|\[BT\]|\[GSM\] AT\+CPIN|Brownout|panic|invalid header' }
$lines | Select-Object -First 8 | ForEach-Object { Write-Host "   $_" }
if ($log -match 'advertising as') {
    Write-Host ''
    Write-Host 'SUCCESS: the node program is installed and running.' -ForegroundColor Green
} elseif ($log -match 'Brownout') {
    Fail 'the board resets from low power (brownout). Use a better USB cable or port; power the GSM module from its own supply.'
} else {
    Write-Host ''
    Write-Host 'Written, but the start-up message was not seen. Press the EN button on the ESP32; if the dashboard later shows the node connected, all is well.' -ForegroundColor Yellow
}
Write-Host ''
Write-Host 'Next: unplug the ESP32 and power it normally. In the Poacher Guard dashboard type the phone number (e.g. 0772109787), press Save, then Send test SMS.'
exit 0
