<#
.SYNOPSIS
  Instala FichaManual en el perfil del usuario y crea accesos directos.
#>
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# installer\ -> repo root; release\FichaManual-Setup\ -> repo root (two levels up)
if ((Split-Path -Leaf $ScriptDir) -eq "FichaManual-Setup") {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
} else {
  $RepoRoot = Split-Path -Parent $ScriptDir
}

# Prefer payload next to this script (release\FichaManual-Setup or installer\ after build).
# Fallbacks allow running installer\FichaManual-Setup.bat from the repo after a local build.
$CandidateRoots = @(
  (Join-Path $ScriptDir "app"),
  (Join-Path $RepoRoot "release\FichaManual-Setup\app"),
  (Join-Path $RepoRoot "dist\FichaManual")
)

$AppSource = $null
foreach ($cand in $CandidateRoots) {
  if (Test-Path (Join-Path $cand "FichaManual.exe")) {
    $AppSource = $cand
    break
  }
}

if (-not $AppSource) {
  throw "No se encuentra FichaManual.exe. Usa release\FichaManual-Setup (o ejecuta scripts\build_installer.ps1)."
}

$ExeSource = Join-Path $AppSource "FichaManual.exe"
$IconSource = Join-Path $ScriptDir "fichamanual.ico"
if (-not (Test-Path $IconSource)) {
  $IconSource = Join-Path $RepoRoot "release\FichaManual-Setup\fichamanual.ico"
}
if (-not (Test-Path $IconSource)) {
  $IconSource = Join-Path $RepoRoot "assets\fichamanual.ico"
}

$InstallDir = Join-Path $env:LOCALAPPDATA "FichaManual"
Write-Host "Instalando en: $InstallDir"

if (Test-Path $InstallDir) {
  Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $AppSource "*") $InstallDir

$IconDest = Join-Path $InstallDir "fichamanual.ico"
$BundledIconCandidates = @(
  (Join-Path $AppSource "assets\fichamanual.ico"),
  (Join-Path $AppSource "_internal\assets\fichamanual.ico")
)
if (Test-Path $IconSource) {
  Copy-Item -Force $IconSource $IconDest
} else {
  foreach ($bundled in $BundledIconCandidates) {
    if (Test-Path $bundled) {
      Copy-Item -Force $bundled $IconDest
      break
    }
  }
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
