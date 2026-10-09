<#
.SYNOPSIS
  Desinstalador de FichaManual.
#>
$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:LOCALAPPDATA "FichaManual"
$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\FichaManual"

$desktopLnk = Join-Path $Desktop "FichaManual.lnk"
if (Test-Path $desktopLnk) { Remove-Item -Force $desktopLnk }
if (Test-Path $StartMenu) { Remove-Item -Recurse -Force $StartMenu }

Write-Host "Eliminando: $InstallDir"
# El script vive dentro de InstallDir; borrar al final vía cmd
$cmd = "ping 127.0.0.1 -n 2 >nul & rmdir /s /q `"$InstallDir`""
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Hidden
Write-Host "FichaManual desinstalado."
Start-Sleep -Seconds 1
