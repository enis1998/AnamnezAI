# MediScreen AI — Hızlı Başlatma (Docker'sız)
# Kullanım: .\start.ps1
# Gereksinimler: Python 3.11+, Ollama

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$backendPath = Join-Path $root "backend"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   MediScreen AI -- Baslatiliyor" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ── [1] Python kontrolü ──────────────────────────
Write-Host ""
Write-Host "[1/4] Python kontrol ediliyor..." -ForegroundColor Yellow
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    $pyCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pyCmd) {
    Write-Host "  HATA: Python bulunamadi! https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
$pyVersion = & $pyCmd.Path --version 2>&1
Write-Host "  OK: $pyVersion" -ForegroundColor Green

# ── [2] Bağımlılıklar ────────────────────────────
Write-Host ""
Write-Host "[2/4] Python bagimliliklar kontrol ediliyor..." -ForegroundColor Yellow
Set-Location $backendPath
pip install -r requirements.txt -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Bagimliliklar hazir." -ForegroundColor Green
} else {
    Write-Host "  HATA: pip install basarisiz! Manuel calistirin:" -ForegroundColor Red
    Write-Host "        pip install -r backend\requirements.txt" -ForegroundColor Gray
    exit 1
}

# ── [3] Ollama kontrolü ──────────────────────────
Write-Host ""
Write-Host "[3/4] Ollama kontrol ediliyor..." -ForegroundColor Yellow
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCmd) {
    Write-Host "  HATA: Ollama kurulu degil! https://ollama.com/download" -ForegroundColor Red
    Write-Host "  Kurun, sonra: ollama pull gemma4:e4b" -ForegroundColor Gray
    exit 1
}
Write-Host "  OK: Ollama bulundu." -ForegroundColor Green

# Ollama çalışıyor mu?
$ollamaRunning = $false
try {
    $ping = Invoke-WebRequest "http://localhost:11434" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
    if ($ping.StatusCode -eq 200) { $ollamaRunning = $true }
} catch {}

if (-not $ollamaRunning) {
    Write-Host "  Ollama serve baslatiliyor (arka plan)..." -ForegroundColor Cyan
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep 3
    Write-Host "  OK: Ollama baslatildi -> http://localhost:11434" -ForegroundColor Green
} else {
    Write-Host "  OK: Ollama zaten calisiyor." -ForegroundColor Green
}

# Model kontrolü
$GEMMA_MODEL = "gemma4:e4b"
$modelList = ollama list 2>&1
if ($modelList -match "gemma4") {
    Write-Host "  OK: Gemma4 modeli yuklu." -ForegroundColor Green
} else {
    Write-Host "  UYARI: $GEMMA_MODEL modeli bulunamadi. Indiriliyor..." -ForegroundColor Yellow
    Write-Host "  (Bu islem 5-20 dakika surebilir, internet hizina gore)" -ForegroundColor Gray
    ollama pull $GEMMA_MODEL
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: $GEMMA_MODEL indirildi." -ForegroundColor Green
    } else {
        Write-Host "  UYARI: Model indirilemedi. AI ozellikleri calismiyor olabilir." -ForegroundColor Red
    }
}

# ── [4] Backend başlat ───────────────────────────
Write-Host ""
Write-Host "[4/4] Backend baslatiliyor..." -ForegroundColor Yellow
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  MediScreen AI -- HAZIR!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Ana Sayfa  : http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs   : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Hasta UI   : http://localhost:8000/index.html" -ForegroundColor White
Write-Host "  Doktor UI  : http://localhost:8000/doctor.html" -ForegroundColor White
Write-Host "  Model      : $GEMMA_MODEL" -ForegroundColor White
Write-Host ""
Write-Host "  Durdurmak icin: Ctrl+C" -ForegroundColor Gray
Write-Host ""

# Tarayıcıyı aç
Start-Sleep 2
Start-Process "http://localhost:8000"

# Backend çalıştır
Set-Location $backendPath
$env:PYTHONUTF8    = "1"
$env:GEMMA_MODEL   = $GEMMA_MODEL
$env:OLLAMA_NUM_GPU = "99"   # Tüm katmanları GPU'ya yükle (CPU-only için 0 yap)
python main.py

