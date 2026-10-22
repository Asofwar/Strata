# Strata Turbo - the easy installer for Windows (NVIDIA RTX 20 series and newer).
#
# Strata-Turbo-Install.cmd (a release asset) downloads this file from the same release and runs it. It asks nothing.
# Before anything big is downloaded it checks the PC: an NVIDIA RTX 20 or newer card, driver 580 or newer, 32 GB of RAM,
# free disk space for the app and the model, the internet. Then it downloads the release zip, checks it against
# SHA256SUMS.txt, unpacks it into %LOCALAPPDATA%\Strata-Turbo\<version> (or <drive>:\Strata-Turbo on another fixed drive
# when that drive has too little space), runs setup with its recommended answers for Cyber-Tiel-Coder
# (START-HERE.bat --setup --family cyber-tiel --yes --no-start, plus --draft-vocab cyrillic when Windows is in Russian),
# puts a "Strata Turbo" shortcut on the desktop and in the Start menu (with Stop and Uninstall next to it) and starts
# Strata Turbo in its own window: the chat opens in the browser when the model is ready. Run again, it updates to the
# newest release and reuses the downloaded model.
# Messages are in Russian when Windows is in Russian, else in English. The details go to <install folder>\install.log.
#
# This file is UTF-8 with a BOM: Windows PowerShell 5.1 reads a file without one in the ANSI code page.
#
# The install copies this file to <install folder>\Strata-Turbo.ps1, and the shortcuts run that copy:
#     Strata-Turbo.ps1 start       start Strata Turbo and open the chat (only the chat when it is already running)
#     Strata-Turbo.ps1 stop        stop it
#     Strata-Turbo.ps1 uninstall   remove it (asks first, and asks again before it deletes the downloaded model)
#     Strata-Turbo.ps1             install or update
#
# Options (environment variables, all optional):
#     STRATA_HOME=D:\Strata        where to install (a path without spaces)
#     STRATA_VERSION=v1.2.0        a given release instead of the latest
#     STRATA_RELEASE_DIR=D:\rel    a folder with the release files instead of GitHub
#                                  (Strata-Turbo-<version>-windows-cuda13.zip, SHA256SUMS.txt, this file)
#     STRATA_DATA_DIR=D:\data      the model folder (setup's --data-dir)
#     STRATA_SETUP_ARGS=...        more setup arguments, after the easy installer's own
#     STRATA_NO_START=1            install, but do not start Strata Turbo at the end
#     STRATA_LANG=ru | en          the language of the messages
#     STRATA_SKIP_CHECKS=1         a failed check only warns (for a PC the checks misjudge)
#     STRATA_CHECK_ONLY=1          run the checks, then stop
#     STRATA_NO_PAUSE=1            never wait for a key
# For tests (they change nothing on the PC):
#     STRATA_SHORTCUTS_DIR=<dir>   the shortcuts go to <dir>\Desktop and <dir>\Programs, and no Apps entry is made
#     STRATA_TEST_GPU=none | nodriver | "<name>;<compute capability>;<driver>;<VRAM MiB>"
#     STRATA_TEST_RAM_GB=16        STRATA_TEST_FREE_GB=5 (every drive) or C=5,D=40        STRATA_TEST_OFFLINE=1
#     STRATA_OPEN_URL_LOG=<file>   the chat's address is written to this file instead of opening the browser
param([string]$Mode = 'install')

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Repo = 'Asofwar/Strata-Turbo'
$ModelTag = 'cybertiel-UD-IQ4_XS'                         # setup's folder for the recommended size (models\<tag>)
$ModelFile = 'Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf'
$ModelBytes = 18119934272                                 # setup.py CYBER_TIEL_FILES
$MinRamGiB = 28        # setup stops below the smallest Flash-Next model's 32 GB less 4 (a 32 GB PC shows ~31.8 GiB)
$MinDriver = 580       # setup.py MIN_DRIVER (CUDA 13)
$MinCC = 7.5           # RTX 20 (Turing) and newer
$AppGiB = 2.0          # the unpacked release, its Python environment and the zip while it is unpacked
$DefaultPort = 8080
$VersionName = '^\d+(\.\d+)+([-+][0-9A-Za-z.]+)?$'   # a version folder (1.2.0): the only folders Start, Stop and Uninstall touch
$VersionDir = '^\d+(\.\d+)+'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\StrataTurbo'

$script:Ru = if ($env:STRATA_LANG) { $env:STRATA_LANG -like 'ru*' } else { (Get-UICulture).TwoLetterISOLanguageName -eq 'ru' }
$script:LogFile = $null
$script:StatusOpen = $false
$script:Console = $true
try { $script:Console = -not [Console]::IsOutputRedirected } catch { $script:Console = $false }
if (-not $script:Console) { try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch { } }   # a log or a test reads it

function T([string]$ru, [string]$en) { if ($script:Ru) { $ru } else { $en } }

# ------------------------------------------------------------------------------------------------ output
function Log([string]$s) {
    if (-not $script:LogFile) { return }
    try { Add-Content -LiteralPath $script:LogFile -Value ('{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $s) -Encoding UTF8 } catch { }
}

function End-Status {
    if ($script:StatusOpen) { Write-Host ''; $script:StatusOpen = $false }
}

function Say([string]$s = '', [string]$color = '') {
    End-Status
    if ($color) { Write-Host $s -ForegroundColor $color } else { Write-Host $s }
    Log $s
}

function Good([string]$s) { Say ('   + ' + $s) 'Green' }
function Note([string]$s) { Say ('   ! ' + $s) 'Yellow' }

function Step([int]$n, [string]$s) {
    Say ''
    Say ((T 'Шаг {0} из 5. {1}' 'Step {0} of 5. {1}') -f $n, $s) 'Cyan'
}

function Show-Status([string]$text) {
    # one line rewritten in place: a progress bar or a clock (a redirected output gets nothing: the log has the steps)
    if (-not $script:Console) { return }
    $w = 79
    try { $w = [Math]::Max(40, $Host.UI.RawUI.WindowSize.Width - 1) } catch { }
    if ($text.Length -gt $w) { $text = $text.Substring(0, $w) }
    Write-Host -NoNewline ("`r" + $text.PadRight($w))
    $script:StatusOpen = $true
}

function Bar([double]$frac) {
    $frac = [Math]::Min(1.0, [Math]::Max(0.0, $frac))
    $n = [int][Math]::Floor($frac * 24)
    return ('[' + ('#' * $n) + ('-' * (24 - $n)) + ']' + (' {0,3}%' -f [int][Math]::Floor($frac * 100)))
}

function Fmt-Time([double]$sec) {
    if ($sec -lt 60) { return (T 'меньше минуты' 'under a minute') }
    $m = [int][Math]::Ceiling($sec / 60)
    if ($m -lt 60) { return ((T '{0} мин' '{0} min') -f $m) }
    return ((T '{0} ч {1} мин' '{0} h {1} min') -f [int][Math]::Floor($m / 60), ($m % 60))
}

function Fmt-Clock([double]$sec) { return ('{0}:{1:00}' -f [int][Math]::Floor($sec / 60), ([int]$sec % 60)) }

function GiB([double]$bytes) { return ('{0:N1}' -f ($bytes / 1GB)) }

function Wait-Key {
    if ($env:STRATA_NO_PAUSE -eq '1') { return }
    try { if ([Console]::IsInputRedirected) { return } } catch { return }
    Say ''
    Write-Host (T 'Нажмите любую клавишу, чтобы закрыть это окно.' 'Press any key to close this window.')
    try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
}

# The one way an install stops: a plain sentence, the details, the log. `throw` unwinds to Main, which waits and exits 1.
function Stop-Easy([string]$sentence, [string[]]$details = @()) {
    Say ''
    Say ((T 'Установка остановлена. ' 'Setup stopped. ') + $sentence) 'Red'
    foreach ($d in $details) { if ($d) { Say ('   ' + $d) } }
    if ($script:LogFile) { Say ((T 'Подробности записаны в файл: {0}' 'Details are in: {0}') -f $script:LogFile) }
    throw 'strata-easy-stop'
}

function Check-Failed([string]$sentence, [string[]]$details = @()) {
    if ($env:STRATA_SKIP_CHECKS -eq '1') {
        Note ($sentence + ' ' + (T '(STRATA_SKIP_CHECKS=1: продолжаю)' '(STRATA_SKIP_CHECKS=1: going on)'))
        return
    }
    Stop-Easy $sentence $details
}

# ------------------------------------------------------------------------------------------------ helpers
function Run-Native([string]$exe, [string]$arguments, [int]$timeoutMs = 20000) {
    # stdout of a program, '' when it cannot run (no stderr records: they would stop this script)
    try {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = $arguments
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $p = [Diagnostics.Process]::Start($psi)
        $out = $p.StandardOutput.ReadToEndAsync()
        [void]$p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($timeoutMs)) { try { $p.Kill() } catch { }; return '' }
        if ($p.ExitCode -ne 0) { return '' }
        return $out.Result
    } catch { return '' }
}

function Http-Ok([string]$url, [int]$timeoutMs = 15000) {
    if ($env:STRATA_TEST_OFFLINE -eq '1') { return $false }
    try {
        $req = [Net.HttpWebRequest]::Create($url)
        $req.Method = 'GET'
        $req.Timeout = $timeoutMs
        $req.UserAgent = 'strata-turbo-easy-installer'
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch [Net.WebException] {
        # an answer of any kind (404, 401 ...) means the site is reachable
        return ($null -ne $_.Exception.Response)
    } catch { return $false }
}

function Free-GiB([string]$path) {
    $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($path))
    $letter = $root.Substring(0, 1).ToUpper()
    if ($env:STRATA_TEST_FREE_GB) {
        $t = $env:STRATA_TEST_FREE_GB
        if ($t -match '^[\d.]+$') { return [double]$t }
        foreach ($pair in ($t -split ',')) {
            $kv = $pair -split '='
            if ($kv.Count -eq 2 -and $kv[0].Trim().ToUpper() -eq $letter) { return [double]$kv[1] }
        }
    }
    try { return ((New-Object IO.DriveInfo $root).AvailableFreeSpace / 1GB) } catch { return 0.0 }
}

function Fixed-Drives {
    $list = @()
    foreach ($d in [IO.DriveInfo]::GetDrives()) {
        try { if ($d.DriveType -eq 'Fixed' -and $d.IsReady) { $list += $d.Name } } catch { }
    }
    return $list
}

function Same-Drive([string]$a, [string]$b) {
    return ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($a)).ToUpper() -eq [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($b)).ToUpper())
}

