# Poacher Guard - program the ESP32 flame + SMS node (run through UPLOAD-ESP32-NODE.bat).
#   * downloads arduino-cli into tools\arduino-cli and the ESP32 board package (once, about 300 MB)
#   * asks for Wi-Fi, phone number(s) and node name (remembered in tools\node-settings.json, which is not uploaded to GitHub)
#   * fills in this PC's address, finds the ESP32's COM port, compiles and uploads firmware\flame_gsm_node
$ErrorActionPreference = 'Continue'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Say($msg) { Write-Host ''; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host ''; Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }
function AskDefault($q, $def) { $a = Read-Host "$q [$def]"; if ($a -eq '') { return $def } else { return $a } }

Write-Host '=================================================='
Write-Host '  POACHER GUARD - program the ESP32 node'
Write-Host '=================================================='

# ---- 1. arduino-cli + ESP32 boards ---------------------------------------------
$cliDir = Join-Path $Root 'tools\arduino-cli'
$cli = Join-Path $cliDir 'arduino-cli.exe'
if (-not (Test-Path $cli)) {
    Say 'Downloading arduino-cli'
    New-Item -ItemType Directory -Force $cliDir | Out-Null
    $zip = Join-Path $env:TEMP 'arduino-cli.zip'
    try { Invoke-WebRequest 'https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip' -OutFile $zip -UseBasicParsing }
    catch { Fail "could not download arduino-cli ($($_.Exception.Message))" }
    Expand-Archive $zip -DestinationPath $cliDir -Force
    if (-not (Test-Path $cli)) { Fail 'arduino-cli.exe not found after download' }
}
$url = 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
$cores = (& $cli core list --additional-urls $url) -join "`n"
if ($cores -notmatch 'esp32:esp32') {
    Say 'Installing the ESP32 board package (first time only, about 10 minutes)'
    & $cli core update-index --additional-urls $url
    & $cli core install esp32:esp32 --additional-urls $url
    if ($LASTEXITCODE -ne 0) { Fail 'could not install the ESP32 board package. Check the internet connection and try again.' }
}

# ---- 2. settings ---------------------------------------------------------------
Say 'Node settings (press Enter to keep the value in brackets)'
$setFile = Join-Path $PSScriptRoot 'node-settings.json'
$s = @{ ssid = ''; password = ''; phones = ''; node = 'SIM8008' }
if (Test-Path $setFile) { $j = Get-Content $setFile -Raw | ConvertFrom-Json; foreach ($k in 'ssid', 'password', 'phones', 'node') { if ($j.$k) { $s[$k] = $j.$k } } }
if (-not $s.ssid) {
    $line = (netsh wlan show interfaces) | Select-String '^\s*SSID\s*:' | Select-Object -First 1
    if ($line) { $s.ssid = ($line.ToString() -split ':', 2)[1].Trim() }
}
$s.ssid = AskDefault 'Wi-Fi name (the same Wi-Fi as this PC)' $s.ssid
$pw = Read-Host "Wi-Fi password$(if ($s.password) { ' [keep saved password]' })"
if ($pw -ne '') { $s.password = $pw }
$s.phones = AskDefault 'Phone number(s) to text, comma separated (e.g. 0772109787)' $s.phones
$s.node = AskDefault 'Node name shown in the texts' $s.node
if (-not $s.ssid -or -not $s.phones) { Fail 'Wi-Fi name and at least one phone number are needed.' }
$s | ConvertTo-Json | Set-Content $setFile -Encoding ASCII

$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi' -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
if (-not $ip) { $ip = AskDefault 'Could not read this PC''s Wi-Fi address. Type it' '192.168.1.100' }
Write-Host "This PC (Poacher Guard server): http://${ip}:8000"

function CStr($v) { return '"' + ($v -replace '\\', '\\' -replace '"', '\"') + '"' }
function SetLine($code, $pattern, $line) { return ($code -replace $pattern, $line.Replace('$', '$$')) }     # $ in a password stays literal
$phones = @()
foreach ($p in ($s.phones -split ',')) {
    $p = ($p -replace '[^\d+]', '')
    if ($p -match '^0\d{9}$') { $p = '+263' + $p.Substring(1) }      # Zimbabwe local -> international
    if ($p) { $phones += (CStr $p) }
}

