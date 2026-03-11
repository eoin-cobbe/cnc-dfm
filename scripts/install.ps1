$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$installScript = Join-Path $rootDir "scripts\\install.py"

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $installScript
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $installScript
    exit $LASTEXITCODE
}

Write-Host "Python 3 is required to run the installer."
exit 1
