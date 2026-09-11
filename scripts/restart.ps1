<#
.SYNOPSIS
    Restart the ScrapeGraphAI Streamlit GUI.

.USAGE
    ./scripts/restart.ps1
    ./scripts/restart.ps1 -Port 8600
#>
param(
    [int]$Port = 8502
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "gui\manage_gui.ps1") restart -Port $Port
