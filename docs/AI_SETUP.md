# Installing Strata for a user (instructions for AI agents)

This page is written for an AI coding assistant (Claude Code, Cursor, Codex, GitHub Copilot, ...) that a user asked to
set up Strata on their PC. Strata runs a large mixture-of-experts model locally on one NVIDIA or AMD graphics card plus
system RAM, and serves an OpenAI- and Anthropic-compatible API on `http://127.0.0.1:8080`. The human-oriented version of
everything below is [INSTALL.md](INSTALL.md).

This is **Asofwar's fork** of Strata, and everything is installed from the fork: https://github.com/Asofwar/Strata. The
fork's releases carry a ready engine for **Windows with an NVIDIA RTX 20 series card or newer (driver 580 or newer)**. On
any other system the engine is built from source, which the fork has not tested (Linux, Mac, AMD, Intel). The fork does not
ship the desktop app installers, the Terminal's installer or its signed update feed, so **do not use `strata launch` or
`strata update`**: you install with setup (`START-HERE.bat` on Windows, `./setup.sh` on Linux and Mac).

Work through the steps in order. Tell the user what you are doing in plain words; they may not be technical.

## 0. Ground rules

- **Never expose the server without an API key.** Keep the default (the server listens on `127.0.0.1` only). Only if the
  user asks for access from other devices, pass `--host 0.0.0.0 --api-key <long random key>` together, and give the user the
  key. Never put a tunnel or port forward in front of a server without a key.
- Do not change the user's system beyond what setup does. It installs Python 3.12 for the user if there is none (no
  administrator rights), a private environment in `.venv/` inside the Strata folder, the engine, the model and the draft
  layer. It does not install drivers. If no ready engine fits the card it offers to install build tools and compile
  (it asks first). Ask the user before installing drivers.
