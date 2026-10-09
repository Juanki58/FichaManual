<#
.SYNOPSIS
  Instala FichaManual en el perfil del usuario y crea accesos directos.
#>
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppSource = Join-Path $ScriptDir "app"
$ExeSource = Join-Path $AppSource "FichaManual.exe"
$IconSource = Join-Path $ScriptDir "fichamanual.ico"

if (-not (Test-Path $ExeSource)) {
  throw "No se encuentra app\FichaManual.exe. Ejecuta este instalador desde la carpeta FichaManual-Setup."
}

$InstallDir = Join-Path $env:LOCALAPPDATA "FichaManual"
Write-Host "Instalando en: $InstallDir"

if (Test-Path $InstallDir) {
  Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $AppSource "*") $InstallDir

$IconDest = Join-Path $InstallDir "fichamanual.ico"
if (Test-Path $IconSource) {
  Copy-Item -Force $IconSource $IconDest
} elseif (Test-Path (Join-Path $AppSource "assets\fichamanual.ico")) {
  Copy-Item -Force (Join-Path $AppSource "assets\fichamanual.ico") $IconDest
}

$ExeDest = Join-Path $InstallDir "FichaManual.exe"
Copy-Item -Force (Join-Path $ScriptDir "Uninstall-FichaManual.ps1") (Join-Path $InstallDir "Uninstall-FichaManual.ps1")

function New-Shortcut {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Target,
    [string]$IconLocation,
    [string]$WorkingDirectory
  )
  $shell = New-Object -ComObject WScript.Shell
  $sc = $shell.CreateShortcut($Path)
  $sc.TargetPath = $Target
  if ($WorkingDirectory) { $sc.WorkingDirectory = $WorkingDirectory }
  if ($IconLocation -and (Test-Path $IconLocation)) {
    $sc.IconLocation = "$IconLocation,0"
  }
  $sc.Description = "FichaManual - Resume y ordena manuales"
  $sc.Save()
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\FichaManual"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

New-Shortcut -Path (Join-Path $Desktop "FichaManual.lnk") -Target $ExeDest -IconLocation $IconDest -WorkingDirectory $InstallDir
New-Shortcut -Path (Join-Path $StartMenu "FichaManual.lnk") -Target $ExeDest -IconLocation $IconDest -WorkingDirectory $InstallDir
New-Shortcut -Path (Join-Path $StartMenu "Desinstalar FichaManual.lnk") -Target "powershell.exe" -WorkingDirectory $InstallDir -IconLocation $IconDest
# Fix uninstall shortcut args
$shell = New-Object -ComObject WScript.Shell
$un = $shell.CreateShortcut((Join-Path $StartMenu "Desinstalar FichaManual.lnk"))
$un.TargetPath = "powershell.exe"
$un.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $InstallDir 'Uninstall-FichaManual.ps1')`""
$un.WorkingDirectory = $InstallDir
if (Test-Path $IconDest) { $un.IconLocation = "$IconDest,0" }
$un.Description = "Desinstalar FichaManual"
$un.Save()

Write-Host ""
Write-Host "Instalacion completada."
Write-Host "Acceso directo en el Escritorio y en el Menu Inicio."
Write-Host "Puedes abrir FichaManual ahora."
