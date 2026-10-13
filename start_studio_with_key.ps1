$ErrorActionPreference = "Stop"

$secure = Read-Host "Paste OPENAI_API_KEY for this local studio session" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($plain)) {
    throw "OPENAI_API_KEY was empty."
}

$envPath = Join-Path $PSScriptRoot ".env"
@(
    "OPENAI_API_KEY=$plain"
    "OPENAI_BASE_URL=http://localhost:3000/v1"
) | Set-Content -Path $envPath -Encoding UTF8

$env:OPENAI_API_KEY = $plain
$env:OPENAI_BASE_URL = "http://localhost:3000/v1"

$old = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess
if ($old) {
    Stop-Process -Id $old -Force
    Start-Sleep -Milliseconds 800
}

$python = "C:\Program Files\Python\python.exe"
$resourceZip = "C:\Users\yuyiling\Downloads\UMGC_resources.zip"
Start-Process -FilePath $python `
    -ArgumentList @("web_app.py", "--port", "8765", "--resource-zip", $resourceZip) `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden

Start-Sleep -Seconds 2
$bootstrap = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/bootstrap" -Method Get
Write-Host ""
Write-Host "UMGC Document Studio restarted at http://127.0.0.1:8765/"
Write-Host ("Key configured: " + $bootstrap.key_configured)
Write-Host ("Model: " + $bootstrap.settings.model)
Write-Host ""
Read-Host "Press Enter to close this window"