- The model download is large: ~70 GB for the Flash-Next sizes (94 GB for Unsloth's UD-IQ4_XS, 111 GB for UD-Q4_K_XL),
  18-19 GB for the fork's Cyber-Tiel and Ornith files. Confirm the user is fine with that before you start, especially on
  a metered connection.
- The first setup is long-running (an hour or more on a slow connection). Run it in the background or with a long
  timeout and poll its output; do not kill it because it is quiet for a while. It is resumable: running the same command
  again continues where it stopped.
- Piping a script from the internet into a shell runs code you have not read. The one-line installers are for people;
  you get the code with `git clone` or the zip (step 2), which you can read first.

## 1. Check the PC

Requirements (details: [INSTALL.md](INSTALL.md#what-you-need)):

- **GPU:** NVIDIA RTX 20, 30, 40 or 50 series, or AMD Radeon RX 7900 XT / XTX, RX 7800 XT / 7700 XT, RX 9060 XT,
  RX 9070 / 9070 XT, Radeon AI PRO R9700, RX 6800 / 6900 series; 12 GB of VRAM or more (an NVIDIA card with 8 GB runs,
  slowly). GTX 10 series and older, and integrated GPUs, are not supported; Pascal / Volta cards (P40, V100) and some
  older AMD cards have experimental paths the user opts into ([OLDER_GPUS.md](OLDER_GPUS.md)). A **Mac** needs Apple
  Silicon (M1 or newer), macOS 15 or newer and 16 GB of memory or more ([MAC.md](MAC.md)). The fork's own models
  (Cyber-Tiel, Ornith) are measured on a 16 GB NVIDIA card. For AMD, Intel and Mac say that the fork has not tested them.
- **Driver:** NVIDIA 580 or newer. AMD on Linux: the kernel's amdgpu driver; on Windows: a current AMD Adrenalin
  driver. If the driver is missing or too old, tell the user to update it (NVIDIA App / nvidia.com/drivers, or AMD
  Software) and restart; do not install drivers yourself unless they ask.
- **RAM:** 32 GB or more (see step 3). **Disk:** ~80 GB free, ideally on an NVMe SSD. **CPU:** x86-64 with AVX2.
  Without AVX2 (Xeon E5 v1/v2 and older) the ready-made engine refuses to start; the route from source builds an
  experimental and slow engine on the PC (10-20 minutes): tell the user that before starting
  ([INSTALL.md](INSTALL.md#older-cpus-experimental)).
- **OS:** Windows 10/11, Linux x86-64 (Ubuntu 22.04/24.04 and Debian 12/13 are fully automatic), or macOS on Apple Silicon.

To check by hand:

| What | Windows (PowerShell) | Linux | Mac |
| --- | --- | --- | --- |
| OS | `[Environment]::OSVersion` | `cat /etc/os-release` | `sw_vers` |
| NVIDIA GPU, VRAM, driver | `nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv` | the same | - |
| AMD GPU | `Get-CimInstance Win32_VideoController \| Select-Object Name, AdapterRAM` (AdapterRAM is capped at 4 GB; trust the model name) | `lspci \| grep -i -E 'vga\|display'`; VRAM: `cat /sys/class/drm/card*/device/mem_info_vram_total` (bytes); `rocm-smi` only if ROCm is installed | - |
| RAM | `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB` | `free -g` | `sysctl -n hw.memsize` (bytes) |
| Free disk | `Get-PSDrive -PSProvider FileSystem` | `df -h .` | `df -h ~` |

If the PC does not meet them, say which part is missing and stop.

## 2. Get the fork

Clone it (or, without git, download https://github.com/Asofwar/Strata/archive/refs/heads/main.zip and unzip it):

```
git clone https://github.com/Asofwar/Strata.git
```

Pick a drive with enough free space and a folder without spaces in its path. The model files go to a `Strata-data` folder
next to the Strata folder (or to `--data-dir <path>`, for example on another drive).

- **Windows with an NVIDIA RTX 20 series card or newer:** setup downloads the ready engine (`strata-windows-x64.zip`)
  from the fork's [latest release](https://github.com/Asofwar/Strata/releases/latest) and checks its SHA-256, so nothing
  is compiled. The release also has `Strata-Turbo-<version>-windows-cuda13.zip`, the fork's code and that engine in one
  zip; unzip it instead of cloning if you prefer.
- **Linux, Mac, AMD, Intel:** setup builds the engine from source on the PC. The fork has not tested these.
- The one-line installers (`irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex`,
  `curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh`) get the same files and run
  `START-HERE.bat` or `./setup.sh`, which ask their questions in the window. You cannot answer those, so use the commands
  in step 4 with flags.

Setup's own check prints the GPU(s), driver, RAM, CPU, free disk and whether this PC can run Strata, and installs nothing
except Python and the `.venv` it needs to run:

```
Windows:  START-HERE.bat --check
Linux:    ./setup.sh --check
```

## 3. Pick the model

Pick by the PC and the use. Ask the user whether they mainly want it for code.

| PC | Flags | Notes |
| --- | --- | --- |
| NVIDIA RTX with 16 GB, 32 GB of RAM or more, for coding agents | `--family cyber-tiel` (or `--family ornith-abl`) | the fork's models: Cyber-Tiel-Coder-35B-A3B (UD-IQ4_XS, the recommended size) and Huihui-Ornith-1.5-35B-A3B-abliterated (IQ4_XS), with the fork's long-context settings. Add `--draft-vocab cyrillic` if the user chats in Russian. No pictures. [FORK.ru.md](FORK.ru.md) (Russian), [QWEN36_PACK.md](QWEN36_PACK.md) |
| 32 GB of RAM | `--family coder --model IQ1_M` | the Qwen3.8 Coder, for code; with a 24 GB card Q2_0 and IQ2_XS also run (setup picks the low-RAM mode) |
| 48 GB | `--model IQ2_XS` | or `Q2_0` (fastest) |
| 64 GB | `--model IQ2_XS` (recommended) | `IQ3_XXS` / `IQ3_S` are slower and a bit better |
| 96 GB+ | `--model IQ3_S` | `--family unsloth --model UD-IQ4_XS` (~4-bit, 94 GB, part of the experts read from the SSD under ~80 GB of RAM); `UD-Q4_K_XL` is experimental: NVIDIA only, NVMe SSD, 7-8.5 tokens/s on 64 GB |

`--family swift` (Swift 1.5, a fine-tune of Qwen3.8 that thinks shorter; sizes IQ2_XS, IQ3_XXS, IQ3_S) is the alternative
to `qwen`. A model name is case sensitive in setup's flags: use the spelling above. More: [MODELS.md](MODELS.md). Without
`--family` and `--model`, `--yes` takes the recommended answer for this PC.

## 4. Set up, without questions

Run setup from the Strata folder (Windows: in `cmd`, or `cmd /c START-HERE.bat ...` from PowerShell):

```
Windows:  START-HERE.bat --yes --family cyber-tiel --no-start
Linux:    ./setup.sh --yes --family cyber-tiel --no-start
```

or, for a Flash-Next size:

```
Windows:  START-HERE.bat --yes --family qwen --model IQ2_XS --vision yes --no-start
Linux:    ./setup.sh --yes --family qwen --model IQ2_XS --vision yes --no-start
```

The flags (all of them: `START-HERE.bat --help`):

| Flag | Meaning |
| --- | --- |
| `--yes` | take the recommended answer to every question (no prompts) |
| `--family cyber-tiel\|ornith-abl\|qwen\|swift\|coder\|unsloth` | the model version (the first two are the fork's) |
| `--model Q2_0\|IQ2_XS\|IQ3_XXS\|IQ3_S\|IQ1_M\|UD-IQ4_XS\|UD-Q4_K_XL` | the size (the Coder is IQ1_M, Unsloth UD-IQ4_XS or UD-Q4_K_XL; the fork's families have their own sizes, the recommended one is the default) |
| `--context N` | context in tokens; default by VRAM: 32768 under 14 GB, 65536 under 20 GB, else 131072 |
| `--vision yes\|no\|gpu\|cpu` | read pictures. Pass `yes` to get the best reader for the card (the CPU under 24 GB, the GPU from 24 GB, any make); `no` turns them off. Not available for the fork's families |
| `--draft-vocab cyrillic` | for the fork's families: draft only tokens that suit Russian |
| `--gpu N` / `--gpus 0,1` / `--gpus all` | one card, or several sharing the model (default: the card with the most VRAM) |
| `--backend cuda\|hip` | NVIDIA or AMD engine; chosen by itself on a PC with only one kind of card |
| `--parallel N` | requests answered at the same time ([BATCHING.md](BATCHING.md)) |
| `--data-dir PATH` | where new model files go. Nothing is moved unless you add `--move-data`; the saved default folder changes only with `--move-data` or `--set-default-data-dir` |
| `--port N` | the server port (default 8080) |
| `--host H --api-key K` | listen beyond this PC; only together with a key |
| `--no-start` | install only, do not start the server |
| `--setup` | install another model or change settings of an installed one |
| `--check` | only check the PC |

`--no-start` is recommended for agents: the server runs in the foreground until its window is closed, which would block your
shell. Start it separately (step 6).

Notes:
- **Linux:** setup uses `sudo apt` (or dnf/pacman) to install Python with venv if it is missing, and on AMD may need
  `build-essential` and `git`. You cannot type the user's password: if a `sudo` step is needed, ask the user to run it
  (e.g. `sudo apt install python3-venv build-essential git`) and then rerun setup.
- **AMD on Linux:** setup installs ROCm into `.venv` (~10 GB, no sudo) unless a system ROCm 7 exists, and compiles the
  engine for the card (10-20 minutes, once). The fork has not tested it.
- **AMD on Windows:** setup downloads upstream's AMD engine (~550 MB, ROCm included) when the release has one. The fork has
  not tested it ([AMD_HIP.md](AMD_HIP.md)); ask the user to report how it runs.
- **NVIDIA with no ready-made engine for the card:** setup offers to install build tools and compile (20-40 minutes);
  `--yes` accepts.
- **Mac:** `./setup.sh` builds the Metal engine on the Mac (needs Apple's Command Line Tools, `xcode-select --install`).
  The fork has not tested it.
- **Do not run `strata update`** (or any `--feed` that points at upstream's releases): it would install upstream's engine,
  which has no pack path for the fork's models.

## 5. While it downloads, tell the user

- It downloads the model from Hugging Face (~70 GB for the Flash-Next sizes, 18-19 GB for the fork's); how long depends on
  their connection (at 100 Mbit/s roughly 1.5-2 hours for 70 GB). It can be stopped and continues where it left off.
- Then it prepares the model for their PC (a few minutes).
- **When the model starts, the PC can be slow or stop responding for 1-3 minutes** (longest the first time): Strata
  loads 35-55 GB into RAM and locks part of it for the graphics card. That is normal; they should not close the window.
- Nothing leaves their PC: the model runs locally.

## 6. Start the server

Setup prints the start script it wrote (`start script: run-<model>.bat`). The name is the family tag plus the size, lower
case: `run-iq2_xs`, `run-swift-iq2_xs`, `run-coder-iq1_m`, `run-unsloth-ud-iq4_xs`, and the same pattern for the fork's
families (their tags are `cybertiel-` and `ornithabl-`). Start it so that it keeps running:

```
Windows (PowerShell):  Start-Process -FilePath ".\run-iq2_xs.bat"            (opens its own window)
Linux:                 nohup ./run-iq2_xs.sh > strata-server.out 2>&1 &
```

The engine log is `strata-<model>.log` in the Strata folder. Closing the window (or killing the process) stops the model.
Later starts: `START-HERE.bat` (or `./setup.sh`) starts it right away and downloads nothing twice. No browser opens by
itself on a start from a script.

## 7. Verify

The HTTP server answers once the model is loaded (30-90 s on later starts, a few minutes the first time). Poll:

```
curl http://127.0.0.1:8080/health
```

It returns `{"status": "ok", "model": ..., "max_context": ..., "images": ..., "api_key": ..., "loaded": true, ...}`.
Then:

```
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\": \"strata\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hello in five words.\"}], \"max_tokens\": 64, \"reasoning_effort\": \"none\"}"
```

With an API key, add `-H "Authorization: Bearer <key>"`.

## 8. Connect the user's apps

- **Browser:** `http://127.0.0.1:8080` - Chat, a live Monitor, and About (settings and addresses).
- **Any OpenAI-compatible app or agent:** base URL `http://127.0.0.1:8080/v1`, any API key (or the configured one),
  any model name.
- **Anthropic-compatible apps:** base URL `http://127.0.0.1:8080`, without `/v1`. Those apps add `/v1/messages`
  themselves.
- **Codex CLI and other Responses API apps:** `http://127.0.0.1:8080/v1/responses` (stateless; Codex's
  `config.toml`: [DETAILS.md](DETAILS.md#the-responses-api-and-codex-cli)).
- **Claude Code:** `ANTHROPIC_BASE_URL=http://127.0.0.1:8080`, `ANTHROPIC_MODEL` set to a Claude model name it knows
  (Strata ignores the name), and any `ANTHROPIC_AUTH_TOKEN` (or the configured key).
- **Thinking level:** `"reasoning_effort": "none" | "low" | "medium" | "high"` (default high).
- Strata answers one request at a time; `--parallel N` in setup decodes up to N together
  ([BATCHING.md](BATCHING.md)). API details: [DETAILS.md](DETAILS.md#using-it).

## 9. When something fails

| Symptom | What to do |
| --- | --- |
| `the NVIDIA driver is too old` | The user updates the driver (NVIDIA App or nvidia.com/drivers) and restarts; run the command again. |
| Download or install stopped | Run the same command again; it continues. |
| No ready engine for this PC, or the engine download failed | Check the internet and the card against the list in step 1, run setup again. On a card or system without a ready engine setup offers to build one; on AMD, Intel and Mac say that the fork has not tested it. Do not run `strata update`. |
| `port 8080 is already in use` | Strata is already running (check `/health`), or use `--port 8081`. |
| Very slow, disk busy, or "the engine stopped unexpectedly" | Not enough free RAM: close programs, or choose a smaller size (`Q2_0` or `IQ2_XS`). |
| `ExpertCache: cudaMalloc(...) failed: out of memory` with free VRAM (Windows) | The page file is off or tiny: set a fixed size (Custom size, the same initial and maximum size, e.g. 65536 MB) and restart; a page file Windows grows on demand ("System managed") may not grow in time (#60). |
| `prompt ... exceeds the context` | Run setup again with a bigger `--context` (`START-HERE.bat --setup --context 131072`). |
| No AMD GPU found (Linux) | The amdgpu driver lists no GPU; check the card and driver. Integrated GPUs are not supported. |

More: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and the [full table](DETAILS.md#troubleshooting). If it still fails,
collect the output of `START-HERE.bat --check` and the engine log named in the error message, and suggest an issue at
https://github.com/Asofwar/Strata/issues.

## Alternative: the MCP server

Strata also has an MCP server, so an AI tool can check, install, start and stop Strata through tool calls
(`strata_status`, `strata_models`, `strata_install`, `strata_start`, `strata_stop`, `strata_logs`) instead of the
shell commands above. It runs setup underneath. See [MCP_SERVER.md](MCP_SERVER.md).
