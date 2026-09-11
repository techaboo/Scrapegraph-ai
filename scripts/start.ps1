<#
.SYNOPSIS
    Start the ScrapeGraphAI Streamlit GUI.

.USAGE
    ./scripts/start.ps1
    ./scripts/start.ps1 -Port 8600
#>
param(
    [int]$Port = 8502
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "gui\manage_gui.ps1") start -Port $Port
