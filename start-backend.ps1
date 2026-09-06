# Arranca el backend (FastAPI + uvicorn).
#
# Ejecutar desde CUALQUIER carpeta:
#     powershell -File C:\ruta\al\proyecto\start-backend.ps1
# o, si ya estás en la raíz del proyecto:
#     .\start-backend.ps1
#
# Resuelve por su cuenta los dos problemas que más fallos causan en Windows:
#   1. El PATH obsoleto que heredan las terminales abiertas antes de instalar
#      Python (por eso se relee del registro).
#   2. Depender de la carpeta actual (por eso las rutas salen de $PSScriptRoot,
#      la ubicación de este script, y no de donde se ejecute).
#
# No hace falta activar el entorno virtual: se invoca su intérprete directamente.

$ErrorActionPreference = 'Stop'

# Relee el PATH persistido en el registro, no el heredado del proceso padre.
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

$backendDir = Join-Path $PSScriptRoot 'backend'
$venvPython = Join-Path $backendDir '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host "No se encontró el entorno virtual en $venvPython" -ForegroundColor Red
    Write-Host "Créalo con:" -ForegroundColor Yellow
    Write-Host "    cd `"$backendDir`""
    Write-Host "    python -m venv .venv"
    Write-Host "    .venv\Scripts\Activate.ps1"
    Write-Host "    pip install -r requirements-dev.txt"
    exit 1
}

if (-not (Test-Path (Join-Path $backendDir '.env'))) {
    Write-Host "Falta backend\.env. Créalo con:" -ForegroundColor Red
    Write-Host "    Copy-Item `"$backendDir\.env.example`" `"$backendDir\.env`""
    exit 1
}

Set-Location $backendDir
Write-Host "Backend en http://localhost:8000  (documentación en /docs)" -ForegroundColor Green
Write-Host "Ctrl+C para detener." -ForegroundColor DarkGray
Write-Host ""

& $venvPython -m uvicorn app.main:app --reload
