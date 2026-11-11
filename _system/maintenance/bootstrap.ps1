# Finds (or downloads) a Python to run setup.py with. Windows 10/11.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Host.UI.RawUI.WindowTitle = 'Meshtastic Emergency Kit - Setup'
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$SYS = Split-Path -Parent $HERE
$WORK = Join-Path $env:TEMP 'meshtastic-setup'
New-Item -ItemType Directory -Force $WORK | Out-Null

function Done($code) { Write-Host ''; Read-Host 'Press Enter to close' | Out-Null; exit $code }

if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue) -or -not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Host 'This needs Windows 10 (version 1803 or newer) or Windows 11.' -ForegroundColor Red; Done 1
}

$py = $null
$dst = Join-Path $WORK 'py'
try {
    $tgz = Join-Path $SYS 'tools\python\python-windows-x64.tar.gz'
    if (-not (Test-Path $tgz)) {
        Write-Host 'Getting a small helper (Python, about 22 MB)...'
        $rel = (& curl.exe -fsSL --retry 3 --connect-timeout 20 https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest) | ConvertFrom-Json
        $a = $rel.assets | Where-Object { $_.name -match '^cpython-3\.12\.\d+\+\d+-x86_64-pc-windows-msvc-install_only_stripped\.tar\.gz$' } | Select-Object -First 1
        if (-not $a) { throw 'helper not found' }
        $tgz = Join-Path $WORK 'python.tar.gz'
        & curl.exe -fL --retry 3 -o $tgz $a.browser_download_url
        if ($LASTEXITCODE -ne 0) { throw 'download failed' }
    }
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    New-Item -ItemType Directory -Force $dst | Out-Null
    & tar.exe -xzf $tgz -C $dst
    $py = Join-Path $dst 'python\python.exe'
    if (-not (Test-Path $py)) { throw 'unpack failed' }
} catch {
    Write-Host "Couldn't get Python on this computer ($_). Check the internet connection and try again." -ForegroundColor Red
    Done 1
}

& $py -u (Join-Path $HERE 'setup.py') @args
Done $LASTEXITCODE
