@echo off
title FichaManual - Instalador
cd /d "%~dp0"
echo.
echo  FichaManual - Instalador
echo  ========================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-FichaManual.ps1"
if errorlevel 1 (
  echo.
  echo La instalacion fallo.
  pause
  exit /b 1
)
echo.
pause
