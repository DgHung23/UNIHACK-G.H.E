# Chạy FruitChain trên Windows (1 lệnh): build frontend nếu chưa có, rồi chạy backend phục vụ cả giao diện.
#   powershell -ExecutionPolicy Bypass -File run.ps1          -> http://127.0.0.1:8000
#   powershell -ExecutionPolicy Bypass -File run.ps1 -Dev     -> backend :8000 + Vite dev :5173
param([switch]$Dev, [int]$Port = 8000, [string]$Python = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Python) {
    if (Test-Path "$root\backend\.venv\Scripts\python.exe") {
        $Python = "$root\backend\.venv\Scripts\python.exe"
    } elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
        $Python = "$env:VIRTUAL_ENV\Scripts\python.exe"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = & py -3.10 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0) { $Python = "python" }
    } else { $Python = "python" }
}
& $Python -c "import bcrypt, fastapi, jwt, sqlalchemy, multipart, cv2, torch, torchvision, web3"
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install -r "$root\backend\requirements.txt"
    if ($LASTEXITCODE -ne 0) { throw "Cannot install backend dependencies." }
}
Push-Location "$root\frontend"
try {
    if (-not (Test-Path "node_modules")) {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    }
    if (-not $Dev) {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
} finally { Pop-Location }
if ($Dev) {
    if ($Port -ne 8000) { throw "Development proxy requires backend port 8000." }
    Start-Process powershell -WindowStyle Hidden -WorkingDirectory "$root\frontend" -ArgumentList "-NoProfile", "-Command", "npm run dev"
}
$env:PYTHONUTF8 = "1"
Push-Location "$root\backend"
try {
    Write-Host "FruitChain: http://127.0.0.1:$Port"
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Backend failed to start. Check the error above." }
} finally { Pop-Location }
