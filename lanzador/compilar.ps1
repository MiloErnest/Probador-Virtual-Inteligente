# Compila "Iniciar Probador.exe" en la raíz del proyecto.
#
#     .\lanzador\compilar.ps1
#
# Usa el compilador de C# que viene con Windows (.NET Framework 4), así que no
# hay que instalar nada. El .exe no se versiona: es un binario sin firmar y se
# genera en un segundo a partir de IniciarProbador.cs, que sí está en git.

$ErrorActionPreference = 'Stop'

$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path $csc)) {
    Write-Host "No se encuentra el compilador de C# de .NET Framework 4 en $env:WINDIR\Microsoft.NET." -ForegroundColor Red
    exit 1
}

$raiz = Split-Path $PSScriptRoot -Parent
$salida = Join-Path $raiz 'Iniciar Probador.exe'
$fuente = Join-Path $PSScriptRoot 'IniciarProbador.cs'

& $csc /nologo /target:exe /optimize+ /codepage:65001 "/out:$salida" $fuente
if ($LASTEXITCODE -ne 0) {
    Write-Host "La compilación ha fallado." -ForegroundColor Red
    exit 1
}
Write-Host "Listo: $salida" -ForegroundColor Green
