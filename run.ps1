$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cliScript = Join-Path $rootDir "src\\dfm_cli.py"

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $cliScript @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $cliScript @args
    exit $LASTEXITCODE
}

Write-Host "Python 3 is required to run cnc-dfm."
exit 1
