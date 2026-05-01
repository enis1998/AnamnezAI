# MediScreen AI — Windows Kurulum Scripti
# PowerShell ile calistir: .\setup.ps1

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   MediScreen AI -- Kurulum Basliyor" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Hedef model — degistirmek icin: gemma4:e2b (hafif) veya gemma4:26b (guclu)
$GEMMA_MODEL = "gemma4:e4b"

# ─────────────────────────────────────────────
# [1/4] Python bagimliliklar
# ─────────────────────────────────────────────
Write-Host "[1/4] Python bagimliliklar kuruluyor..." -ForegroundColor Yellow
$backendPath = Join-Path $PSScriptRoot "backend"
Set-Location $backendPath
pip install -r requirements.txt -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Bagimliliklar kuruldu." -ForegroundColor Green
} else {
    Write-Host "  HATA: pip install basarisiz!" -ForegroundColor Red; exit 1
}

# ─────────────────────────────────────────────
# [2/4] Ollama kontrolu
# ─────────────────────────────────────────────
Write-Host ""; Write-Host "[2/4] Ollama kontrol ediliyor..." -ForegroundColor Yellow
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCmd) {
    Write-Host "  HATA: Ollama kurulu degil! https://ollama.com" -ForegroundColor Red; exit 1
}
Write-Host "  OK: Ollama bulundu." -ForegroundColor Green

# ─────────────────────────────────────────────
# [3/4] Gemma 4 model indir (yoksa)
# ─────────────────────────────────────────────
Write-Host ""; Write-Host "[3/4] Gemma 4 model kontrol ediliyor ($GEMMA_MODEL)..." -ForegroundColor Yellow
$modelList = ollama list 2>&1
if ($modelList -match $GEMMA_MODEL.Split(":")[0]) {
    Write-Host "  OK: $GEMMA_MODEL zaten yuklu." -ForegroundColor Green
} else {
    Write-Host "  Indiriliyor: $GEMMA_MODEL (5-15 dakika surebilir)..." -ForegroundColor Cyan
    ollama pull $GEMMA_MODEL
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK: Model indirildi." -ForegroundColor Green }
    else { Write-Host "  UYARI: Model indirilemedi. Elle calistirin: ollama pull $GEMMA_MODEL" -ForegroundColor Red }
}

# ─────────────────────────────────────────────
# [4/4] Ollama serve + Backend baslat
# ─────────────────────────────────────────────
Write-Host ""; Write-Host "[4/4] Servisler baslatiliyor..." -ForegroundColor Yellow

# Ollama zaten calisiyor mu?
$ollamaRunning = $false
try {
    $ping = Invoke-WebRequest "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($ping.StatusCode -eq 200) { $ollamaRunning = $true }
} catch {}

if (-not $ollamaRunning) {
    Write-Host "  Ollama serve baslatiliyor (arka planda)..." -ForegroundColor Cyan
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep 3
    Write-Host "  OK: Ollama baslatildi (port 11434)" -ForegroundColor Green
} else {
    Write-Host "  OK: Ollama zaten calisiyor (port 11434)" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  MediScreen AI -- HAZIR!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  API       : http://localhost:8000" -ForegroundColor White
Write-Host "  Docs      : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Hasta UI  : frontend\index.html" -ForegroundColor White
Write-Host "  Doktor UI : frontend\doctor.html" -ForegroundColor White
Write-Host "  Model     : $GEMMA_MODEL (Ollama)" -ForegroundColor White
Write-Host ""
Write-Host "  Ctrl+C ile durdurabilirsiniz." -ForegroundColor Gray
Write-Host ""

# Tarayicida frontend oto-ac
Start-Process (Join-Path $PSScriptRoot "frontend\index.html")

# Backend calistir
Set-Location $backendPath
$env:PYTHONUTF8 = "1"
$env:GEMMA_MODEL = $GEMMA_MODEL
python main.py