function Under([string]$child, [string]$parent) {
    $c = [IO.Path]::GetFullPath($child).TrimEnd('\') + '\'
    $p = [IO.Path]::GetFullPath($parent).TrimEnd('\') + '\'
    return $c.StartsWith($p, [StringComparison]::OrdinalIgnoreCase)
}

function Settings-DataDir {
    # the model folder setup remembers for every Strata on this PC (setup.py settings_path / data_folder)
    $base = $env:APPDATA
    if (-not $base) { return $null }
    $f = Join-Path (Join-Path $base 'Strata') 'settings.json'
    if (-not (Test-Path -LiteralPath $f)) { return $null }
    try {
        $s = Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($s.data_dir) { return [string]$s.data_dir }
    } catch { }
    return $null
}

function Server-Up([int]$port) {
    # a Strata server answers /status with its state (busy, ...)
    try {
        $r = Invoke-RestMethod -UseBasicParsing -Uri ("http://127.0.0.1:{0}/status" -f $port) -TimeoutSec 3
        return ($null -ne $r)
    } catch { return $false }
}

function Port-Free([int]$port) {
    try {
        $l = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Loopback), $port
        $l.Start()
        $l.Stop()
        return $true
    } catch { return $false }
}

function Open-Chat([int]$port) {
    $url = 'http://127.0.0.1:{0}/' -f $port
    if ($env:STRATA_OPEN_URL_LOG) { Add-Content -LiteralPath $env:STRATA_OPEN_URL_LOG -Value $url; return }
    try { Start-Process $url } catch { Say ((T 'Откройте в браузере: {0}' 'Open in your browser: {0}') -f $url) }
}

function Version-Key([string]$name) {
    try { return [version]($name -replace '[^0-9.].*$', '') } catch { return [version]'0.0' }
}

# Every unpacked Strata version in the install folder, newest first, with its Cyber-Tiel start script and config.
function Installed-Versions([string]$homeDir) {
    $out = @()
    if (-not (Test-Path -LiteralPath $homeDir)) { return $out }
    foreach ($d in (Get-ChildItem -LiteralPath $homeDir -Directory -ErrorAction SilentlyContinue)) {
        if ($d.Name -notmatch $VersionName) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $d.FullName 'START-HERE.bat'))) { continue }
        $bats = @(Get-ChildItem -LiteralPath $d.FullName -Filter 'run-cybertiel-*.bat' -ErrorAction SilentlyContinue)
        if (-not $bats.Count) { $bats = @(Get-ChildItem -LiteralPath $d.FullName -Filter 'run-*.bat' -ErrorAction SilentlyContinue) }
        $bat = $bats | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $cfg = $null
        $port = $DefaultPort
        $log = $null
        $ready = $false
        if ($bat) {
            $cfg = Join-Path $d.FullName ('strata-' + $bat.BaseName.Substring(4) + '.json')
            if (Test-Path -LiteralPath $cfg) {
                try {
                    $j = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($j.port) { $port = [int]$j.port }
                    if ($j.log) { $log = [string]$j.log }
                    $a = @($j.args)
                    $i = [Array]::IndexOf($a, '--native')
                    $gguf = if ($i -ge 0 -and $i + 1 -lt $a.Count) { [string]$a[$i + 1] } else { $null }
                    $exeOk = (-not $j.exe) -or ([string]$j.exe).StartsWith('component:') -or (Test-Path -LiteralPath ([string]$j.exe))
                    $ready = $exeOk -and ((-not $gguf) -or (Test-Path -LiteralPath $gguf))
                } catch { $ready = $false }
            }
        }
        $out += [pscustomobject]@{ Name = $d.Name; Dir = $d.FullName; Key = (Version-Key $d.Name); Bat = $(if ($bat) { $bat.FullName } else { $null })
                                   Tiel = [bool]($bat -and $bat.Name -like 'run-cybertiel-*')
                                   Cfg = $cfg; Port = $port; Log = $log; Ready = $ready }
    }
    return @($out | Sort-Object Key, Name -Descending)
}

