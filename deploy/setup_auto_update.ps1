# One-time setup for the unattended data refresh:
#   1. stores the admin password encrypted with DPAPI (this Windows user only);
#   2. registers a "FIGHT IQ data update" scheduled task.
#
#   powershell -ExecutionPolicy Bypass -File deploy\setup_auto_update.ps1
#   # options:  -Time 07:00  -Email you@example.com  -Server https://fightiq.fly.dev
#
# The task runs daily at -Time. If the PC is off or asleep at that moment, it runs
# as soon as the machine is next awake (StartWhenAvailable) - it never wakes the PC.
# Re-run this script any time to change the password, email, or time.

param(
    [string]$Time = "07:00",
    [string]$Email = "nrmcnally@gmail.com",
    [string]$Server = "https://fightiq.fly.dev",
    [string]$TaskName = "FIGHT IQ data update"
)

$ErrorActionPreference = "Stop"
$deployDir = $PSScriptRoot

# 1. Store the admin password, DPAPI-encrypted for the current user+machine.
$secure = Read-Host "FIGHT IQ admin password for $Email" -AsSecureString
$secure | ConvertFrom-SecureString | Set-Content (Join-Path $deployDir ".fightiq_admin_pw.dpapi")
Write-Host "Password stored (encrypted; only your Windows account can read it)."

# 2. Server/email config read by auto_update.py.
@{ server = $Server; email = $Email } | ConvertTo-Json |
    Set-Content -Encoding utf8 (Join-Path $deployDir "auto_update.config.json")

# 3. Register (or replace) the scheduled task.
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$deployDir\auto_update.ps1`""
)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Force `
    -Description "Scrape fresh UFC data locally and push it to $Server. Logs: deploy\logs\" | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered: daily at $Time (catches up if the PC was off)."
Write-Host "Test it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Logs land in:      $deployDir\logs\"
