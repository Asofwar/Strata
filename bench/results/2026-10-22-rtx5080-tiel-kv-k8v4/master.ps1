# One downtime of the user's server on 8096: engine arms in --serve mode with stdin request files (int8 K/V vs k8v4);
# the server is restarted in any case at the end.  Stop early: create master.stop in this folder.
# Based on the harness of sessions 38cbbe6e (mystifying-torvalds) and 9f9c99df (prefill-200k).
param([switch]$DryRun, [string]$Arms = "ctl,k8,ctl,k8,klc,klk,klc", [string]$Tag = "d1",
      [string]$Exe = "E:\Projects\Strata-main\build\strata.exe")
$S = Split-Path -Parent $MyInvocation.MyCommand.Path
$TL = Join-Path $S "timeline.log"
$stopf = Join-Path $S "master.stop"
$lock = "C:\Users\Admin\AppData\Local\Temp\strata-gpu.lock"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class NoThrottle {
  [StructLayout(LayoutKind.Sequential)] public struct PT { public uint Version; public uint ControlMask; public uint StateMask; }
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool SetProcessInformation(IntPtr h, int cls, ref PT info, uint size);
  public static bool Off(IntPtr h) {
    PT i = new PT(); i.Version = 1; i.ControlMask = 0x5; i.StateMask = 0;
    if (SetProcessInformation(h, 4, ref i, (uint) Marshal.SizeOf(i))) return true;
    i.ControlMask = 0x1; return SetProcessInformation(h, 4, ref i, (uint) Marshal.SizeOf(i));
  }
}
"@

function Note($m) { $l = "$(Get-Date -Format 'HH:mm:ss') [$Tag] $m"; $l | Out-File -Append -Encoding utf8 $TL; $l }
$env:PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.4\bin\x64;C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.4\bin;" + $env:PATH
$cfg = Get-Content "E:\Projects\Strata-integrate\strata-tiel-main.json" -Raw | ConvertFrom-Json
$baseEnv = @{}
foreach ($p in $cfg.env.PSObject.Properties) { $baseEnv[$p.Name] = [string]$p.Value }
# the live config's args minus the conversation disk (its directory is the user's)
$baseArgs = [System.Collections.ArrayList]@()
$skip = 0
foreach ($a in $cfg.args) {
  if ($skip -gt 0) { $skip--; continue }
  if ($a -in @("--conversation-disk-dir", "--conversation-disk-mib", "--conversation-disk-persist")) { $skip = 1; continue }
  [void]$baseArgs.Add([string]$a)
}
$armEnvKeys = @("STRATA_DECODE_TIMING", "STRATA_LOGPOS", "STRATA_LOGPOS_TOPK")

