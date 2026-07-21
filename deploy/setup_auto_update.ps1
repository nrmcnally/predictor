# One-time setup for the unattended data refresh:
#   1. stores the admin password and odds API key encrypted with DPAPI
#      (this Windows user only);
#   2. registers a "FIGHT IQ data update" scheduled task.
#
#   powershell -ExecutionPolicy Bypass -File deploy\setup_auto_update.ps1
#   # options:  -Time 07:00  -Email you@example.com  -Server https://fightiq.fly.dev
#
# The task runs daily at -Time while this Windows user is logged on. A second
# at-logon trigger catches up after the PC was powered off or the account was
# signed out, and auto_update.py's success marker prevents duplicate daily runs.
# WakeToRun wakes a sleeping PC, but no local task can wake a powered-off PC.
# Re-run this script any time to change either secret, email, or time.

param(
    [string]$Time = "07:00",
    [string]$Email = "nrmcnally@gmail.com",
    [string]$Server = "https://fightiq.fly.dev",
    [string]$TaskName = "FIGHT IQ data update",
    [switch]$ReuseStoredSecrets
)

$ErrorActionPreference = "Stop"
$deployDir = $PSScriptRoot
$adminSecretPath = Join-Path $deployDir ".fightiq_admin_pw.dpapi"
$oddsSecretPath = Join-Path $deployDir ".fightiq_odds_api_key.dpapi"

# 1. Store the admin password, DPAPI-encrypted for the current user+machine.
if ($ReuseStoredSecrets) {
    if (-not (Test-Path $adminSecretPath) -or -not (Test-Path $oddsSecretPath)) {
        throw "Stored credentials are incomplete; run setup without -ReuseStoredSecrets."
    }
    Write-Host "Reusing the existing DPAPI-encrypted credentials."
}
else {
    $secure = Read-Host "FIGHT IQ admin password for $Email" -AsSecureString
    $secure | ConvertFrom-SecureString | Set-Content $adminSecretPath
    Write-Host "Password stored (encrypted; only your Windows account can read it)."

    $oddsKey = Read-Host "The Odds API key used by the daily refresh" -AsSecureString
    $oddsKey | ConvertFrom-SecureString | Set-Content $oddsSecretPath
    Write-Host "Odds API key stored (encrypted; only your Windows account can read it)."
}

# 2. Server/email config read by auto_update.py.
@{ server = $Server; email = $Email } | ConvertTo-Json |
    Set-Content -Encoding utf8 (Join-Path $deployDir "auto_update.config.json")

# 3. Register (or replace) the scheduled task.
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$deployDir\auto_update.ps1`""
)
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $Time
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask -TaskName $TaskName -Action $action `
    -Trigger @($dailyTrigger, $logonTrigger) `
    -Settings $settings -Force `
    -Description "Scrape fresh UFC data locally and push it to $Server. Logs: deploy\logs\" | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered: daily at $Time while this user is logged on."
Write-Host "A logon trigger catches up safely when the PC missed the scheduled time."
Write-Host "WakeToRun is enabled for sleep; successful uploads run at most once per day."
Write-Host "Test it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Logs land in:      $deployDir\logs\"
