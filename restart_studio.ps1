$ErrorActionPreference = "Stop"

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
$processId = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess

[PSCustomObject]@{
    pid = $processId
    key_configured = $bootstrap.key_configured
    model = $bootstrap.settings.model
    base_url = $bootstrap.settings.base_url
    batches = @($bootstrap.batches).Count
}
