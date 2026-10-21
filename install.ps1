# FreeAgent IDE — Windows one-command installer
# Usage: irm https://raw.githubusercontent.com/<user>/FreeAgent-IDE/main/install.ps1 | iex
# Or from a cloned repo: .\install.ps1

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }

Write-Host ""
Write-Host "FreeAgent IDE installer" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host "Root: $Root"

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# --- Architecture ---
$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
Write-Host "OS: Windows / $arch"

if ($arch -notin @("X64", "Arm64")) {
    Write-Warning "Unsupported architecture: $arch (x64 recommended)"
}

# --- Python ---
$python = $null
$localPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (Test-Path $localPy) {
    $python = $localPy
}
foreach ($cand in @("python", "py")) {
    if ($python) { break }
    if (Test-Command $cand) {
        try {
            $ver = & $cand --version 2>&1 | Out-String
            # Skip Windows Store stub
            $cmd = Get-Command $cand -ErrorAction SilentlyContinue
            if ($cmd.Source -like "*WindowsApps*") { continue }
            if ($ver -match "Python 3\.(1[1-9]|[2-9]\d)") {
                $python = $cand
                break
            }
        } catch {}
    }
}

if (-not $python) {
    Write-Host "Python 3.11+ not found. Installing via winget..." -ForegroundColor Yellow
    if (-not (Test-Command "winget")) {
        throw "winget not available. Install Python 3.11+ from https://www.python.org/downloads/ then re-run."
    }
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (Test-Command "python") { $python = "python" }
    elseif (Test-Command "py") { $python = "py" }
    else { throw "Python installed but not on PATH. Restart the terminal and re-run install.ps1" }
}

Write-Host "Using: $(& $python --version)"

# --- Node (for frontend build) ---
if (-not (Test-Command "node")) {
    Write-Host "Node.js not found. Installing LTS via winget..." -ForegroundColor Yellow
    if (Test-Command "winget") {
        winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Warning "Install Node.js 18+ manually, then re-run to build the UI."
    }
}

# --- Ollama (optional but recommended) ---
if (-not (Test-Command "ollama")) {
    Write-Host "Ollama not found." -ForegroundColor Yellow
    $ans = Read-Host "Install Ollama for local models? [Y/n]"
    if ($ans -eq "" -or $ans -match "^[Yy]") {
        if (Test-Command "winget") {
            winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("Path", "User")
        } else {
            Write-Host "Download Ollama from https://ollama.com/download"
        }
    }
}

# --- Python venv ---
$venv = Join-Path $Root "backend\.venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..."
    & $python -m venv $venv
}
$pip = Join-Path $venv "Scripts\pip.exe"
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "Installing Python dependencies..."
& $py -m pip install --upgrade pip
& $pip install -e (Join-Path $Root "backend")

# --- Frontend ---
$frontend = Join-Path $Root "frontend"
if (Test-Command "npm") {
    Write-Host "Installing & building frontend..."
    Push-Location $frontend
    npm install
    npm run build
    Pop-Location
} else {
    Write-Warning "npm not found - skipping UI build. API-only mode will work."
}

# --- Optional model pull ---
if (Test-Command "ollama") {
    $pull = Read-Host "Download recommended model llama3.2:3b now? [Y/n]"
    if ($pull -eq "" -or $pull -match "^[Yy]") {
        try { ollama pull llama3.2:3b } catch { Write-Warning $_.Exception.Message }
    }
}

# --- Launcher (repo already ships start.ps1; rewrite only if missing) ---
$launcher = Join-Path $Root "start.ps1"
if (-not (Test-Path $launcher)) {
    $launcherLines = @(
        '$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }'
        '$py = Join-Path $Root "backend\.venv\Scripts\python.exe"'
        'if (-not (Test-Path $py)) { Write-Host "Virtualenv missing. Run .\install.ps1 first." -ForegroundColor Red; exit 1 }'
        'Set-Location (Join-Path $Root "backend")'
        'Write-Host "Starting FreeAgent IDE at http://127.0.0.1:8765" -ForegroundColor Cyan'
        'Write-Host "Press Ctrl+C to stop."'
        '& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8765'
    )
    Set-Content -Path $launcher -Value $launcherLines -Encoding UTF8
}

# Desktop shortcut
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'FreeAgent IDE.lnk'
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($shortcutPath)
    $sc.TargetPath = 'powershell.exe'
    $sc.Arguments = "-NoExit -ExecutionPolicy Bypass -File `"$launcher`""
    $sc.WorkingDirectory = $Root
    $sc.Description = 'FreeAgent IDE'
    $sc.Save()
    Write-Host "Desktop shortcut created."
} catch {
    Write-Warning "Could not create desktop shortcut: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Start Ollama if using local models"
Write-Host "  2. Run:  .\start.ps1"
Write-Host "  3. Open: http://127.0.0.1:8765"
Write-Host ""

$launch = Read-Host "Launch FreeAgent IDE now? [Y/n]"
if ($launch -eq "" -or $launch -match "^[Yy]") {
    & $launcher
}
