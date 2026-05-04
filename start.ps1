$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; python api_main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PATH = '$nodePath'; Set-Location '$root\frontend'; npm run dev"

Write-Host "Backend  → http://localhost:8000/docs"
Write-Host "Frontend → http://localhost:5173"
