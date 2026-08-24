param(
  [Parameter(Mandatory = $true)][string]$FilePath,
  [Parameter(Mandatory = $true)][string]$PrinterName
)

$ErrorActionPreference = 'Stop'
$sumatraPdf = Join-Path $PSScriptRoot 'vendor\sumatrapdf-3.6.1\SumatraPDF-3.6.1-64.exe'
$quotedPrinterName = '"{0}"' -f $PrinterName.Replace('"', '\"')
$quotedFilePath = '"{0}"' -f $FilePath.Replace('"', '\"')

if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) { throw "Print file does not exist." }
if (-not (Test-Path -LiteralPath $sumatraPdf -PathType Leaf)) { throw "Vendored SumatraPDF executable does not exist." }
if (-not (Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue)) { throw "Configured printer does not exist." }

$sumatraProcess = Start-Process -FilePath $sumatraPdf -ArgumentList @(
  '-print-to', $quotedPrinterName,
  '-print-settings', 'simplex',
  '-silent', $quotedFilePath
) -Wait -PassThru
if ($sumatraProcess.ExitCode -ne 0) { throw "SumatraPDF print failed with exit code $($sumatraProcess.ExitCode)." }
