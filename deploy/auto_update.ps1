# Task Scheduler entrypoint for the unattended data refresh. Decrypts the stored
# admin password (DPAPI, tied to this Windows account), then runs auto_update.py
# with output tee'd to deploy\logs\. Run deploy\setup_auto_update.ps1 once first.

$ErrorActionPreference = "Stop"

$deployDir = $PSScriptRoot
$repoRoot = Split-Path $deployDir -Parent
$secretPath = Join-Path $deployDir ".fightiq_admin_pw.dpapi"
$python = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"

$logDir = Join-Path $deployDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("auto_update_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $secretPath)) {
    "No stored admin password at $secretPath - run deploy\setup_auto_update.ps1 once." |
        Tee-Object -FilePath $log
    exit 1
}
if (-not (Test-Path $python)) {
    "Backend venv python not found at $python." | Tee-Object -FilePath $log
    exit 1
}

# Decrypt the password (only decryptable by this user on this machine) into the
# env var auto_update.py / push_update.py expect. Never written to disk or logs.
$secure = Get-Content $secretPath | ConvertTo-SecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$env:FIGHTIQ_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# Native stderr must not become a terminating error mid-run (PS 5.1 quirk).
$ErrorActionPreference = "Continue"
& $python (Join-Path $deployDir "auto_update.py") 2>&1 |
    ForEach-Object { "$_" } |
    Tee-Object -FilePath $log
$exitCode = $LASTEXITCODE

# Keep the 30 most recent logs.
Get-ChildItem $logDir -Filter "auto_update_*.log" |
    Sort-Object Name -Descending |
    Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue

exit $exitCode
