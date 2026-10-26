<#
.SYNOPSIS
  Intenta generar la APK debug de FichaManual (Android).
  Requiere JDK 17+ y Android SDK (p. ej. Android Studio).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$AndroidDir = Join-Path $Root "android"
Set-Location $AndroidDir

function Test-Java {
  try {
    $null = & java -version 2>&1
    return $LASTEXITCODE -eq 0 -or $true
  } catch {
    return $false
  }
}

if (-not (Test-Java)) {
  Write-Host "No se encontró Java en el PATH."
  Write-Host "Abre la carpeta android\ en Android Studio y usa:"
  Write-Host "  Build → Build Bundle(s) / APK(s) → Build APK(s)"
  Write-Host "Salida esperada: android\app\build\outputs\apk\debug\app-debug.apk"
  exit 1
}

$gradlew = Join-Path $AndroidDir "gradlew.bat"
if (-not (Test-Path $gradlew)) {
  Write-Host "Falta gradlew.bat. Abre android\ una vez en Android Studio"
  Write-Host "para que genere el wrapper, o instala Gradle y ejecuta:"
  Write-Host "  gradle wrapper"
  Write-Host "Luego vuelve a lanzar este script."
  exit 1
}

& $gradlew assembleDebug --no-daemon
if ($LASTEXITCODE -ne 0) { throw "assembleDebug falló (código $LASTEXITCODE)" }

$apk = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $apk)) { throw "No se generó la APK: $apk" }

$destDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$dest = Join-Path $destDir "FichaManual-android-debug.apk"
Copy-Item -Force $apk $dest
Write-Host ""
Write-Host "APK lista:"
Write-Host "  $apk"
Write-Host "  $dest"