# arm = @{ set = @{flag = value or $null to drop}; add = @(extra args); env = @{}; req = file; timeout = s }
$kl = @("--short-read", "1024", "--prompt-cache", "3")
$A = [ordered]@{
  ctl = @{ env = @{ STRATA_DECODE_TIMING = "1" }; req = "seq_speed.txt"; timeout = 1200 }
  k8  = @{ set = @{ "--kv" = "k8v4" }; env = @{ STRATA_DECODE_TIMING = "1" }; req = "seq_speed.txt"; timeout = 1800 }
  klc = @{ env = @{ STRATA_LOGPOS = "LP:klc.lp"; STRATA_LOGPOS_TOPK = "40" }; req = "seq_kl.txt"; add = $kl; timeout = 900 }
  klk = @{ set = @{ "--kv" = "k8v4" }; env = @{ STRATA_LOGPOS = "LP:klk.lp"; STRATA_LOGPOS_TOPK = "40" }; req = "seq_kl.txt"; add = $kl; timeout = 1500 }
}
function ArmArgs($arm) {
  $out = [System.Collections.ArrayList]@()
  $i = 0
  while ($i -lt $baseArgs.Count) {
    $f = $baseArgs[$i]
    $hasVal = ($i + 1 -lt $baseArgs.Count) -and -not $baseArgs[$i + 1].StartsWith("--")
    if ($arm["set"] -and $arm["set"].ContainsKey($f)) {
      $v = $arm["set"][$f]
      if ($null -ne $v) { [void]$out.Add($f); [void]$out.Add($v) }
      $i += $(if ($hasVal) { 2 } else { 1 }); continue
    }
    [void]$out.Add($f); if ($hasVal) { [void]$out.Add($baseArgs[$i + 1]) }
    $i += $(if ($hasVal) { 2 } else { 1 })
  }
  if ($arm["add"]) { foreach ($x in $arm["add"]) { [void]$out.Add($x) } }
  [void]$out.Add("--serve")
  return $out
}
function RunArm($name) {
  if (Test-Path $stopf) { Note "skip $name (stop-file)"; return }
  $arm = $A[$name]
  if ($null -eq $arm) { throw "unknown arm $name" }
  $file = "$Tag-$name"
  $k = 2
  while (Test-Path (Join-Path $S "$file.log")) { $file = "$Tag-$name" + "_$k"; $k++ }
  foreach ($k in @($baseEnv.Keys)) { Set-Item "env:$k" $baseEnv[$k] }
  foreach ($k in $armEnvKeys) { if (-not $baseEnv.ContainsKey($k)) { Remove-Item "env:$k" -ErrorAction SilentlyContinue } }
  foreach ($k in $arm["env"].Keys) {
    $v = [string]$arm["env"][$k]
    if ($v.StartsWith("LP:")) { $v = Join-Path $S ($file + ".lp"); Remove-Item $v -ErrorAction SilentlyContinue }
    Set-Item "env:$k" $v
  }
  $a = ArmArgs $arm
  $arm["req"] | Out-File -Encoding utf8 (Join-Path $S "$file.req.txt")
  ($a -join " ") | Out-File -Encoding utf8 (Join-Path $S "$file.cmd.txt")
  (Get-ChildItem env: | Where-Object { $_.Name -like 'STRATA_*' } | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join " " | Out-File -Encoding utf8 (Join-Path $S "$file.env.txt")
  Note "start $file ($($arm['req']))"
  $p = Start-Process -FilePath $Exe -ArgumentList ($a | ForEach-Object { '"' + $_ + '"' }) -WorkingDirectory "E:\Projects\Strata-main" `
       -RedirectStandardInput (Join-Path $S $arm["req"]) -RedirectStandardError (Join-Path $S "$file.log") `
       -RedirectStandardOutput (Join-Path $S "$file.out") -NoNewWindow -PassThru
  # as serve/winjob.py does for the server's engine (#691): no EcoQoS, or Windows may slow a background engine
  $nt = [NoThrottle]::Off($p.Handle)
  Note "$file pid $($p.Id) no-throttle=$nt"
  $deadline = (Get-Date).AddSeconds($arm["timeout"])
  while (-not $p.WaitForExit(5000)) {
    if ((Get-Date) -gt $deadline) { $p.Kill(); Note "$file TIMEOUT killed"; break }
    if (Test-Path $stopf) { $p.Kill(); Note "$file killed (stop-file)"; break }
  }
  $p.WaitForExit()
  Note "end $file exit=$($p.ExitCode)"
}

if ($DryRun) { foreach ($n in ($Arms -split ",")) { $m = $A[$n]; "$n : " + ((ArmArgs $m) -join " ") + " ENV " + (($m["env"].Keys | ForEach-Object { "$_=" + $m["env"][$_] }) -join " ") + " REQ " + $m["req"] }; exit 0 }
# ---- the GPU lock
while ($true) {
  if (Test-Path $stopf) { Note "stop-file before the lock"; exit 0 }
  try { New-Item -ItemType Directory -Path $lock -ErrorAction Stop | Out-Null; break } catch { Start-Sleep 15 }
}
"agitated-matsumoto (kv int8 vs k8v4 at 130K/200K, server 8096 stopped) $(Get-Date -Format o)" | Out-File -Encoding utf8 (Join-Path $lock "owner.txt")
Note "lock taken"
try {
  # ---- stop the user's server (when idle)
  Note "waiting for the server to be idle"
  $idle = 0
  while ($idle -lt 20) {
    if (Test-Path $stopf) { Note "stop-file before downtime"; exit 0 }
    try { $st = Invoke-RestMethod -Uri 'http://127.0.0.1:8096/status' -TimeoutSec 5 } catch { $st = $null }
    if ($null -eq $st -or (-not $st.busy -and $st.queued -eq 0)) { $idle += 5 } else { $idle = 0 }
    Start-Sleep 5
  }
  Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -like '*run-tiel-main.bat*' } |
    ForEach-Object { taskkill /PID $_.ProcessId /T /F 2>&1 | Out-Null }
  Start-Sleep 5
  $left = Get-Process strata -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*Strata-main*' }
  if ($left) { $left | ForEach-Object { Stop-Process -Id $_.Id -Force }; Start-Sleep 3 }
  Note "DOWNTIME START (server stopped)"
  $smi = Start-Process -FilePath "nvidia-smi.exe" -ArgumentList "--query-gpu=timestamp,memory.used,clocks.sm,temperature.gpu,power.draw --format=csv,noheader -l 1" `
         -RedirectStandardOutput (Join-Path $S "$Tag-smi.log") -NoNewWindow -PassThru
  try {
    foreach ($n in ($Arms -split ",")) { RunArm $n }
  } finally {
    try { $smi.Kill() } catch {}
    Note "restarting the server"
    Start-Process -FilePath 'E:\Projects\Strata-integrate\run-tiel-main.bat' -WorkingDirectory 'E:\Projects\Strata-integrate'
    $up = $false
    for ($i = 0; $i -lt 120; $i++) {
      Start-Sleep 5
      try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8096/v1/models' -TimeoutSec 5; if ($h.data[0].status.value -eq 'loaded') { $up = $true; break } } catch {}
    }
    if ($up) { Note "DOWNTIME END (server loaded)" } else { Note "server did not report loaded in 10 min" }
  }
} finally {
  Remove-Item -Recurse -Force $lock -ErrorAction SilentlyContinue
  Note "lock released"
}
