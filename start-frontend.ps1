# Arranca el frontend (Vite).
#
# Ejecutar desde CUALQUIER carpeta:
#     powershell -File C:\ruta\al\proyecto\start-frontend.ps1
# o, si ya estás en la raíz del proyecto:
#     .\start-frontend.ps1
#
# Igual que start-backend.ps1: relee el PATH del registro (para que encuentre
# npm aunque la terminal se abriera antes de instalar Node) y resuelve las
# rutas desde la ubicación del script, no desde la carpeta actual.

$ErrorActionPreference = 'Stop'

$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

$frontendDir = Join-Path $PSScriptRoot 'frontend'

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm no está disponible ni siquiera tras releer el PATH." -ForegroundColor Red
    Write-Host "Instala Node.js con:  winget install OpenJS.NodeJS.LTS" -ForegroundColor Yellow
    exit 1
}

Set-Location $frontendDir

if (-not (Test-Path (Join-Path $frontendDir '.env'))) {
    Copy-Item '.env.example' '.env'
    Write-Host "Creado frontend\.env a partir de .env.example" -ForegroundColor DarkGray
}

if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host "Instalando dependencias (solo la primera vez)..." -ForegroundColor Yellow
    npm install --no-fund --no-audit
}

Write-Host "Frontend en http://localhost:5173" -ForegroundColor Green
Write-Host "Necesita el backend corriendo en el puerto 8000 (.\start-backend.ps1)." -ForegroundColor DarkGray
Write-Host "Ctrl+C para detener." -ForegroundColor DarkGray
Write-Host ""

npm run dev
