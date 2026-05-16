# ============================================================
#  AnamnezAI — Yerel GPU Köprüsü
#  Cloudflare Tunnel (ucretsiz, limitsiz) kullanir
#  Kullanim: PowerShell'de  .\bridge_gpu.ps1
# ============================================================

param(
    [int]$OllamaPort = 11434
)

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$DEPLOY_DIR = Join-Path $SCRIPT_DIR "deploy"
$CF_EXE = "C:\Users\pc\AppData\Local\Programs\cloudflared\cloudflared.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AnamnezAI GPU Bridge - Yerel GPU'yu sunucuya bagla" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ollama calisiyor mu? ───────────────────────────────────
Write-Host "[1/4] Yerel Ollama kontrol ediliyor..." -ForegroundColor Yellow

# Ollama'yi OLLAMA_ORIGINS=* ile (yeniden) baslatmak gerekiyor
# Cloudflare tunnel farkli origin'den gelecegi icin Ollama izin vermeli
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ollamaProc) {
    Write-Host "      Ollama calisiyor (PID: $($ollamaProc.Id)). ORIGINS=* kontrolu yapiliyor..." -ForegroundColor Gray
    # Test: tünel disinda bir origin ile erisim simule et
    try {
        $headers = @{ "Origin" = "https://test.trycloudflare.com" }
        $null = Invoke-RestMethod "http://localhost:$OllamaPort/api/tags" -Headers $headers -TimeoutSec 5
        Write-Host "      OK OLLAMA_ORIGINS=* aktif" -ForegroundColor Green
    } catch {
        Write-Host "      Ollama CORS restricts disallows tunnel. Yeniden baslatiliyor OLLAMA_ORIGINS=*..." -ForegroundColor Yellow
        Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 3
        $env:OLLAMA_ORIGINS = "*"
        $env:OLLAMA_HOST = "0.0.0.0:11434"
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Write-Host "      Ollama basliyor (15 sn bekleniyor)..." -ForegroundColor Gray
        Start-Sleep -Seconds 15
    }
} else {
    Write-Host "      Ollama calısmiyor. OLLAMA_ORIGINS=* ile baslatiliyor..." -ForegroundColor Yellow
    $env:OLLAMA_ORIGINS = "*"
    $env:OLLAMA_HOST = "0.0.0.0:11434"
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Write-Host "      Ollama basliyor (15 sn bekleniyor)..." -ForegroundColor Gray
    Start-Sleep -Seconds 15
}

try {
    $resp = Invoke-RestMethod "http://localhost:$OllamaPort/api/tags" -TimeoutSec 10
    $models = $resp.models | ForEach-Object { $_.name }
    Write-Host "      OK Ollama calisiyor. Modeller: $($models -join ', ')" -ForegroundColor Green
    if (-not ($models | Where-Object { $_ -match "gemma" })) {
        Write-Host "      UYARI: gemma modeli bulunamadi!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "      HATA: Ollama calısmiyor! Once 'ollama serve' calistir." -ForegroundColor Red
    exit 1
}

# ── 2. cloudflared var mi? ────────────────────────────────────
Write-Host ""
Write-Host "[2/4] cloudflared kontrol ediliyor..." -ForegroundColor Yellow
if (-not (Test-Path $CF_EXE)) {
    Write-Host "      Indiriliyor..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path (Split-Path $CF_EXE) -Force | Out-Null
    curl.exe -L "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -o $CF_EXE --silent --show-error
    if (-not (Test-Path $CF_EXE)) {
        Write-Host "      HATA: cloudflared indirilemedi!" -ForegroundColor Red
        exit 1
    }
}
Write-Host "      OK cloudflared: $CF_EXE" -ForegroundColor Green

# ── 3. Tuneli baslat ─────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Cloudflare tuneli baslatiliyor..." -ForegroundColor Yellow
$tunnelLog = "$env:TEMP\cf_gpu_tunnel.log"
if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force }

$tunnelProcess = Start-Process -FilePath $CF_EXE `
    -ArgumentList "tunnel","--url","http://localhost:$OllamaPort" `
    -RedirectStandardError $tunnelLog `
    -PassThru -WindowStyle Hidden

Write-Host "      PID $($tunnelProcess.Id) - URL bekleniyor (max 25 sn)..." -ForegroundColor Gray

$tunnelUrl = $null
$deadline = (Get-Date).AddSeconds(35)
while ((Get-Date) -lt $deadline -and -not $tunnelUrl) {
    Start-Sleep -Milliseconds 700
    if (Test-Path $tunnelLog) {
        $lines = Get-Content $tunnelLog -ErrorAction SilentlyContinue
        foreach ($line in $lines) {
            if ($line -match '(https://[a-z0-9][a-z0-9\-]+\.trycloudflare\.com)') {
                $tunnelUrl = $Matches[1]
                break
            }
        }
    }
}

if (-not $tunnelUrl) {
    Write-Host "      HATA: Tunel URL alinamadi. Log:" -ForegroundColor Red
    Get-Content $tunnelLog -ErrorAction SilentlyContinue | Select-Object -Last 8
    Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "      OK Tunel URL: $tunnelUrl" -ForegroundColor Green

# ── 4. Sunucuyu guncelle ─────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Sunucu guncelleniyor..." -ForegroundColor Yellow
python (Join-Path $DEPLOY_DIR "gpu_bridge_update.py") $tunnelUrl

# ── Ozet ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GPU Koprusu Kuruldu!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Tunel URL  : $tunnelUrl" -ForegroundColor White
Write-Host "  Sunucu     : http://10.200.9.11" -ForegroundColor White
Write-Host "  Model      : gemma4:e4b + medgemma:4b (senin GPU'nda)" -ForegroundColor White
Write-Host ""
Write-Host "  UYARI: Bu pencereyi KAPATMA - tunel aktif olmali!" -ForegroundColor Yellow
Write-Host "  Ctrl+C ile durdurunca sunucu otomatik CPU moduna alınır." -ForegroundColor Gray
Write-Host ""

# ── Ctrl+C bekle, kapaninca sunucuyu geri al ─────────────────
try {
    Write-Host "Tunel aktif... (Ctrl+C ile durdur)" -ForegroundColor Green
    while (-not $tunnelProcess.HasExited) {
        Start-Sleep -Seconds 5
    }
} finally {
    Write-Host ""
    Write-Host "[Cleanup] Tunel kapatiliyor..." -ForegroundColor Yellow
    Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[Cleanup] Sunucu CPU moduna aliniyor..." -ForegroundColor Yellow
    python (Join-Path $DEPLOY_DIR "gpu_bridge_restore.py")
    Write-Host "[Done] Sunucu CPU moduna gecti." -ForegroundColor Gray
}

