# ============================================================
#  AnamnezAI GPU Koprusu - Masaustu Kisayolu Olustur
#  Bir kez calistir: .\masaustu_kisayol_olustur.ps1
# ============================================================

$BatPath    = "$PSScriptRoot\GPU_BRIDGE_BASLAT.bat"
$ShortcutPath = [System.Environment]::GetFolderPath("Desktop") + "\AnamnezAI GPU Koprusu.lnk"

$WSH = New-Object -ComObject WScript.Shell
$Shortcut = $WSH.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath  = $BatPath
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.WindowStyle = 1
$Shortcut.Description = "AnamnezAI - Yerel GPU'yu sunucuya bagla"
$Shortcut.Save()

Write-Host ""
Write-Host "  Masaustu kisayolu olusturuldu!" -ForegroundColor Green
Write-Host "  Dosya: $ShortcutPath" -ForegroundColor Gray
Write-Host ""
Write-Host "  Her bilgisayar acilisinda:" -ForegroundColor Yellow
Write-Host "  1. Masaustundeki 'AnamnezAI GPU Koprusu' ikonuna cift tikla" -ForegroundColor White
Write-Host "  2. Pencere acik kaldigi surece sunucu senin GPU'nunu kullanir" -ForegroundColor White
Write-Host "  3. Bilgisayari kapatirken pencereyi kapat (otomatik CPU moduna gecer)" -ForegroundColor White
Write-Host ""

