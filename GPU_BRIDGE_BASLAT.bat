@echo off
title AnamnezAI GPU Koprusu
color 0A
echo.
echo  ============================================================
echo   AnamnezAI - Yerel GPU Koprusu Baslatiliyor
echo  ============================================================
echo.
echo  Bu pencere acik kaldigi surece sunucu senin GPU'nunu kullanir.
echo  KAPATMA! Kapatirsan sunucu tekrar yavas CPU moduna gecer.
echo.
powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0bridge_gpu.ps1"
pause

