<#
.SYNOPSIS
    Show whether the ScrapeGraphAI Streamlit GUI is running.

.USAGE
    ./scripts/status.ps1
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "gui\manage_gui.ps1") status
