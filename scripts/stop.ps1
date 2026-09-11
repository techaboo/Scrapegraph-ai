<#
.SYNOPSIS
    Stop the ScrapeGraphAI Streamlit GUI.

.USAGE
    ./scripts/stop.ps1
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "gui\manage_gui.ps1") stop
