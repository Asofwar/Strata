# Strata Turbo (the fork) - Windows installer.
# Usage (PowerShell):
#     irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
# What it does: finds the fork's release on GitHub, downloads Strata-Turbo-<version>-windows-cuda13.zip (the fork's
# code with a ready engine for NVIDIA RTX 20 and newer), checks it against the release's SHA256SUMS.txt, unpacks it into
# %LOCALAPPDATA%\Strata-Turbo\<version> and starts START-HERE.bat, which asks which model to set up.
# Options (environment variables, all optional):
#     $env:STRATA_VERSION = 'v1.0.0'      a given release instead of the latest
#     $env:STRATA_HOME = 'D:\Strata'      where to unpack (a path without spaces)
#     $env:STRATA_SETUP_ARGS = '--setup --family cyber-tiel'   arguments for START-HERE.bat
#     $env:STRATA_NO_START = '1'          unpack only, do not start setup
& {   # a child scope: `irm | iex` runs in the caller's scope, and this script's variables must not overwrite the caller's
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Die([string]$msg) { [Console]::Error.WriteLine("strata-turbo installer: $msg"); throw "strata-turbo installer stopped" }

$repo = 'Asofwar/Strata'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { Die 'this is the Windows installer; on Linux use install.sh.' }
$arch = $env:PROCESSOR_ARCHITEW6432; if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
if ($arch -ne 'AMD64') { Die "this release has an engine for Windows on x64 only (this PC: $arch)." }

Write-Host 'Strata Turbo installer'
$gpu = ''
try { $gpu = (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1 -ExpandProperty Name) } catch { }
if ($gpu) { Write-Host "  Graphics: $gpu" }
else { Write-Host '  No NVIDIA card found. The ready engine in this release needs NVIDIA RTX 20 or newer (driver 580+); setup can still build one from source.' }

$api = if ($env:STRATA_VERSION) { "https://api.github.com/repos/$repo/releases/tags/$($env:STRATA_VERSION)" } else { "https://api.github.com/repos/$repo/releases/latest" }
try { $rel = Invoke-RestMethod -UseBasicParsing -Uri $api -Headers @{ 'User-Agent' = 'strata-turbo-installer' } }
catch { Die "could not read the release list ($api). Check your internet connection." }
# releases up to 1.1.0 named the package Strata-Asofwar-*, later ones Strata-Turbo-*
$zipAsset = $rel.assets | Where-Object { $_.name -like 'Strata-Turbo-*-windows-cuda13.zip' -or $_.name -like 'Strata-Asofwar-*-windows-cuda13.zip' } | Select-Object -First 1
$sumAsset = $rel.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' } | Select-Object -First 1
if (-not $zipAsset -or -not $sumAsset) { Die "release $($rel.tag_name) has no Windows package (Strata-Turbo-*-windows-cuda13.zip and SHA256SUMS.txt)." }
$version = $rel.tag_name.TrimStart('v')
Write-Host "  Release: $($rel.tag_name) ($([math]::Round($zipAsset.size / 1MB)) MB)"

# an install from before the rename (Strata-Asofwar) keeps its folder, so its models in Strata-data are reused
$legacy = Join-Path $env:LOCALAPPDATA 'Strata-Asofwar'
$homeDir = if ($env:STRATA_HOME) { $env:STRATA_HOME } elseif (Test-Path $legacy) { $legacy } else { Join-Path $env:LOCALAPPDATA 'Strata-Turbo' }
if ($homeDir -match '\s') {
    if ($env:STRATA_HOME) { Die "STRATA_HOME has a space in its path ($homeDir); the engine's build tools need a path without spaces." }
    $homeDir = if (Test-Path 'C:\Strata-Asofwar') { 'C:\Strata-Asofwar' } else { 'C:\Strata-Turbo' }
    Write-Host "  Your profile path has a space, so the install goes to $homeDir"
}
$dest = Join-Path $homeDir $version
if (Test-Path (Join-Path $dest 'START-HERE.bat')) {
    Write-Host "  $($rel.tag_name) is already unpacked in $dest"
} else {
    $work = Join-Path ([IO.Path]::GetTempPath()) ("strata-turbo-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        $zip = Join-Path $work $zipAsset.name
        $sums = Join-Path $work 'SHA256SUMS.txt'
        Write-Host 'Downloading...'
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $sumAsset.browser_download_url -OutFile $sums
            Invoke-WebRequest -UseBasicParsing -Uri $zipAsset.browser_download_url -OutFile $zip
        } catch { Die 'the download failed. Check your internet connection and run this again; nothing was installed.' }
        $line = Get-Content $sums | Where-Object { $_ -match ('\s\*?' + [regex]::Escape($zipAsset.name) + '$') } | Select-Object -First 1
        if (-not $line) { Die "SHA256SUMS.txt has no line for $($zipAsset.name); nothing was installed." }
        $want = (-split $line)[0].ToLower()
        $got = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
        if ($got -ne $want) { Die "the download does not match SHA256SUMS.txt (got $got, wanted $want). Nothing was installed; try again." }
        Write-Host '  Checksum ok.'
        $unpack = Join-Path $work 'unpack'
        try { Expand-Archive -LiteralPath $zip -DestinationPath $unpack -Force }
        catch { Die 'the archive could not be unpacked (is the disk full?). Nothing was installed.' }
        $inner = Get-ChildItem $unpack -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'START-HERE.bat') } | Select-Object -First 1
        if (-not $inner) { Die 'the archive does not look like a Strata Turbo package.' }
        New-Item -ItemType Directory -Force -Path $homeDir | Out-Null
        Move-Item $inner.FullName $dest
        Write-Host "  Unpacked to $dest"
    } finally {
        Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
    }
}

if ($env:STRATA_NO_START -eq '1') {
    Write-Host "Done. To set up a model, run $dest\START-HERE.bat"
    return
}
Write-Host 'Starting setup (START-HERE.bat). Models and their data go to the Strata-data folder it shows.'
Write-Host '  For the fork''s long-context models answer with Cyber-Tiel-Coder or Ornith, or run:'
Write-Host "  $dest\START-HERE.bat --setup --family cyber-tiel"
Push-Location $dest
try { & cmd.exe /c "START-HERE.bat $($env:STRATA_SETUP_ARGS)" } finally { Pop-Location }
}
