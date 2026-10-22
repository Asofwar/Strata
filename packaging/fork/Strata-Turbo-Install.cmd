@echo off
rem Strata Turbo for Windows: the easy installer. Double-click this file.
rem It checks this PC, then downloads and sets up everything by itself (the app, Python, the Cyber-Tiel-Coder model of
rem about 17 GB) and puts a "Strata Turbo" icon on the desktop. Run it again to update; the model is not downloaded
rem again. Instructions: https://github.com/Asofwar/Strata-Turbo/blob/main/docs/EASY_INSTALL.md
rem What it runs: the PowerShell code at the end of this file downloads easy-install.ps1 from the latest release of
rem https://github.com/Asofwar/Strata-Turbo, checks it against the release's SHA256SUMS.txt and starts it.
rem Options (environment variables): STRATA_VERSION=v1.2.0 for a given release, STRATA_RELEASE_DIR=<folder> for release
rem files in a folder instead of GitHub, and the others listed at the top of easy-install.ps1.
setlocal
title Strata Turbo
set "STRATA_EASY_CMD=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s = [IO.File]::ReadAllText($env:STRATA_EASY_CMD); $i = $s.LastIndexOf('#STRATA-BOOTSTRAP' + '#'); if ($i -lt 0) { exit 3 }; Invoke-Expression $s.Substring($i)"
set "RC=%errorlevel%"
if "%RC%"=="9009" (
  echo Windows PowerShell was not found. Strata Turbo needs it: it is part of Windows 10 and 11.
  pause
)
exit /b %RC%
#STRATA-BOOTSTRAP#
# Windows PowerShell runs this part (cmd never reaches it). ASCII only: the Russian messages are base64 of UTF-8 text.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$ru = if ($env:STRATA_LANG) { $env:STRATA_LANG -like 'ru*' } else { (Get-UICulture).TwoLetterISOLanguageName -eq 'ru' }
function Msg([string]$b64, [string]$en) { if ($ru) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)) } else { $en } }
function Give-Up([string]$text, [string]$detail) {
    Write-Host ''
    Write-Host $text -ForegroundColor Red
    if ($detail) { Write-Host $detail }
    Write-Host ''
    if ($env:STRATA_NO_PAUSE -ne '1') {
        Write-Host (Msg '0J3QsNC20LzQuNGC0LUg0LvRjtCx0YPRjiDQutC70LDQstC40YjRgywg0YfRgtC+0LHRiyDQt9Cw0LrRgNGL0YLRjCDRjdGC0L4g0L7QutC90L4u' 'Press any key to close this window.')
        try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
    }
    exit 1
}
$name = 'easy-install.ps1'
$repo = 'Asofwar/Strata-Turbo'
$dst = Join-Path $env:TEMP ('strata-turbo-easy-' + [Guid]::NewGuid().ToString('N').Substring(0, 8) + '.ps1')
$noNet = Msg '0J3QtSDRg9C00LDQu9C+0YHRjCDRgdC60LDRh9Cw0YLRjCDRg9GB0YLQsNC90L7QstGJ0LjQuiBTdHJhdGEgVHVyYm8uINCf0YDQvtCy0LXRgNGM0YLQtSDQv9C+0LTQutC70Y7Rh9C10L3QuNC1INC6INC40L3RgtC10YDQvdC10YLRgyDQuCDQt9Cw0L/Rg9GB0YLQuNGC0LUg0Y3RgtC+0YIg0YTQsNC50Lsg0LXRidGRINGA0LDQty4=' 'Could not download the Strata Turbo installer. Check your internet connection and run this file again.'
$sums = $null
try {
    if ($env:STRATA_RELEASE_DIR) {
        Copy-Item -LiteralPath (Join-Path $env:STRATA_RELEASE_DIR $name) -Destination $dst
        $f = Join-Path $env:STRATA_RELEASE_DIR 'SHA256SUMS.txt'
        if (Test-Path -LiteralPath $f) { $sums = [IO.File]::ReadAllText($f) }
    } else {
        $base = if ($env:STRATA_VERSION) { "https://github.com/$repo/releases/download/$($env:STRATA_VERSION)/" } else { "https://github.com/$repo/releases/latest/download/" }
        Invoke-WebRequest -UseBasicParsing -Uri ($base + $name) -OutFile $dst -TimeoutSec 120
        try {
            $c = (Invoke-WebRequest -UseBasicParsing -Uri ($base + 'SHA256SUMS.txt') -TimeoutSec 60).Content
            $sums = if ($c -is [byte[]]) { [Text.Encoding]::ASCII.GetString($c) } else { [string]$c }
        } catch { $sums = $null }
    }
} catch { Give-Up $noNet $_.Exception.Message }
# a release that lists easy-install.ps1 in SHA256SUMS.txt gets it checked; an older one has no such line
$line = if ($sums) { ($sums -split "`r?`n") | Where-Object { $_ -match ('\s\*?' + [regex]::Escape($name) + '$') } | Select-Object -First 1 } else { $null }
if ($line) {
    $want = (-split $line)[0].ToLower()
    $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash.ToLower()
    if ($got -ne $want) {
        Remove-Item -LiteralPath $dst -ErrorAction SilentlyContinue
        Give-Up (Msg '0KHQutCw0YfQsNC90L3Ri9C5INGD0YHRgtCw0L3QvtCy0YnQuNC6INC/0L7QstGA0LXQttC00ZHQvSAo0L3QtSDRgdC+0LLQv9Cw0LvQsCDQutC+0L3RgtGA0L7Qu9GM0L3QsNGPINGB0YPQvNC80LApLiDQl9Cw0L/Rg9GB0YLQuNGC0LUg0Y3RgtC+0YIg0YTQsNC50Lsg0LXRidGRINGA0LDQty4=' 'The downloaded installer is damaged (its checksum does not match). Run this file again.') "got $got, wanted $want"
    }
}
$rc = 1
try {
    & $dst
    $rc = $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $dst -ErrorAction SilentlyContinue
}
exit $rc