# ------------------------------------------------------------------------------------------------ the checks
function Get-Gpus {
    # @{ Adapter = <an NVIDIA display adapter's name or $null>; Smi = <nvidia-smi answered>; Cards = @(...) }
    $t = $env:STRATA_TEST_GPU
    if ($t) {
        if ($t -eq 'none') { return @{ Adapter = $null; Smi = $false; Cards = @() } }
        if ($t -eq 'nodriver') { return @{ Adapter = 'NVIDIA GeForce RTX 3060'; Smi = $false; Cards = @() } }
        $f = $t -split ';'
        return @{ Adapter = $f[0]; Smi = $true; Cards = @([pscustomobject]@{ Name = $f[0]; CC = [double]$f[1]; Driver = $f[2]; VramMiB = [double]$f[3] }) }
    }
    $adapter = $null
    $wmiDriver = $null
    try {
        $nv = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
        if ($nv) {
            $adapter = [string]$nv.Name
            # Windows' driver version 32.0.15.6142 is NVIDIA's 561.42 (its last five digits)
            $digits = ([string]$nv.DriverVersion) -replace '\D', ''
            if ($digits.Length -ge 5) { $last = $digits.Substring($digits.Length - 5); $wmiDriver = $last.Substring(0, 3) + '.' + $last.Substring(3) }
        }
    } catch { }
    $smi = $null
    foreach ($c in @((Join-Path $env:SystemRoot 'System32\nvidia-smi.exe'), (Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'))) {
        if (Test-Path -LiteralPath $c) { $smi = $c; break }
    }
    if (-not $smi) { $g = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue; if ($g) { $smi = $g.Source } }
    $cards = @()
    if ($smi) {
        $text = Run-Native $smi '--query-gpu=name,compute_cap,driver_version,memory.total --format=csv,noheader,nounits'
        if (-not $text) {   # an old driver does not know compute_cap
            $text = Run-Native $smi '--query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits'
            foreach ($line in ($text -split "`r?`n")) {
                $f = @($line -split ',' | ForEach-Object { $_.Trim() })
                if ($f.Count -ge 3) { $cards += [pscustomobject]@{ Name = $f[0]; CC = 0.0; Driver = $f[1]; VramMiB = ($f[2] -as [double]) } }
            }
        } else {
            foreach ($line in ($text -split "`r?`n")) {
                $f = @($line -split ',' | ForEach-Object { $_.Trim() })
                if ($f.Count -ge 4) {
                    $cc = 0.0
                    [void][double]::TryParse($f[1], [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$cc)
                    $cards += [pscustomobject]@{ Name = $f[0]; CC = $cc; Driver = $f[2]; VramMiB = ($f[3] -as [double]) }
                }
            }
        }
    }
    if (-not $cards.Count -and $adapter -and $wmiDriver -and $smi) {
        # nvidia-smi is there but said nothing usable: Windows' own view of the driver
        $cards += [pscustomobject]@{ Name = $adapter; CC = 0.0; Driver = $wmiDriver; VramMiB = 0 }
    }
    return @{ Adapter = $adapter; Smi = [bool]$cards.Count; Cards = $cards }
}

function Driver-Major([string]$v) {
    $m = [regex]::Match([string]$v, '^\s*(\d+)')
    if ($m.Success) { return [int]$m.Groups[1].Value }
    return 0
}

function Check-Gpu {
    $info = Get-Gpus
    $driverPage = T 'https://www.nvidia.com/ru-ru/drivers/' 'https://www.nvidia.com/en-us/drivers/'
    if (-not $info.Adapter -and -not $info.Cards.Count) {
        Check-Failed (T 'На этом компьютере не найдена видеокарта NVIDIA.' 'No NVIDIA graphics card was found on this PC.') @(
            (T 'Strata Turbo работает только с видеокартами NVIDIA GeForce RTX 20-й серии и новее (RTX 2060, 3060, 4070, 5080 и т. п.).' `
               'Strata Turbo runs only on NVIDIA GeForce RTX 20 series cards and newer (RTX 2060, 3060, 4070, 5080 and so on).'))
        return
    }
    if (-not $info.Cards.Count) {
        Check-Failed (T 'Видеокарта NVIDIA есть, но её драйвер не установлен или не отвечает.' 'There is an NVIDIA card, but its driver is not installed or does not answer.') @(
            ((T 'Установите драйвер с {0} (или через приложение NVIDIA App), перезагрузите компьютер и запустите установку снова.' `
                'Install the driver from {0} (or with the NVIDIA App), restart the PC and run this installer again.') -f $driverPage))
        return
    }
    $best = $info.Cards | Sort-Object @{ Expression = { $_.CC } ; Descending = $true }, @{ Expression = { $_.VramMiB } ; Descending = $true } | Select-Object -First 1
    $vram = [double]$best.VramMiB / 1024
    # compute capability 7.5 = Turing (RTX 20, GTX 16); a driver too old to say it names the card instead
    $old = if ($best.CC -gt 0) { $best.CC -lt $MinCC } else { $best.Name -match 'GTX\s*(9\d\d|10\d\d)\b|\bGT\s*\d{3,4}\b|Quadro\s+[KMP]\d|Tesla\s+[KMP]' }
    if ($old) {
        Check-Failed ((T 'Видеокарта {0} слишком старая.' 'The graphics card {0} is too old.') -f $best.Name) @(
            (T 'Нужна NVIDIA GeForce RTX 20-й серии или новее.' 'Strata Turbo needs an NVIDIA GeForce RTX 20 series card or newer.'))
        return
    }
    $major = Driver-Major $best.Driver
    if ($major -lt $MinDriver) {
        Check-Failed ((T 'Драйвер видеокарты устарел: версия {0}, а нужна {1} или новее.' 'The graphics driver is too old: version {0}, and {1} or newer is needed.') -f $best.Driver, $MinDriver) @(
            (T 'Обновите его: откройте приложение NVIDIA App, вкладку «Драйверы», и нажмите «Загрузить».' `
               'Update it: open the NVIDIA App, go to Drivers and click Download.'),
            ((T 'Или скачайте драйвер со страницы {0} (выберите свою видеокарту).' 'Or download it from {0} (choose your card).') -f $driverPage),
            (T 'Потом перезагрузите компьютер и запустите установку снова.' 'Then restart the PC and run this installer again.'))
        return
    }
    if ($vram -gt 0) {
        Good ((T 'Видеокарта: {0}, память видеокарты {1:N0} ГБ, драйвер {2}' 'Graphics card: {0}, {1:N0} GB of graphics memory, driver {2}') -f $best.Name, $vram, $best.Driver)
    } else {
        Good ((T 'Видеокарта: {0}, драйвер {1}' 'Graphics card: {0}, driver {1}') -f $best.Name, $best.Driver)
    }
    if ($vram -gt 0 -and $vram -lt 11) {
        Note (T 'У видеокарты меньше 12 ГБ памяти: Strata Turbo будет работать, но заметно медленнее.' 'The card has less than 12 GB of memory: Strata Turbo will run, but noticeably slower.')
    }
}

function Check-Ram {
    $gib = 0.0
    if ($env:STRATA_TEST_RAM_GB) { $gib = [double]$env:STRATA_TEST_RAM_GB }
    else { try { $gib = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB } catch { $gib = 0.0 } }
    if ($gib -gt 0 -and $gib -lt $MinRamGiB) {
        Check-Failed ((T 'Мало оперативной памяти: {0:N0} ГБ.' 'Not enough memory (RAM): {0:N0} GB.') -f $gib) @(
            (T 'Strata Turbo нужно не меньше 32 ГБ оперативной памяти.' 'Strata Turbo needs 32 GB of RAM or more.'))
        return
    }
    Good ((T 'Оперативная память: {0:N0} ГБ' 'Memory (RAM): {0:N0} GB') -f $gib)
}

# Where the app and the model go, with enough free space for both: an earlier install's folder, else
# %LOCALAPPDATA%\Strata-Turbo, else <the fixed drive with the most free space>:\Strata-Turbo.
function Plan-Folders {
    $existing = $null
    if ($env:STRATA_HOME) { $existing = $env:STRATA_HOME }
    else {
        try { $loc = (Get-ItemProperty -LiteralPath $UninstallKey -ErrorAction Stop).InstallLocation; if ($loc -and (Test-Path -LiteralPath $loc)) { $existing = $loc } } catch { }
        if (-not $existing) {
            $cands = @((Join-Path $env:LOCALAPPDATA 'Strata-Asofwar'), (Join-Path $env:LOCALAPPDATA 'Strata-Turbo'), 'C:\Strata-Turbo', 'C:\Strata-Asofwar')
            foreach ($d in (Fixed-Drives)) { $cands += (Join-Path $d 'Strata-Turbo') }
            foreach ($c in $cands) { if (@(Installed-Versions $c).Count) { $existing = $c; break } }
        }
    }
    if ($existing -and $existing -match '\s') {
        Stop-Easy ((T 'В пути к папке установки есть пробел: {0}' 'The install folder''s path has a space: {0}') -f $existing) @(
            (T 'Укажите папку без пробелов в переменной STRATA_HOME.' 'Set STRATA_HOME to a folder without spaces.'))
    }
    $dataDir = if ($env:STRATA_DATA_DIR) { $env:STRATA_DATA_DIR } else { Settings-DataDir }
    if ($dataDir -and -not (Test-Path -LiteralPath ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($dataDir))))) {
        Stop-Easy ((T 'Диск с папкой моделей Strata ({0}) сейчас недоступен.' 'The drive of Strata''s model folder ({0}) is not available now.') -f $dataDir) @(
            (T 'Подключите этот диск и запустите установку снова.' 'Connect that drive and run this installer again.'))
    }
    $needModel = ($ModelBytes / 1GB) + 1.5    # the file, setup's own 1 GB of room and some more
    $needApp = $AppGiB + 0.5

    function Fits([string]$homeDir) {
        $data = if ($dataDir) { $dataDir } else { Join-Path $homeDir 'Strata-data' }
        $m = Join-Path (Join-Path (Join-Path $data 'models') $ModelTag) $ModelFile
        $present = (Test-Path -LiteralPath $m) -and ((Get-Item -LiteralPath $m).Length -eq $ModelBytes)
        $partBytes = 0
        if (-not $present -and (Test-Path -LiteralPath ($m + '.part'))) { $partBytes = (Get-Item -LiteralPath ($m + '.part')).Length }
        $nm = if ($present) { 0.0 } else { $needModel - ($partBytes / 1GB) }
        if (Same-Drive $homeDir $data) {
            $need = $needApp + $nm
            $ok = (Free-GiB $homeDir) -ge $need
            return @{ Ok = $ok; Data = $data; Present = $present; Need = $need; Short = $(if ($ok) { $null } else { $homeDir }); NeedShort = $need }
        }
        $okA = (Free-GiB $homeDir) -ge $needApp
        $okM = (Free-GiB $data) -ge $nm
        $short = if (-not $okM) { $data } elseif (-not $okA) { $homeDir } else { $null }
        return @{ Ok = ($okA -and $okM); Data = $data; Present = $present; Need = ($needApp + $nm); Short = $short; NeedShort = $(if (-not $okM) { $nm } else { $needApp }) }
    }

    if ($existing) {
        $f = Fits $existing
        if (-not $f.Ok) {
            $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($f.Short))
            Check-Failed ((T 'Мало места на диске {0}: свободно {1:N1} ГБ, а нужно около {2:N0} ГБ.' 'Not enough free space on drive {0}: {1:N1} GB free, about {2:N0} GB needed.') -f $root.TrimEnd('\'), (Free-GiB $f.Short), [Math]::Ceiling($f.NeedShort)) @(
                (T 'Освободите место (удалите ненужные файлы или очистите корзину) и запустите установку снова.' 'Free some space (delete files you do not need, empty the Recycle Bin) and run this installer again.'))
        }
        return @{ Home = $existing; Data = $f.Data; ModelPresent = $f.Present; Need = $f.Need; Moved = $false }
    }
    $default = Join-Path $env:LOCALAPPDATA 'Strata-Turbo'
    # the engine's tools need a path without spaces; a user name in Cyrillic (or any non-ASCII letters) gets the same
    # short path too: part of the engine opens files with narrow (code page) paths
    if ($default -match '\s' -or $default -match '[^\x21-\x7E]') { $default = 'C:\Strata-Turbo' }
    $f = Fits $default
    if ($f.Ok) { return @{ Home = $default; Data = $f.Data; ModelPresent = $f.Present; Need = $f.Need; Moved = $false } }
    if ($dataDir -and -not (Same-Drive $dataDir $default) -and $f.Short -eq $dataDir) {
        $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($dataDir))
        Check-Failed ((T 'Мало места на диске {0} в папке моделей Strata ({1}): нужно около {2:N0} ГБ.' 'Not enough free space on drive {0} for Strata''s model folder ({1}): about {2:N0} GB needed.') -f $root.TrimEnd('\'), $dataDir, [Math]::Ceiling($f.NeedShort)) @(
            (T 'Освободите место и запустите установку снова.' 'Free some space and run this installer again.'))
    }
    $best = $null
    $bestFree = -1.0
    foreach ($d in (Fixed-Drives)) {
        if (Same-Drive $d $default) { continue }
        $h = Join-Path $d 'Strata-Turbo'
        $g = Fits $h
        $free = Free-GiB $d
        if ($g.Ok -and $free -gt $bestFree) { $best = @{ Home = $h; Data = $g.Data; ModelPresent = $g.Present; Need = $g.Need; Moved = $true }; $bestFree = $free }
    }
    if ($best) {
        $root = [IO.Path]::GetPathRoot($default).TrimEnd('\')
        Note ((T 'На диске {0} мало места (свободно {1:N1} ГБ, нужно около {2:N0} ГБ), поэтому Strata Turbo будет установлена в {3}.' `
                 'Drive {0} has too little free space ({1:N1} GB free, about {2:N0} GB needed), so Strata Turbo goes to {3}.') -f $root, (Free-GiB $default), [Math]::Ceiling($f.Need), $best.Home)
        return $best
    }
    $root = [IO.Path]::GetPathRoot($default).TrimEnd('\')
    Check-Failed ((T 'Не хватает места на диске: нужно около {0:N0} ГБ свободного места (на диске {1} свободно {2:N1} ГБ).' 'Not enough disk space: about {0:N0} GB of free space is needed (drive {1} has {2:N1} GB free).') -f [Math]::Ceiling($f.Need), $root, (Free-GiB $default)) @(
        (T 'Освободите место (удалите ненужные файлы или очистите корзину) и запустите установку снова.' 'Free some space (delete files you do not need, empty the Recycle Bin) and run this installer again.'))
    return @{ Home = $default; Data = $f.Data; ModelPresent = $f.Present; Need = $f.Need; Moved = $false }
}

function No-Internet([string]$site) {
    Stop-Easy ((T 'Нет связи с интернетом: не открывается {0}.' 'No internet connection: {0} does not answer.') -f $site) @(
        (T 'Проверьте, что интернет работает (например, откройте любой сайт в браузере), и запустите установку снова.' `
           'Check that the internet works (open any website in your browser) and run this installer again.'),
        (T 'Если интернет есть, а ошибка повторяется, этот сайт может быть недоступен у вашего провайдера.' `
           'If the internet works and this repeats, your provider may block that site.'))
}

# The release to install: @{ Version; Tag; ZipName; Zip (URL or path); Sums; Size }
function Find-Release {
    if ($env:STRATA_RELEASE_DIR) {
        $dir = $env:STRATA_RELEASE_DIR
        $zips = @(Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^Strata-(Turbo|Asofwar)-(.+)-windows-cuda13\.zip$' })
        if (-not $zips.Count) { Stop-Easy ((T 'В папке {0} нет файла Strata-Turbo-<версия>-windows-cuda13.zip.' 'The folder {0} has no Strata-Turbo-<version>-windows-cuda13.zip.') -f $dir) }
        $z = $zips | Sort-Object @{ Expression = { Version-Key ($_.Name -replace '^Strata-(Turbo|Asofwar)-', '') } } -Descending | Select-Object -First 1
        $ver = [regex]::Match($z.Name, '^Strata-(Turbo|Asofwar)-(.+)-windows-cuda13\.zip$').Groups[2].Value
        return @{ Version = $ver; Tag = ('v' + $ver); ZipName = $z.Name; Zip = $z.FullName; Sums = (Join-Path $dir 'SHA256SUMS.txt'); Size = $z.Length }
    }
    if ($env:STRATA_TEST_OFFLINE -eq '1') { No-Internet 'github.com' }
    $api = if ($env:STRATA_VERSION) { "https://api.github.com/repos/$Repo/releases/tags/$($env:STRATA_VERSION)" } else { "https://api.github.com/repos/$Repo/releases/latest" }
    try {
        $rel = Invoke-RestMethod -UseBasicParsing -Uri $api -Headers @{ 'User-Agent' = 'strata-turbo-easy-installer' } -TimeoutSec 30
        # releases up to 1.1.0 named the package Strata-Asofwar-*, later ones Strata-Turbo-*
        $zipAsset = $rel.assets | Where-Object { $_.name -like 'Strata-Turbo-*-windows-cuda13.zip' -or $_.name -like 'Strata-Asofwar-*-windows-cuda13.zip' } | Select-Object -First 1
        $sumAsset = $rel.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' } | Select-Object -First 1
        if (-not $zipAsset -or -not $sumAsset) {
            Stop-Easy ((T 'В выпуске {0} нет файлов для Windows.' 'Release {0} has no Windows package.') -f $rel.tag_name) @(
                (T 'Попробуйте позже: выпуск может ещё загружаться.' 'Try again later: the release may still be uploading.'))
        }
        return @{ Version = $rel.tag_name.TrimStart('v'); Tag = $rel.tag_name; ZipName = $zipAsset.name; Zip = $zipAsset.browser_download_url
                  Sums = $sumAsset.browser_download_url; Size = $zipAsset.size }
    } catch {
        if ($_.Exception.Message -eq 'strata-easy-stop') { throw }
        Log ('GitHub API: ' + $_.Exception.Message)
    }
    # the API can refuse (60 requests an hour per address): the release page's redirect names the latest tag too
    $tag = $env:STRATA_VERSION
    if (-not $tag) {
        try {
            $req = [Net.HttpWebRequest]::Create("https://github.com/$Repo/releases/latest")
            $req.AllowAutoRedirect = $false
            $req.UserAgent = 'strata-turbo-easy-installer'
            $req.Timeout = 30000
            $resp = $req.GetResponse()
            $loc = $resp.Headers['Location']
            $resp.Close()
            if ($loc -match '/releases/tag/([^/?#]+)') { $tag = $Matches[1] }
        } catch { Log ('github.com: ' + $_.Exception.Message) }
    }
    if (-not $tag) { No-Internet 'github.com' }
    $ver = $tag.TrimStart('v')
    $name = "Strata-Turbo-$ver-windows-cuda13.zip"
    return @{ Version = $ver; Tag = $tag; ZipName = $name; Zip = "https://github.com/$Repo/releases/download/$tag/$name"
              Sums = "https://github.com/$Repo/releases/download/$tag/SHA256SUMS.txt"; Size = 0 }
}

# ------------------------------------------------------------------------------------------------ download and unpack
# A file from a URL or a path, with a progress bar; returns the bytes per second (0 for a copy).
function Get-File([string]$src, [string]$dst, [double]$size) {
    if ($src -notmatch '^https?://') { Copy-Item -LiteralPath $src -Destination $dst -Force; return 0.0 }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $in = $null
        $out = $null
        try {
            $req = [Net.HttpWebRequest]::Create($src)
            $req.UserAgent = 'strata-turbo-easy-installer'
            $req.Timeout = 30000
            $req.ReadWriteTimeout = 60000
            $resp = $req.GetResponse()
            $total = [double]$resp.ContentLength
            if ($total -le 0) { $total = $size }
            $in = $resp.GetResponseStream()
            $out = [IO.File]::Create($dst)
            $buf = New-Object byte[] (1MB)
            $have = 0.0
            $t0 = [DateTime]::UtcNow
            $last = $t0
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
                $out.Write($buf, 0, $n)
                $have += $n
                $now = [DateTime]::UtcNow
                if (($now - $last).TotalMilliseconds -ge 500 -and $total -gt 0) {
                    $last = $now
                    $rate = $have / [Math]::Max(0.5, ($now - $t0).TotalSeconds)
                    Show-Status ('   ' + (Bar ($have / $total)) + ('  {0:N0} / {1:N0} {2}' -f ($have / 1MB), ($total / 1MB), (T 'МБ' 'MB')) +
                                 ('  ' + (T 'осталось {0}' '{0} left') -f (Fmt-Time (($total - $have) / [Math]::Max(1.0, $rate)))))
                }
            }
            $out.Close(); $out = $null
            $in.Close(); $in = $null
            $resp.Close()
            End-Status
            if ($total -gt 0 -and $have -ne $total) { throw ('short download: {0} of {1} bytes' -f $have, $total) }
            return ($have / [Math]::Max(0.5, ([DateTime]::UtcNow - $t0).TotalSeconds))
        } catch {
            End-Status
            Log ("download $src (attempt $attempt): " + $_.Exception.Message)
            if ($out) { $out.Close() }
            if ($in) { $in.Close() }
            if ($attempt -eq 3) { throw }
            Start-Sleep -Seconds 5
        }
    }
}

function Expand-Release([string]$zip, [string]$dest) {
    # the zip's one top folder is unpacked straight into <dest>.partial, renamed to <dest> when it is whole (a cut-off
    # unpack never looks installed), and no path gets longer than it has to (Windows' 260-character limit)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $partial = $dest + '.partial'
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Recurse -Force }
    New-Item -ItemType Directory -Path $partial | Out-Null
    $root = [IO.Path]::GetFullPath($partial).TrimEnd('\') + '\'
    $za = [IO.Compression.ZipFile]::OpenRead($zip)
    try {
        $top = $null
        foreach ($e in $za.Entries) { if ($e.FullName -match '^([^/]+)/START-HERE\.bat$') { $top = $Matches[1]; break } }
        if (-not $top) { Stop-Easy (T 'Скачанный файл не похож на выпуск Strata Turbo.' 'The downloaded file does not look like a Strata Turbo release.') }
        $all = $za.Entries.Count
        $i = 0
        foreach ($e in $za.Entries) {
            $i++
            if (-not $e.FullName.StartsWith($top + '/')) { continue }
            $rel = $e.FullName.Substring($top.Length + 1)
            if (-not $rel) { continue }
            $target = [IO.Path]::GetFullPath((Join-Path $partial ($rel -replace '/', '\')))
            if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { continue }   # never outside the folder
            if ($e.FullName.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($target); continue }
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $target, $true)
            if ($i % 200 -eq 0) { Show-Status ('   ' + (Bar ($i / $all)) + '  ' + (T 'распаковываю' 'unpacking')) }
        }
    } finally { $za.Dispose() }
    End-Status
    Rename-Item -LiteralPath $partial -NewName (Split-Path -Leaf $dest)
}

function Get-App($rel, [string]$homeDir, [string]$dest, [bool]$modelPresent) {
    $dl = Join-Path $homeDir '.download'
    New-Item -ItemType Directory -Force -Path $dl | Out-Null
    $zip = Join-Path $dl $rel.ZipName
    $sums = Join-Path $dl 'SHA256SUMS.txt'
    try {
        try { [void](Get-File $rel.Sums $sums 0) }
        catch { No-Internet 'github.com' }
        Say ((T '   Скачиваю программу ({0:N0} МБ)...' '   Downloading the app ({0:N0} MB)...') -f ([double]$rel.Size / 1MB))
        $rate = 0.0
        try { $rate = Get-File $rel.Zip $zip $rel.Size }
        catch { No-Internet 'github.com' }
        $line = Get-Content -LiteralPath $sums | Where-Object { $_ -match ('\s\*?' + [regex]::Escape($rel.ZipName) + '$') } | Select-Object -First 1
        if (-not $line) { Stop-Easy ((T 'В SHA256SUMS.txt нет строки для {0}.' 'SHA256SUMS.txt has no line for {0}.') -f $rel.ZipName) }
        $want = (-split $line)[0].ToLower()
        $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLower()
        if ($got -ne $want) {
            Stop-Easy (T 'Скачанный файл повреждён (не совпала контрольная сумма). Запустите установку ещё раз.' 'The download is damaged (its checksum does not match). Run this installer again.') @("got $got, wanted $want")
        }
        Good (T 'Программа скачана и проверена' 'The app is downloaded and checked')
        if ($rate -gt 0 -and -not $modelPresent) {
            Say ((T '   Скорость интернета около {0:N1} МБ/с: модель (17 ГБ) скачается примерно за {1}.' '   Internet speed is about {0:N1} MB/s: the model (17 GB) takes about {1} to download.') -f ($rate / 1MB), (Fmt-Time ($ModelBytes / $rate)))
        }
        Say (T '   Распаковываю...' '   Unpacking...')
        try { Expand-Release $zip $dest }
        catch {
            if ($_.Exception.Message -eq 'strata-easy-stop') { throw }
            Log ('unpack: ' + $_.Exception.Message)
            Stop-Easy (T 'Не получилось распаковать программу (возможно, кончилось место на диске).' 'The app could not be unpacked (is the disk full?).') @($_.Exception.Message)
        }
        Good ((T 'Программа распакована в {0}' 'Unpacked to {0}') -f $dest)
    } finally {
        Remove-Item -LiteralPath $dl -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ------------------------------------------------------------------------------------------------ setup, followed
function Quote-Arg([string]$a) { if ($a -match '[\s"]') { return '"' + ($a -replace '"', '\"') + '"' } return $a }

function Run-Setup([string]$dest, [string[]]$setupArgs, [bool]$modelPresent) {
    $setupLog = Join-Path (Split-Path -Parent $dest) 'install-setup.log'
    Remove-Item -LiteralPath $setupLog -ErrorAction SilentlyContinue
    Log ('setup: START-HERE.bat ' + ($setupArgs -join ' '))
    # the full path: cmd skips the current folder when NoDefaultCurrentDirectoryInExePath is set
    $line = '"' + (Join-Path $dest 'START-HERE.bat') + '" ' + (($setupArgs | ForEach-Object { Quote-Arg $_ }) -join ' ') + ' < nul > "' + $setupLog + '" 2>&1'
    $p = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\cmd.exe') -ArgumentList ('/d /s /c "' + $line + '"') `
                       -WorkingDirectory $dest -NoNewWindow -PassThru
    $null = $p.Handle   # kept, so ExitCode is there after the process ends
    $t0 = [DateTime]::UtcNow
    $offset = 0L
    $pending = ''
    $failMsg = $null
    $failHint = $null
    $done = $false
    $samples = New-Object System.Collections.ArrayList
    $lastPct = -10
    $progress = $null

    $phases = @{
        'python' = (T 'Устанавливаю Python — программу, на которой работает Strata (бесплатно, 1–3 минуты)' 'Installing Python, the program Strata runs on (free, 1-3 minutes)')
        'prep' = (T 'Подготавливаю программу (первый раз до 5 минут)' 'Preparing the app (up to 5 minutes the first time)')
        'pc' = (T 'Проверяю компьютер и выбираю настройки' 'Checking the PC and choosing the settings')
        'pip' = (T 'Устанавливаю компоненты Python (1–3 минуты)' 'Installing Python components (1-3 minutes)')
        'engine' = (T 'Готовлю движок Strata' 'Preparing the Strata engine')
        'download' = (T 'Скачиваю модель Cyber-Tiel-Coder (17 ГБ). Это самый долгий шаг. Если окно закрыть, скачивание потом продолжится с того же места.' 'Downloading the Cyber-Tiel-Coder model (17 GB). This is the longest step. If the window is closed, the download resumes where it stopped.')
        'have' = (T 'Модель уже скачана, второй раз не качаю' 'The model is already downloaded: not downloading it again')
        'verify' = (T 'Проверяю скачанную модель (1–3 минуты)' 'Checking the downloaded model (1-3 minutes)')
        'prepare' = (T 'Готовлю модель к работе' 'Preparing the model')
        'finish' = (T 'Сохраняю настройки' 'Saving the settings')
    }
    function Enter-Phase([string]$name) {
        if ($script:SetupPhase -eq $name) { return }
        $script:SetupPhase = $name
        if ($name -in @('download', 'have', 'verify', 'prepare', 'finish') -and -not $script:Step4) {
            $script:Step4 = $true
            Step 4 (T 'Скачиваю модель' 'Downloading the model')
        }
        Say ('   ' + $phases[$name])
        $script:PhaseT = [DateTime]::UtcNow
    }
    $script:SetupPhase = ''
    $script:Step4 = $false
    $script:Step5Seen = $false
    $script:PhaseT = $t0
    Step 3 (T 'Устанавливаю программу и компоненты' 'Installing the app and its components')
    Enter-Phase 'prep'

    while ($true) {
        $exited = $p.HasExited
        $text = ''
        if (Test-Path -LiteralPath $setupLog) {
            try {
                $fs = New-Object IO.FileStream ($setupLog, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
                try {
                    if ($fs.Length -gt $offset) {
                        [void]$fs.Seek($offset, [IO.SeekOrigin]::Begin)
                        $buf = New-Object byte[] ($fs.Length - $offset)
                        $n = $fs.Read($buf, 0, $buf.Length)
                        $offset += $n
                        $text = [Text.Encoding]::UTF8.GetString($buf, 0, $n)
                    }
                } finally { $fs.Close() }
            } catch { }
        }
        if ($text) {
            $pending += $text
            # the download's progress: "\r  <file>:  12.34 / 18.12 GB (68%)" every 2 s, on one line
            $ms = [regex]::Matches($pending, '([\d.]+) / ([\d.]+) GB \((\d+)%\)')
            if ($ms.Count -and $script:Step5Seen) {      # (step 4's engine download, when there is one, is not the model)
                Enter-Phase 'download'
                $m = $ms[$ms.Count - 1]
                $inv = [Globalization.CultureInfo]::InvariantCulture
                $progress = @{ Have = [double]::Parse($m.Groups[1].Value, $inv) * 1e9; Total = [double]::Parse($m.Groups[2].Value, $inv) * 1e9 }
                [void]$samples.Add(@([DateTime]::UtcNow, $progress.Have))
                while ($samples.Count -gt 2 -and ([DateTime]::UtcNow - $samples[0][0]).TotalSeconds -gt 40) { $samples.RemoveAt(0) }
            }
            $parts = $pending -split "`n"
            $pending = $parts[$parts.Count - 1]
            for ($k = 0; $k -lt $parts.Count - 1; $k++) {
                $l = ($parts[$k].TrimEnd("`r") -split "`r")[-1].TrimEnd()   # a CRLF's CR, then the last of a line's \r rewrites
                if ($l -match 'Python 3\.10 or newer is not installed') { Enter-Phase 'python' }
                elseif ($l -match '^=== Step 1:|^=== Step 2:') { Enter-Phase 'pc' }
                elseif ($l -match '^=== Step 3:') { Enter-Phase 'pip' }
                elseif ($l -match '^=== Step 4:') { Enter-Phase 'engine' }
                elseif ($l -match '^=== Step 5:') { $script:Step5Seen = $true; if (-not $modelPresent) { Enter-Phase 'download' } }
                elseif ($l -match 'already downloaded' -and $l -match '\.gguf') { Enter-Phase 'have' }
                elseif ($l -match '^\s*checking .*\(SHA-256') { Enter-Phase 'verify' }
                elseif ($l -match '^=== Step 6:') { Enter-Phase 'prepare' }
                elseif ($l -match '^=== Step 7:') { Enter-Phase 'finish' }
                elseif ($l -match '^All set\.') { $done = $true }
                elseif ($l -match '^\s*\[X\]\s+(.*)$') { $failMsg = $Matches[1]; $failHint = '' }
                elseif ($null -ne $failHint -and $failHint -eq '' -and $l -match '^\s{5,}(\S.*)$') { $failHint = $Matches[1] }
                elseif ($l -match 'Python could not be installed automatically') { $failMsg = 'python' }
                elseif ($l -match 'Could not create the Python environment') { $failMsg = 'venv' }
            }
        }
        if ($exited) { break }
        $now = [DateTime]::UtcNow
        if ($script:SetupPhase -eq 'download' -and $progress -and $progress.Total -gt 0) {
            $rate = 0.0
            if ($samples.Count -ge 2) {
                $dt = ($samples[$samples.Count - 1][0] - $samples[0][0]).TotalSeconds
                if ($dt -gt 0) { $rate = ($samples[$samples.Count - 1][1] - $samples[0][1]) / $dt }
            }
            $frac = $progress.Have / $progress.Total
            $left = if ($rate -gt 0) { (T 'осталось около {0}' 'about {0} left') -f (Fmt-Time (($progress.Total - $progress.Have) / $rate)) } else { (T 'считаю время' 'estimating') }
            Show-Status ('   ' + (Bar $frac) + ('  {0} / {1} {2}  {3}' -f (GiB $progress.Have), (GiB $progress.Total), (T 'ГБ' 'GB'), $left))
            $pct = [int][Math]::Floor($frac * 100)
            if ($pct -ge $lastPct + 10) { $lastPct = $pct - ($pct % 10); Log ('model download: {0}% ({1} / {2} GiB)' -f $pct, (GiB $progress.Have), (GiB $progress.Total)) }
        } else {
            Show-Status ('   ' + (T 'идёт работа, прошло {0}' 'working, {0} so far') -f (Fmt-Clock ($now - $script:PhaseT).TotalSeconds))
        }
        Start-Sleep -Milliseconds 1000
    }
    End-Status
    $p.WaitForExit()
    $code = $p.ExitCode
    # setup's whole output goes into the install log
    try { Add-Content -LiteralPath $script:LogFile -Value (Get-Content -LiteralPath $setupLog -Raw -Encoding UTF8) -Encoding UTF8 } catch { }
    Remove-Item -LiteralPath $setupLog -ErrorAction SilentlyContinue
    Log ("setup exit code: $code")
    if ($done -and -not $failMsg) { return }
    $sentence = T 'Не получилось настроить Strata Turbo.' 'Strata Turbo could not be set up.'
    $details = @()
    if ($failMsg -eq 'python') {
        $sentence = T 'Не получилось установить Python автоматически.' 'Python could not be installed automatically.'
        $details = @((T 'Установите Python 3.12 с https://www.python.org/downloads/ (в установщике отметьте «Add python.exe to PATH») и запустите установку снова.' `
                        'Install Python 3.12 from https://www.python.org/downloads/ (tick "Add python.exe to PATH" in its installer) and run this installer again.'))
    } elseif ($failMsg -eq 'venv') {
        $details = @((T 'Не получилось создать рабочую папку Python. Запустите установку ещё раз.' 'The Python environment could not be created. Run this installer again.'))
    } elseif ($failMsg) {
        if ($failMsg -match 'not enough free disk space') { $sentence = T 'Не хватило места на диске.' 'The disk ran out of space.' }
        elseif ($failMsg -match 'cannot reach|could not finish downloading|download') { $sentence = T 'Прервалось скачивание: проверьте интернет.' 'A download failed: check the internet connection.' }
        $details = @(((T 'Сообщение программы установки (на английском): {0}' 'Setup said: {0}') -f $failMsg), $failHint)
    }
    $details += (T 'Запустите установку ещё раз: то, что уже скачано, второй раз качаться не будет.' 'Run this installer again: what is already downloaded is not downloaded again.')
    Stop-Easy $sentence $details
}

# ------------------------------------------------------------------------------------------------ shortcuts, Apps entry
function Shortcut-Dirs {
    if ($env:STRATA_SHORTCUTS_DIR) {
        return @{ Desktop = (Join-Path $env:STRATA_SHORTCUTS_DIR 'Desktop'); Programs = (Join-Path $env:STRATA_SHORTCUTS_DIR 'Programs'); Registry = $false }
    }
    return @{ Desktop = [Environment]::GetFolderPath('Desktop'); Programs = [Environment]::GetFolderPath('Programs'); Registry = $true }
}

function Shortcut-Names {
    return @{ Start = 'Strata Turbo'; Stop = (T 'Остановить Strata Turbo' 'Stop Strata Turbo'); Uninstall = (T 'Удалить Strata Turbo' 'Uninstall Strata Turbo') }
}

function New-Shortcut([string]$path, [string]$launcher, [string]$mode, [string]$icon, [string]$description) {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($path)
    $s.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $s.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $launcher + '" ' + $mode
    $s.WorkingDirectory = Split-Path -Parent $launcher
    if ($icon -and (Test-Path -LiteralPath $icon)) { $s.IconLocation = $icon + ',0' }
    $s.Description = $description
    $s.Save()
}

function Install-Shortcuts([string]$homeDir, [string]$dest, [string]$version) {
    $launcher = Join-Path $homeDir 'Strata-Turbo.ps1'
    if (-not ($PSCommandPath -and ([IO.Path]::GetFullPath($PSCommandPath) -eq [IO.Path]::GetFullPath($launcher)))) {
        Copy-Item -LiteralPath $PSCommandPath -Destination $launcher -Force
    }
    $icon = Join-Path $homeDir 'strata-turbo.ico'
    $src = Join-Path $dest 'apps\desktop\src-tauri\icons\icon.ico'
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination $icon -Force }
    $dirs = Shortcut-Dirs
    $names = Shortcut-Names
    $menu = Join-Path $dirs.Programs 'Strata Turbo'
    New-Item -ItemType Directory -Force -Path $dirs.Desktop, $menu | Out-Null
    Get-ChildItem -LiteralPath $menu -Filter '*.lnk' -ErrorAction SilentlyContinue | Remove-Item -Force   # (names of another language)
    $about = T 'Запустить Strata Turbo и открыть чат' 'Start Strata Turbo and open the chat'
    New-Shortcut (Join-Path $dirs.Desktop ($names.Start + '.lnk')) $launcher 'start' $icon $about
    New-Shortcut (Join-Path $menu ($names.Start + '.lnk')) $launcher 'start' $icon $about
    New-Shortcut (Join-Path $menu ($names.Stop + '.lnk')) $launcher 'stop' $icon (T 'Выключить Strata Turbo' 'Stop Strata Turbo')
    New-Shortcut (Join-Path $menu ($names.Uninstall + '.lnk')) $launcher 'uninstall' $icon (T 'Удалить Strata Turbo с компьютера' 'Remove Strata Turbo from this PC')
    if ($dirs.Registry) {
        # the Apps list (Settings > Apps): a per-user entry, no administrator rights needed
        New-Item -Path $UninstallKey -Force | Out-Null
        $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $vals = @{ DisplayName = 'Strata Turbo'; DisplayVersion = $version; Publisher = 'Asofwar'; InstallLocation = $homeDir
                   UninstallString = ('"' + $ps + '" -NoProfile -ExecutionPolicy Bypass -File "' + $launcher + '" uninstall')
                   URLInfoAbout = "https://github.com/$Repo"; DisplayIcon = $icon }
        foreach ($k in $vals.Keys) { New-ItemProperty -Path $UninstallKey -Name $k -Value $vals[$k] -PropertyType String -Force | Out-Null }
        New-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -Path $UninstallKey -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
    }
    Good (T 'Значок «Strata Turbo» есть на рабочем столе и в меню «Пуск»' 'The "Strata Turbo" icon is on the desktop and in the Start menu')
}

function Remove-Shortcuts {
    $dirs = Shortcut-Dirs
    $names = Shortcut-Names
    foreach ($n in @('Strata Turbo', $names.Start)) { Remove-Item -LiteralPath (Join-Path $dirs.Desktop ($n + '.lnk')) -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath (Join-Path $dirs.Programs 'Strata Turbo') -Recurse -Force -ErrorAction SilentlyContinue
    if ($dirs.Registry) { Remove-Item -LiteralPath $UninstallKey -Recurse -Force -ErrorAction SilentlyContinue }
}

# ------------------------------------------------------------------------------------------------ start, serve, stop
function Disable-QuickEdit {
    # a click into a console window with Quick Edit on pauses everything that writes to it, the server included
    try {
        if (-not ('StrataConsole' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class StrataConsole {
    [DllImport("kernel32.dll")] static extern IntPtr GetStdHandle(int n);
    [DllImport("kernel32.dll")] static extern bool GetConsoleMode(IntPtr h, out uint m);
    [DllImport("kernel32.dll")] static extern bool SetConsoleMode(IntPtr h, uint m);
    public static void NoQuickEdit() { IntPtr h = GetStdHandle(-10); uint m; if (GetConsoleMode(h, out m)) SetConsoleMode(h, (m & ~0x40u) | 0x80u); }
}
'@
        }
        [StrataConsole]::NoQuickEdit()
    } catch { }
}

function Pid-Stamp([int]$id) {
    # a process's id with its start time: a PID file left by a closed window can name another program after a restart
    try { return ('{0} {1}' -f $id, (Get-Process -Id $id -ErrorAction Stop).StartTime.ToFileTimeUtc()) } catch { return $null }
}

function Serving-Pid([string]$homeDir) {
    # the window that serves Strata Turbo now, or $null
    $pidFile = Join-Path $homeDir 'strata-turbo.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $line = ([string](Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)).Trim()
    $id = ($line -split ' ')[0] -as [int]
    if ($id -and $id -ne $PID -and (Pid-Stamp $id) -eq $line) { return $id }
    return $null
}

function Serve([string]$homeDir, $inst) {
    $pidFile = Join-Path $homeDir 'strata-turbo.pid'
    $flag = Join-Path $homeDir 'strata-turbo.stopping'      # Stop writes the PID of the window it stops into it
    $stamp = Pid-Stamp $PID
    Set-Content -LiteralPath $pidFile -Value $stamp -Encoding ASCII
    try { $Host.UI.RawUI.WindowTitle = 'Strata Turbo' } catch { }
    Disable-QuickEdit
    $url = 'http://127.0.0.1:{0}/' -f $inst.Port
    Say ''
    Say (T ' Strata Turbo запускается. Это занимает 1–3 минуты, в это время компьютер может притормаживать.' ' Strata Turbo is starting. It takes 1-3 minutes, and the PC can be slow meanwhile.') 'Cyan'
    Say (T ' Когда всё будет готово, чат сам откроется в браузере.' ' When it is ready, the chat opens in your browser by itself.') 'Cyan'
    Say ((T ' Адрес чата: {0}' ' The chat: {0}') -f $url) 'Cyan'
    Say (T ' Не закрывайте это окно, пока пользуетесь чатом: закрытое окно выключает Strata Turbo.' ' Keep this window open while you use the chat: closing it stops Strata Turbo.') 'Cyan'
    Say (T ' Ниже идут технические сообщения программы, их можно не читать.' ' The technical messages below can be ignored.') 'DarkGray'
    Say ''
    if ($env:STRATA_OPEN_URL_LOG) {   # (a test) the server's own browser start writes the address there too
        $env:BROWSER = 'powershell -NoProfile -Command Add-Content -LiteralPath ' + ($env:STRATA_OPEN_URL_LOG -replace '\\', '/') + ' -Value %s'
    }
    $code = 1
    try {
        $p = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\cmd.exe') -ArgumentList ('/d /s /c ""' + $inst.Bat + '" < nul"') `
                           -WorkingDirectory $inst.Dir -NoNewWindow -PassThru
        $null = $p.Handle
        $p.WaitForExit()
        $code = $p.ExitCode
    } finally {
        # only this window's own PID file: an update may already have started the next window
        $now = ([string](Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)).Trim()
        if ($now -eq $stamp) { Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue }
    }
    Say ''
    $stopped = ([string](Get-Content -LiteralPath $flag -ErrorAction SilentlyContinue | Select-Object -First 1)).Trim() -eq [string]$PID
    if ($stopped) {
        Remove-Item -LiteralPath $flag -ErrorAction SilentlyContinue
        Say (T 'Strata Turbo выключена. Включить снова — значок «Strata Turbo» на рабочем столе.' 'Strata Turbo is stopped. To start it again, use the "Strata Turbo" icon on the desktop.') 'Green'
        Start-Sleep -Seconds 3
        return 0
    }
    if ($code -eq 0) {
        Say (T 'Strata Turbo выключена.' 'Strata Turbo is stopped.') 'Green'
        Start-Sleep -Seconds 3
        return 0
    }
    Say (T 'Strata Turbo остановилась с ошибкой. Запустите её ещё раз значком «Strata Turbo» на рабочем столе.' 'Strata Turbo stopped with an error. Start it again with the "Strata Turbo" icon on the desktop.') 'Red'
    if ($inst.Log) { Say ((T 'Подробности записаны в файл: {0}' 'Details are in: {0}') -f $inst.Log) }
    Wait-Key
    return 1
}

function Start-Strata([string]$homeDir) {
    try { $Host.UI.RawUI.WindowTitle = 'Strata Turbo' } catch { }
    $inst = Installed-Versions $homeDir | Where-Object { $_.Bat } | Select-Object -First 1
    if (-not $inst) {
        Say (T 'Strata Turbo установлена не до конца. Запустите установщик Strata-Turbo-Install.cmd ещё раз.' 'Strata Turbo is not fully installed. Run Strata-Turbo-Install.cmd again.') 'Red'
        Wait-Key
        return 1
    }
    if (Server-Up $inst.Port) {
        Say (T 'Strata Turbo уже работает. Открываю чат в браузере.' 'Strata Turbo is already running. Opening the chat in your browser.') 'Green'
        Open-Chat $inst.Port
        Start-Sleep -Seconds 3
        return 0
    }
    if (Serving-Pid $homeDir) {
        Say (T 'Strata Turbo уже запускается в другом окне. Подождите: чат откроется сам.' 'Strata Turbo is already starting in another window. Please wait: the chat opens by itself.') 'Green'
        Start-Sleep -Seconds 5
        return 0
    }
    return (Serve $homeDir $inst)
}

function Stop-Strata([string]$homeDir, [bool]$quiet = $false) {
    # the servers and engines of this install's version folders, and nothing else: no process tree either (the browser
    # the server opened can be its child)
    $dirs = @(Installed-Versions $homeDir | ForEach-Object { $_.Dir.TrimEnd('\') + '\' })
    $mine = @()
    if ($dirs.Count) {
        $mine = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $p = $_
            ($p.Name -eq 'python.exe' -and $p.CommandLine -and $p.CommandLine -match 'server\.py' -and
             @($dirs | Where-Object { $p.CommandLine.IndexOf($_, [StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count) -or
            ($p.Name -like 'strata*.exe' -and $p.ExecutablePath -and @($dirs | Where-Object { Under $p.ExecutablePath $_ }).Count) })
    }
    if (-not $mine.Count) {
        if (-not $quiet) { Say (T 'Strata Turbo сейчас не запущена.' 'Strata Turbo is not running.') }
        return
    }
    $serving = Serving-Pid $homeDir
    if ($serving) { Set-Content -LiteralPath (Join-Path $homeDir 'strata-turbo.stopping') -Value $serving -Encoding ASCII }
    foreach ($p in $mine) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    for ($i = 0; $i -lt 30; $i++) {
        $left = @($mine | Where-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
        if (-not $left.Count -and -not ($serving -and (Get-Process -Id $serving -ErrorAction SilentlyContinue))) { break }
        Start-Sleep -Milliseconds 500
    }
    Say (T 'Strata Turbo выключена.' 'Strata Turbo is stopped.') 'Green'
}

# ------------------------------------------------------------------------------------------------ uninstall
function Ask-Yes([string]$question) {
    if ($env:STRATA_UNINSTALL_ANSWERS) {   # (tests) the answers, in order: y,n
        $a = @($env:STRATA_UNINSTALL_ANSWERS -split ',')
        $script:AnswerI = 1 + [int]$script:AnswerI
        $ans = if ($script:AnswerI -le $a.Count) { $a[$script:AnswerI - 1] } else { 'n' }
        Say ($question + ' ' + $ans)
        return (Is-Yes $ans)
    }
    try { if ([Console]::IsInputRedirected) { return $false } } catch { return $false }
    $ans = Read-Host ($question + (T ' (д = да, н = нет)' ' (y = yes, n = no)'))
    Log ($question + ' ' + $ans)
    return (Is-Yes $ans)
}

function Is-Yes([string]$ans) {
    $a = $ans.Trim().ToLower()
    # in Russian only д / да count: "l" / "lf" are д / да typed with the English layout, and "y" there is н (no) typed so
    if ($script:Ru) { return ($a -in @('д', 'да', 'l', 'lf')) }
    return ($a -in @('y', 'yes'))
}

function Folder-GiB([string]$path) {
    try { return ((Get-ChildItem -LiteralPath $path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB) } catch { return 0.0 }
}

function Other-Installs([string]$homeDir) {
    # Strata folders outside this install that setup remembers (they can share the model folder)
    $base = $env:APPDATA
    $f = if ($base) { Join-Path (Join-Path $base 'Strata') 'settings.json' } else { $null }
    if (-not $f -or -not (Test-Path -LiteralPath $f)) { return @() }
    try { $s = Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return @() }
    return @(@($s.installs) | Where-Object { $_ -and -not (Under ([string]$_) $homeDir) -and (Test-Path -LiteralPath (Join-Path ([string]$_) 'setup.py')) })
}

function Uninstall-Strata([string]$homeDir) {
    try { $Host.UI.RawUI.WindowTitle = (T 'Удаление Strata Turbo' 'Uninstall Strata Turbo') } catch { }
    # only a folder this installer made: never a drive's root, never a folder without its launcher
    $isRoot = $homeDir -and ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($homeDir)).TrimEnd('\') -ieq [IO.Path]::GetFullPath($homeDir).TrimEnd('\'))
    if (-not $homeDir -or $isRoot -or -not (Test-Path -LiteralPath (Join-Path $homeDir 'Strata-Turbo.ps1'))) {
        Say ((T 'Папка {0} не похожа на папку установки Strata Turbo: ничего не удалено.' '{0} does not look like a Strata Turbo install folder: nothing was removed.') -f $homeDir) 'Red'
        Wait-Key
        return 1
    }
    Say ((T 'Удаление Strata Turbo из папки {0}' 'Removing Strata Turbo from {0}') -f $homeDir) 'Cyan'
    if (-not (Ask-Yes (T 'Удалить Strata Turbo с этого компьютера?' 'Remove Strata Turbo from this PC?'))) {
        Say (T 'Ничего не удалено.' 'Nothing was removed.')
        Wait-Key
        return 0
    }
    Stop-Strata $homeDir $true
    $own = Join-Path $homeDir 'Strata-data'                  # the model folder an install here made
    $remembered = if ($env:STRATA_DATA_DIR) { $env:STRATA_DATA_DIR } else { Settings-DataDir }
    $deleteModel = $false
    if (Test-Path -LiteralPath $own) {
        $gb = Folder-GiB $own
        $size = if ($gb -ge 10) { '{0:N0}' -f $gb } else { '{0:N1}' -f $gb }
        $q = (T 'Удалить и скачанную модель ({0} ГБ)? Если её оставить, при новой установке не придётся качать её снова.' 'Delete the downloaded model too ({0} GB)? If you keep it, a new install does not download it again.') -f $size
        if (@(Other-Installs $homeDir).Count) { $q += T ' Эту папку используют и другие копии Strata на компьютере.' ' Other copies of Strata on this PC use that folder too.' }
        $deleteModel = Ask-Yes $q
    }
    Remove-Shortcuts
    Set-Location -LiteralPath $env:TEMP              # the shortcut started this in the install folder: leave it
    [Environment]::CurrentDirectory = $env:TEMP
    # what this installer (and install.ps1) put there, and nothing else
    $items = @(Installed-Versions $homeDir | ForEach-Object { $_.Dir })
    $items += @(Get-ChildItem -LiteralPath $homeDir -Directory -Force -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match $VersionDir -and $_.Name -match '\.(partial|broken-\d+)$' } | ForEach-Object { $_.FullName })
    $items += @('.download', 'Strata-Turbo.ps1', 'strata-turbo.ico', 'install.log', 'install-setup.log', 'strata-turbo.pid', 'strata-turbo.stopping' |
                ForEach-Object { Join-Path $homeDir $_ })
    if ($deleteModel) { $items += $own }
    foreach ($item in $items) {
        if (Test-Path -LiteralPath $item) { Remove-Item -LiteralPath $item -Recurse -Force -ErrorAction SilentlyContinue }
    }
    $rest = @(Get-ChildItem -LiteralPath $homeDir -Force -ErrorAction SilentlyContinue)
    if (-not $rest.Count) { Remove-Item -LiteralPath $homeDir -Force -ErrorAction SilentlyContinue }
    Say (T 'Strata Turbo удалена.' 'Strata Turbo is removed.') 'Green'
    if (Test-Path -LiteralPath $own) {
        Say ((T 'Модель осталась в папке {0}. Если она больше не нужна, удалите эту папку.' 'The model stays in {0}. If you no longer need it, delete that folder.') -f $own)
    }
    if ($remembered -and -not (Under $remembered $homeDir)) {
        Say ((T 'Модели Strata в папке {0} общие для всех копий Strata на компьютере: их я не трогаю.' 'Strata''s models in {0} are shared by every Strata on this PC: they are left alone.') -f $remembered)
    }
    $others = @($rest | Where-Object { $_.Name -ne 'Strata-data' })
    if ($others.Count) {
        Say ((T 'В папке {0} остались файлы, которые положил туда не установщик: их я не трогаю.' '{0} still has files the installer did not put there: they are left alone.') -f $homeDir)
    }
    Wait-Key
    return 0
}

# ------------------------------------------------------------------------------------------------ install / update
function Install-Strata {
    try { $Host.UI.RawUI.WindowTitle = (T 'Установка Strata Turbo' 'Strata Turbo setup') } catch { }
    $script:LogFile = Join-Path $env:TEMP 'strata-turbo-install.log'
    Set-Content -LiteralPath $script:LogFile -Value ('Strata Turbo easy installer, {0:yyyy-MM-dd HH:mm:ss}' -f (Get-Date)) -Encoding UTF8
    Say (T 'Strata Turbo — установка' 'Strata Turbo setup') 'Cyan'
    # one install at a time (a double-clicked installer started twice would share its download and unpack folders)
    $script:Mutex = New-Object Threading.Mutex($false, 'Local\StrataTurboEasyInstall')
    $own = $false
    try { $own = $script:Mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $own = $true }
    if (-not $own) { Stop-Easy (T 'Установка Strata Turbo уже идёт в другом окне.' 'Strata Turbo setup is already running in another window.') }
    Say (T 'Установщик сам проверит компьютер, скачает и настроит всё нужное. Отвечать на вопросы не нужно.' 'The installer checks this PC, then downloads and sets up everything by itself. There are no questions to answer.')

    Step 1 (T 'Проверяю компьютер' 'Checking this PC')
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { Stop-Easy 'Windows only.' }
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    if ($arch -ne 'AMD64') { Check-Failed ((T 'Нужна 64-разрядная Windows на процессоре Intel или AMD (у этого компьютера: {0}).' 'Strata Turbo needs 64-bit Windows on an Intel or AMD processor (this PC: {0}).') -f $arch) }
    Check-Gpu
    Check-Ram
    $plan = Plan-Folders
    $homeDir = $plan.Home
    Good ((T 'Место на диске: хватает (нужно около {0:N0} ГБ), папка установки {1}' 'Disk space: enough (about {0:N0} GB needed), install folder {1}') -f [Math]::Ceiling($plan.Need), $homeDir)
    $rel = Find-Release
    if (-not $env:STRATA_RELEASE_DIR) { Good (T 'Интернет: есть' 'Internet: works') }
    if (-not $plan.ModelPresent) {
        $hf = if ($env:HF_ENDPOINT) { $env:HF_ENDPOINT.TrimEnd('/') } else { 'https://huggingface.co' }
        if (-not (Http-Ok ($hf + '/api/models/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP'))) { No-Internet ($hf -replace '^https?://', '') }
        Good ((T 'Сайт с моделью ({0}) открывается' 'The model''s site ({0}) answers') -f ($hf -replace '^https?://', ''))
    }
    if (-not (Http-Ok 'https://pypi.org/simple/numpy/')) { No-Internet 'pypi.org' }
    if ($env:STRATA_CHECK_ONLY -eq '1') {
        Say ''
        Say ((T 'Проверка пройдена: на этот компьютер можно установить Strata Turbo {0}.' 'All checks passed: Strata Turbo {0} can be installed on this PC.') -f $rel.Version) 'Green'
        return 0
    }
    New-Item -ItemType Directory -Force -Path $homeDir | Out-Null
    $log = Join-Path $homeDir 'install.log'
    try {
        Get-Content -LiteralPath $script:LogFile -Raw -Encoding UTF8 | Set-Content -LiteralPath $log -Encoding UTF8
        Remove-Item -LiteralPath $script:LogFile -ErrorAction SilentlyContinue
        $script:LogFile = $log
    } catch { }

    $versions = @(Installed-Versions $homeDir)
    $dest = Join-Path $homeDir $rel.Version
    $current = $versions | Where-Object { $_.Name -eq $rel.Version } | Select-Object -First 1
    $older = $versions | Where-Object { $_.Name -ne $rel.Version -and $_.Ready } | Select-Object -First 1

    Step 2 ((T 'Скачиваю программу Strata Turbo {0}' 'Downloading Strata Turbo {0}') -f $rel.Version)
    if ($current) { Good ((T 'Версия {0} — самая новая, и она уже скачана' 'Version {0} is the newest, and it is already downloaded') -f $rel.Version) }
    else {
        if ($older) { Say ((T '   Обновление: сейчас установлена версия {0}, новая — {1}. Скачанная модель останется, второй раз её качать не нужно.' '   Update: version {0} is installed, the new one is {1}. The downloaded model is kept and not downloaded again.') -f $older.Name, $rel.Version) }
        if (Test-Path -LiteralPath $dest) {   # a folder of that name that is not a whole version: kept aside, not deleted
            Rename-Item -LiteralPath $dest -NewName ('{0}.broken-{1:yyyyMMddHHmmss}' -f $rel.Version, (Get-Date))
        }
        Get-App $rel $homeDir $dest $plan.ModelPresent
    }

    $inst = Installed-Versions $homeDir | Where-Object { $_.Name -eq $rel.Version } | Select-Object -First 1
    if ($inst -and $inst.Ready -and $inst.Tiel -and -not $env:STRATA_SETUP_ARGS) {   # (another model set up here by hand: Cyber-Tiel is set up beside it)
        Step 3 (T 'Устанавливаю программу и компоненты' 'Installing the app and its components')
        Good ((T 'Strata Turbo {0} уже установлена и настроена' 'Strata Turbo {0} is already installed and set up') -f $rel.Version)
        Step 4 (T 'Скачиваю модель' 'Downloading the model')
        Good (T 'Модель уже скачана' 'The model is already downloaded')
    } else {
        $setupArgs = @('--setup', '--family', 'cyber-tiel', '--yes', '--no-start')
        if ($script:Ru) { $setupArgs += @('--draft-vocab', 'cyrillic') }   # Russian answers decode ~30% faster (setup's --help)
        if ($env:STRATA_DATA_DIR) { $setupArgs += @('--data-dir', $env:STRATA_DATA_DIR) }
        # the port: the earlier version's, else 8080, else the next free one (another program may hold 8080)
        $port = if ($older) { $older.Port } else { $DefaultPort }
        if (-not $older -and -not (Port-Free $port)) {
            for ($q = 8081; $q -le 8099; $q++) { if (Port-Free $q) { $port = $q; break } }
        }
        if ($port -ne $DefaultPort) { $setupArgs += @('--port', [string]$port) }
        if ($env:STRATA_SETUP_ARGS) { $setupArgs += @(-split $env:STRATA_SETUP_ARGS) }
        Run-Setup $dest $setupArgs $plan.ModelPresent
        try { $Host.UI.RawUI.WindowTitle = (T 'Установка Strata Turbo' 'Strata Turbo setup') } catch { }
        Good (T 'Модель скачана и настроена' 'The model is downloaded and set up')
        $inst = Installed-Versions $homeDir | Where-Object { $_.Name -eq $rel.Version } | Select-Object -First 1
        if (-not $inst -or -not $inst.Bat) { Stop-Easy (T 'Программа установки не создала файл запуска.' 'Setup did not write the start script.') }
    }

    Step 5 (T 'Создаю значки и запускаю' 'Creating the icons and starting')
    Install-Shortcuts $homeDir $inst.Dir $rel.Version
    Say ''
    Say (T 'Готово! Strata Turbo установлена.' 'Done! Strata Turbo is installed.') 'Green'
    Say (T 'В следующий раз запускайте её значком «Strata Turbo» на рабочем столе.' 'Next time, start it with the "Strata Turbo" icon on the desktop.')
    if ($env:STRATA_NO_START -eq '1') { return 0 }
    # an earlier version still running: stopped now, so the new one gets the port and the graphics memory
    Stop-Strata $homeDir $true
    try { $script:Mutex.ReleaseMutex() } catch { }   # serving is not installing: a later run may update meanwhile
    return (Serve $homeDir $inst)
}

# ------------------------------------------------------------------------------------------------ main
$homeOfThis = if ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { $null }
$rc = 1
try {
    switch ($Mode.ToLower()) {
        'install' { $rc = Install-Strata }
        'start' { $rc = Start-Strata $homeOfThis }
        'stop' { Stop-Strata $homeOfThis; Start-Sleep -Seconds 2; $rc = 0 }
        'uninstall' { $rc = Uninstall-Strata $homeOfThis }
        default { Write-Host "usage: Strata-Turbo.ps1 [start|stop|uninstall]"; $rc = 2 }
    }
    $rc = [int](@($rc)[-1])
} catch {
    if ($_.Exception.Message -ne 'strata-easy-stop') {
        Say ''
        Say ((T 'Установка остановлена из-за непредвиденной ошибки: {0}' 'Setup stopped on an unexpected error: {0}') -f $_.Exception.Message) 'Red'
        Log ($_ | Out-String)
        if ($script:LogFile) { Say ((T 'Подробности записаны в файл: {0}' 'Details are in: {0}') -f $script:LogFile) }
    }
    Wait-Key
    $rc = 1
}
exit $rc