# ---- 3. build a copy of the sketch with these settings ----------------------------
$src = Join-Path $Root 'firmware\flame_gsm_node\flame_gsm_node.ino'
$build = Join-Path $env:TEMP 'poacher_guard_build\flame_gsm_node'
New-Item -ItemType Directory -Force $build | Out-Null
$code = Get-Content $src -Raw
$code = SetLine $code '(?m)^const char\* WIFI_SSID = .*$' ('const char* WIFI_SSID = ' + (CStr $s.ssid) + ';')
$code = SetLine $code '(?m)^const char\* WIFI_PASS = .*$' ('const char* WIFI_PASS = ' + (CStr $s.password) + ';')
$code = SetLine $code '(?m)^const char\* SERVER    = .*$' ('const char* SERVER    = ' + (CStr "http://${ip}:8000") + ';')
$code = SetLine $code '(?m)^const char\* NODE_ID   = .*$' ('const char* NODE_ID   = ' + (CStr $s.node) + ';')
$code = SetLine $code '(?m)^const char\* PHONES\[\] = .*$' ('const char* PHONES[] = {' + ($phones -join ', ') + '};')
Set-Content (Join-Path $build 'flame_gsm_node.ino') $code -Encoding ASCII

# ---- 4. find the ESP32 ---------------------------------------------------------------
Say 'Looking for the ESP32 (plug it in by USB now)'
$port = $null
for ($try = 0; $try -lt 15 -and -not $port; $try++) {
    $ports = @()
    try {
        $list = (& $cli board list --format json) -join "`n" | ConvertFrom-Json
        $items = if ($list.detected_ports) { $list.detected_ports } else { $list }
        foreach ($d in $items) {
            $p = $d.port
            if ($p -and $p.protocol -eq 'serial' -and $p.address -ne 'COM1') {
                $vid = "$($p.properties.vid)".ToLower()
                $ports += [pscustomobject]@{ addr = $p.address; esp = ($vid -match '10c4|1a86|303a|0403') }
            }
        }
    } catch {}
    $esp = @($ports | Where-Object { $_.esp })
    if ($esp.Count -eq 1) { $port = $esp[0].addr }
    elseif ($ports.Count -eq 1) { $port = $ports[0].addr }
    elseif ($ports.Count -gt 1) { $port = AskDefault ("Several ports found: " + (($ports | ForEach-Object { $_.addr }) -join ', ') + '. Which one is the ESP32?') $ports[0].addr }
    if (-not $port) { Start-Sleep 2 }
}
if (-not $port) {
    Fail ('no ESP32 found. Use a USB DATA cable (not charge-only) and install the USB driver for the chip printed near ' +
          'the USB socket: CP2102 -> silabs.com "CP210x VCP driver", CH340 -> wch-ic.com "CH341SER". Then run this again.')
}
Write-Host "ESP32 on $port"

# ---- 5. compile + upload ----------------------------------------------------------------
Say 'Compiling'
& $cli compile --fqbn esp32:esp32:esp32 $build
if ($LASTEXITCODE -ne 0) { Fail 'compile error (shown above). Send the red lines to whoever maintains the project.' }
Say "Uploading to $port (if it stays on 'Connecting...', hold the BOOT button on the ESP32)"
& $cli upload -p $port --fqbn esp32:esp32:esp32 $build
if ($LASTEXITCODE -ne 0) { Fail 'upload failed. Close the Arduino IDE / Serial Monitor if open, hold BOOT while it connects, and try again.' }
Write-Host ''
Write-Host "Done. The node '$($s.node)' texts $($phones -join ', ') and reports to http://${ip}:8000" -ForegroundColor Green
Write-Host 'Keep Poacher Guard running on this PC so poacher alerts reach the node.'
$m = Read-Host 'Open the serial monitor to watch the node start (GSM, Wi-Fi, flame)? [Y/n]'
if ($m -eq '' -or $m -match '^[Yy]') { Write-Host 'Press Ctrl+C to stop watching.'; & $cli monitor -p $port -c baudrate=115200 }
