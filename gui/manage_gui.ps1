<#
.SYNOPSIS
    Start, stop, restart, or check the status of the ScrapeGraphAI Streamlit GUI.

.USAGE
    ./gui/manage_gui.ps1 start
    ./gui/manage_gui.ps1 stop
    ./gui/manage_gui.ps1 restart
    ./gui/manage_gui.ps1 status
    ./gui/manage_gui.ps1 start -Port 8600
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start",

    [int]$Port = 8502
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$GuiDir = Join-Path $RepoRoot "gui"
$GuiScript = Join-Path $GuiDir "scrapegraph_gui.py"
$PidFile = Join-Path $GuiDir ".gui.pid"
$LogFile = Join-Path $GuiDir "gui.log"
$ErrLogFile = Join-Path $GuiDir "gui.err.log"
$StreamlitExe = Join-Path $RepoRoot ".venv\Scripts\streamlit.exe"

function Get-RunningProcess {
    if (Test-Path $PidFile) {
        $storedPid = (Get-Content $PidFile -Raw).Trim()
        if ($storedPid -match '^\d+$') {
            $proc = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
            if ($proc) {
                return $proc
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    return $null
}

function Start-Gui {
    $existing = Get-RunningProcess
    if ($existing) {
        Write-Host "GUI already running (PID $($existing.Id)) at http://localhost:$Port/"
        return
    }

    if (-not (Test-Path $StreamlitExe)) {
        throw "streamlit executable not found at $StreamlitExe. Run 'uv sync' first."
    }
    if (-not (Test-Path $GuiScript)) {
        throw "GUI script not found at $GuiScript."
    }

    $proc = Start-Process -FilePath $StreamlitExe `
        -ArgumentList @("run", $GuiScript, "--server.port", $Port, "--server.headless", "true") `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $ErrLogFile `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $PidFile -Value $proc.Id
    Start-Sleep -Seconds 2

    if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
        Write-Host "GUI started (PID $($proc.Id)) at http://localhost:$Port/"
        Write-Host "Logs: $LogFile"
    } else {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "GUI failed to start. Check $ErrLogFile for details."
    }
}

function Stop-Gui {
    $existing = Get-RunningProcess
    if (-not $existing) {
        Write-Host "GUI is not running."
        return
    }

    # -T also kills the streamlit worker's child processes (e.g. Playwright browser).
    & taskkill /PID $existing.Id /T /F | Out-Null
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "GUI stopped (was PID $($existing.Id))."
}

function Get-GuiStatus {
    $existing = Get-RunningProcess
    if ($existing) {
        Write-Host "GUI running (PID $($existing.Id)) at http://localhost:$Port/"
    } else {
        Write-Host "GUI is not running."
    }
}

switch ($Action) {
    "start"   { Start-Gui }
    "stop"    { Stop-Gui }
    "restart" { Stop-Gui; Start-Sleep -Seconds 1; Start-Gui }
    "status"  { Get-GuiStatus }
}
