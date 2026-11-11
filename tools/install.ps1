# Poacher Guard one-click installer for Windows 10/11 (run through INSTALL.bat).
#   * Python 3.12 (winget, or the python.org installer if winget is missing)
#   * Microsoft Visual C++ runtime (needed by PyTorch/OpenCV) if it is missing
#   * a private Python environment in .venv with every package from requirements.txt
#   * desktop shortcuts, an optional firewall rule for port 8000, then starts Poacher Guard
# Re-running it is safe: finished steps are skipped. A log is written to install.log.
param([switch]$Unattended, [switch]$NoStart)
if ($env:PG_UNATTENDED) { $Unattended = $true }     # automatic test runs (GitHub Actions)
if ($env:PG_NOSTART) { $NoStart = $true }

$ErrorActionPreference = 'Continue'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { Start-Transcript -Path (Join-Path $Root 'install.log') -Force | Out-Null } catch {}

function Say($msg) { Write-Host ''; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ''; Write-Host "INSTALL FAILED: $msg" -ForegroundColor Red
    Write-Host "The full log is in $Root\install.log"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
function Ask($question) {
    if ($Unattended) { return $true }
    $a = Read-Host "$question [Y/n]"
    return ($a -eq '' -or $a -match '^[Yy]')
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

# Returns the full path of a usable python.exe (3.10 to 3.14), preferring 3.12.
function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in '3.12', '3.11', '3.13', '3.10', '3.14') {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { $candidates += $exe.Trim() }
        }
    }
    foreach ($v in '312', '311', '313', '310', '314') {
        $p = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"
        if (Test-Path $p) { $candidates += $p }
        $p = Join-Path $env:ProgramFiles "Python$v\python.exe"
        if (Test-Path $p) { $candidates += $p }
    }
    if ($candidates.Count -gt 0) { return $candidates[0] }
    return $null
}

Write-Host '=================================================='
Write-Host '  POACHER GUARD - installer'
Write-Host "  Folder: $Root"
Write-Host '=================================================='

# ---- 1. Python ---------------------------------------------------------------
Say 'Checking Python'
$py = Find-Python
if (-not $py) {
    Say 'Installing Python 3.12 (about 25 MB)'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --scope user --silent --accept-source-agreements --accept-package-agreements
    }
    Refresh-Path
    $py = Find-Python
    if (-not $py) {
        $setup = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
        Write-Host 'Downloading Python from python.org ...'
        try { Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $setup -UseBasicParsing }
        catch { Fail "could not download Python ($($_.Exception.Message)). Check the internet connection." }
        Start-Process $setup -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1' -Wait
        Refresh-Path
        $py = Find-Python
    }
    if (-not $py) { Fail 'Python could not be installed. Install Python 3.12 from python.org (tick "Add python.exe to PATH") and run INSTALL.bat again.' }
}
Write-Host "Using $py"

# ---- 2. Visual C++ runtime ---------------------------------------------------
Say 'Checking the Microsoft Visual C++ runtime'
if (-not (Test-Path (Join-Path $env:WINDIR 'System32\vcruntime140_1.dll'))) {
    Write-Host 'Missing - installing it (Windows will ask for permission).'
    $vc = Join-Path $env:TEMP 'vc_redist.x64.exe'
    try {
        Invoke-WebRequest 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $vc -UseBasicParsing
        Start-Process $vc -ArgumentList '/install', '/quiet', '/norestart' -Verb RunAs -Wait
    } catch { Write-Host "Could not install it automatically: $($_.Exception.Message)" -ForegroundColor Yellow }
} else { Write-Host 'Present.' }

# ---- 3. Python packages ------------------------------------------------------
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Say 'Creating the Python environment (.venv)'
    & $py -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) { Fail 'could not create the Python environment.' }
}
Say 'Installing packages - about 5 to 10 minutes and 1 GB of downloads the first time'
& $venvPy -m pip install --upgrade pip --disable-pip-version-check
& $venvPy -m pip install -r (Join-Path $Root 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Fail 'package installation failed. Check the internet connection and run INSTALL.bat again.' }
Write-Host 'Packages installed.' -ForegroundColor Green

# ---- 4. Hardware check -------------------------------------------------------
Say 'Checking camera, microphone and model files'
& $venvPy (Join-Path $Root 'check_setup.py')

# ---- 5. Desktop shortcuts ----------------------------------------------------
Say 'Creating desktop shortcuts'
try {
    $desk = [Environment]::GetFolderPath('Desktop')
    $sh = New-Object -ComObject WScript.Shell
    $links = @(
        @('Poacher Guard.lnk', 'run-poacher-guard.bat', 'Start the detectors and the dashboard', 'imageres.dll,101'),
        @('Poacher Guard - upload ESP32 node.lnk', 'UPLOAD-ESP32-NODE.bat', 'Program the ESP32 flame + SMS node', 'imageres.dll,109')
    )
    foreach ($l in $links) {
        $s = $sh.CreateShortcut((Join-Path $desk $l[0]))
        $s.TargetPath = Join-Path $Root $l[1]
        $s.WorkingDirectory = $Root
        $s.Description = $l[2]
        $s.IconLocation = Join-Path $env:WINDIR ('System32\' + $l[3])
        $s.Save()
        Write-Host "  $($l[0])"
    }
} catch { Write-Host "Could not create shortcuts: $($_.Exception.Message)" -ForegroundColor Yellow }

# ---- 6. Firewall (phones and the ESP32 node reach the dashboard on port 8000) --
Say 'Firewall'
$rule = Get-NetFirewallRule -DisplayName 'Poacher Guard 8000' -ErrorAction SilentlyContinue
if ($rule) { Write-Host 'Port 8000 is already open.' }
elseif (Ask 'Allow phones and the ESP32 node on this Wi-Fi to reach the dashboard (opens port 8000; Windows will ask for permission)?') {
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-Command',
            "New-NetFirewallRule -DisplayName 'Poacher Guard 8000' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Public"
        Write-Host 'Port 8000 opened.'
    } catch { Write-Host 'Skipped (permission not given). Only this PC can open the dashboard.' -ForegroundColor Yellow }
}

# ---- done ---------------------------------------------------------------------
$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi' -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
Write-Host ''
Write-Host '==================================================' -ForegroundColor Green
Write-Host '  Poacher Guard is installed.' -ForegroundColor Green
Write-Host '  Start it any time with the "Poacher Guard" icon on the desktop.'
Write-Host '  Dashboard on this PC : http://localhost:8000'
if ($ip) { Write-Host "  Phones / ESP32 node  : http://${ip}:8000" }
Write-Host '==================================================' -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch {}

if (-not $NoStart -and (Ask 'Start Poacher Guard now?')) {
    Start-Process (Join-Path $Root 'run-poacher-guard.bat') -WorkingDirectory $Root
}
