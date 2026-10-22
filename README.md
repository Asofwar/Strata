<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a> · <a href="README.ru.md">Русский</a></p>

<h2 align="center">Asofwar's fork: coding agents with 262K context on a 16 GB card</h2>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=fork%20release" alt="Fork release"></a>
  <a href="https://github.com/Niko1221/Strata"><img src="https://img.shields.io/badge/upstream-Niko1221%2FStrata-blue" alt="Upstream: Niko1221/Strata"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Fork docs"></a>
</p>

This fork of [Niko1221/Strata](https://github.com/Niko1221/Strata) runs the Qwen3.6-35B-A3B models Cyber-Tiel-Coder
and Ornith on Strata's main engine from a pack: int8 K/V (11 KiB per token instead of 44), MTP drafts and the fork's
own long-context kernels, so a coding agent gets up to 262K of context on one 16 GB card.

Measured on an RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS with the settings setup
writes (2026-10-21/22):

| Context | Reading the prompt from scratch | Writing |
| ---: | ---: | ---: |
| 130K | 25.7 s | 146-167 tokens/s |
| 200K | 49.4 s | 161-171 tokens/s |

**What the fork adds**

- **Long-context speed:** decode attention per verify window, INT8 prompt attention, a kernel for short windows, the
  Q6_K experts on MMQ and the expert arena locked in RAM. Each is opt-in; setup turns them on for the fork's models.
- **Conversations on NVMe:** going back to a ~123K conversation after another one takes 2.4-2.6 s instead of 33-34 s.
- **For agents:** reasoning-loop recovery, `ban_scripts` (no Chinese or Korean tokens inside a Russian answer),
  grammar-constrained tool calls (opt-in) and a deterministic mode for A/B runs.
- **Benchmarks:** `bench/eval-ru` (short tasks, Russian prompts) and `bench/agent-ru` (20 multi-turn coding tasks:
  Cyber-Tiel 53 of 60, Ornith 55 of 60).

### Install the fork

Windows, NVIDIA RTX 20 or newer, driver 580 or newer:

1. Download `Strata-Asofwar-<version>-windows-cuda13.zip` from the
   [fork's latest release](https://github.com/Asofwar/Strata/releases/latest) and unzip it into a folder without
   spaces in its path. It holds the fork's code and a ready engine.
2. Run `START-HERE.bat --setup --family cyber-tiel` (or `--family ornith-abl`). Add `--draft-vocab cyrillic` if you
   chat in Russian.

A clone works the same way and `UPDATE.bat` updates it. On Linux use `./setup.sh` with the same options (the fork has
not tested Linux). Other ways to install the fork are in [Install](#install). Don't use `strata update` or upstream's
installers: the fork publishes no signed update feed, and upstream's engine has no pack path for these models.

**Read more:** [docs/FORK.ru.md](docs/FORK.ru.md) (overview, every measurement, the recommended config; Russian) ·
[the kernels](docs/DETAILS.md#long-contexts-on-the-pack-path-qwen36--ornith--cyber-tiel-this-fork-opt-in) ·
[EVAL.ru.md](docs/EVAL.ru.md) · [AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md)

<p align="center"><sub>Everything below is upstream Strata's README. Its install section is rewritten for the fork.</sub></p>

---

<h3 align="center">Run a state-of-the-art model on your own gaming PC</h3>

<p align="center">Support for NVIDIA, AMD, Intel · Windows, Linux, Mac · free and open source</p>

<p align="center">
  <a href="https://github.com/Niko1221/Strata/releases"><img src="https://img.shields.io/github/v/release/Niko1221/Strata?include_prereleases&label=upstream%20release" alt="Upstream latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="MIT license"></a>
  <a href="https://github.com/Asofwar/Strata/stargazers"><img src="https://img.shields.io/github/stars/Asofwar/Strata?style=flat" alt="GitHub stars"></a>
</p>

<p align="center"><a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4"><img src="docs/media/pagoda-preview.webp" width="720" alt="A voxel pagoda garden that Strata's model wrote, running in the browser"></a><br>
<sub>A voxel pagoda garden, 1 shot prompt running on an RTX 5070 with Strata (IQ3_S, 128K context) ·
<a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4">full video (49 s)</a></sub></p>

Strata runs **[Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)**, a 125-billion-parameter model that
normally needs a server, on a normal PC. It chats, writes code, reads pictures and works with your apps and coding
agents. Your chats and files stay on your PC.

**New here?** Check [what you need](#what-you-need), then [install](#install).

- **Runs on a gaming PC.** 32 GB of RAM and graphics memory together is enough to start.
- **Works with your tools.** It speaks the OpenAI and Anthropic APIs, so Claude Code, Codex CLI, OpenCode and other agents connect to it.
- **Reads pictures.** They are on by default.
- **Free.** MIT license, no account, no cloud.
- **Private.** No telemetry. What Strata downloads, when it uses the internet and how it checks downloads is in [docs/SAFETY.md](docs/SAFETY.md).

Version 0.2.1 · engine 0.1.46

## What you need

**You need at least 32 GB of RAM and graphics memory (VRAM) together.** On a Mac or a Ryzen AI Max, that is the unified
memory. More memory gives a bigger model or a faster one.

- A 32 GB PC with a 12-16 GB card runs the Coder.
- 64 GB of RAM runs every size.

| Your computer | Details |
| --- | --- |
| **NVIDIA** GeForce RTX 20, 30, 40, 50 series (12 GB or more) | [Install](#install) (Windows: the release zip). |
| **AMD** Radeon RX 6800 and newer, Radeon AI PRO R9700 (12 GB or more) | [AMD cards](docs/AMD_HIP.md) |
| **Intel** Arc | [Intel Arc](docs/INTEL_ARC.md), [Intel engine](docs/INTEL.md) |
| **Apple Silicon Mac** (M1 or newer, macOS 15 or newer) | [Mac](docs/MAC.md) |
| **AMD Ryzen AI Max (Strix Halo)** and other unified-memory systems | [Strix Halo](docs/STRIX_HALO.md) |
| Older cards and processors | [Older GPUs](docs/OLDER_GPUS.md), [Older CPUs](docs/INSTALL.md#older-cpus-experimental) |

Also needed:

- about 80 GB of free disk (an SSD makes the first start much faster)
- Windows 10 / 11, Linux or macOS
- a current graphics driver

Two or three cards of the same make can share a model ([multi-GPU](docs/MULTI_GPU.md)). Strata never splits a model across
NVIDIA and AMD cards. Full list: [docs/INSTALL.md](docs/INSTALL.md#what-you-need).

## Install

This is Asofwar's fork, and everything below installs the fork from its [releases](https://github.com/Asofwar/Strata/releases), not upstream's. The fork ships a Windows build for NVIDIA RTX 20 or newer (driver 580 or newer). It does not ship Strata's desktop app installers (`.exe`, `.AppImage`, `.dmg`), the Terminal's signed update feed (`strata update`), or builds for Mac, AMD (HIP) and Intel. For those, [build from source](#build-from-source); the fork has not tested them.

Pick one option. They all start the same engine and use the same models.

### Option A: the release zip (Windows, NVIDIA)

The easiest way on Windows. The zip holds the fork's code and a ready engine, so nothing is compiled. Download the file from the [latest release](https://github.com/Asofwar/Strata/releases/latest).

| System | Your graphics card | File to download |
| --- | --- | --- |
| **Windows 10 / 11** | NVIDIA RTX 20 series or newer, driver 580 or newer | `Strata-Asofwar-<version>-windows-cuda13.zip` |

**If you are unsure:** an NVIDIA RTX card with a driver of version 580 or newer is what this zip is for. For an older card or driver, see [Older GPUs](docs/OLDER_GPUS.md) and build from source. The release also has `strata-windows-x64.zip` (the engine alone): setup downloads it by itself, so you don't need it.

Then:

1. Unzip the file into a folder without spaces in its path.
2. Double-click `START-HERE.bat`. It finds your card, asks which model and size, how much context and whether it should read pictures, downloads the model and starts it. Press Enter for the recommended answers. For the fork's models run `START-HERE.bat --setup --family cyber-tiel` (or `--family ornith-abl`), as in [Install the fork](#install-the-fork).

The model is a big download (about 40-70 GB) and continues where it stopped if it is interrupted. Closing the window stops Strata and the engine.

### Option B: one line

Windows (PowerShell), NVIDIA RTX 20 or newer:

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

It downloads the zip of Option A from the latest release, checks it against `SHA256SUMS.txt`, unzips it and runs `START-HERE.bat`.

Linux (the fork has not tested Linux):

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

It downloads the release's source and runs `./setup.sh`, which builds the engine from source on your PC.

To read a script before it runs, download it first (`curl -fsSL <address> -o install.sh` or, in PowerShell, `irm <address> -OutFile install.ps1`), read it, then run it.

### Option C: let your AI set it up

Paste this into Claude Code, Cursor, Codex, GitHub Copilot or another coding assistant:

```text
Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.
```

It checks your graphics card, RAM and disk, picks the model that fits, installs and starts it, and tells you how to
connect your apps. AI tools can also install, start and stop Strata through its [MCP server](docs/MCP_SERVER.md).

Prefer to build it yourself? See [Build from source](#build-from-source).

## Models

The app and `strata launch` recommend a model for your memory. It is one model in several sizes, compressed more or less.
Smaller sizes are faster. Larger sizes are a bit smarter.

### Low on memory? Try Gyro

[Gyro](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-Gyro-GGUF) (by agentionai) is the smallest way to run this model.

| Size | Memory it needs (RAM + VRAM) | Download | What it is |
| --- | ---: | ---: | --- |
| **Gyro-S** | 27.6 GB | 58.5 GB | For PCs that fit nothing else. Quality is lower than IQ2_XS. |
| **Gyro-M** | 35 GB | 92.0 GB | About IQ3_XXS quality with about 20% less GPU memory. It writes answers 17-21% slower than Q2_0 on a 12 GB card and on an R9700. |

Gyro runs on NVIDIA and AMD cards (AMD is experimental), not on Intel Arc or the Mac. Details and measurements:
[docs/GYRO.md](docs/GYRO.md). Start it with `strata launch --model gyro-s`.

### The other sizes

| Your memory (RAM + VRAM) | Take | Notes |
| --- | --- | --- |
| **32 GB** | **Gyro-S**, or the **[Coder](docs/MODELS.md#coder)** for code | The Coder needs 32 GB of RAM and keeps half of the experts, so it is weaker outside code |
| **40 GB** | **[Swift 1.5](docs/MODELS.md#swift-15)** IQ2_XS (39.2 GB), or **Gyro-M** (35 GB) | Swift thinks for a shorter time before it answers. Gyro-M is close to IQ3_XXS in quality, but it writes answers 17-21% slower than Q2_0 |
| **48 GB** | **IQ3_XXS** (47.0 GB) | Slower, better |
| **64 GB** | **IQ3_S** (54.8 GB), the original or Swift 1.5 | The slowest, the best: it matches the full model on the published tests |
| **96 GB or more** | Unsloth's **UD-IQ4_XS** (about 72 GB of RAM) to **Q8_0** (about 136 GB), 4 to 8 bit | Closer to the full model. With less RAM, Strata reads part of them from the SSD, which is much slower |

Less RAM than a row says can still work: Strata switches to its
[low-RAM mode](docs/MODELS.md#a-big-graphics-card-and-little-ram) by itself. Expect it to be slower, and much slower
with a small graphics card.

More choices:

- **[Swift 1.5](docs/MODELS.md#swift-15)** is a fine-tune that thinks for a shorter time before it answers, at about the same quality and RAM.
- **[NVFP4](docs/NVFP4.md)** is NVIDIA's 4-bit version for NVIDIA cards. It needs about 80 GB of RAM to keep every expert in RAM.
- **[Qwen3.6-35B-A3B](docs/QWEN36.md)** is a smaller, different model that reads pictures and can answer several requests at once.
- **[Huihui-Ornith-1.5-35B-A3B-abliterated](docs/QWEN36_PACK.md#huihui-ornith-15-35b-a3b-abliterated)** and **[Cyber-Tiel-Coder-35B-A3B](docs/QWEN36_PACK.md#cyber-tiel-coder-35b-a3b)** are fine-tunes of the same architecture that run from a Strata pack with int8 KV, for long contexts (100K-262K) on a 16 GB card.
- **[OrcaRouter's Uncensored IQ3_XXS](docs/MODELS.md#orcarouter-uncensored-iq3_xxs)** is set up by hand.

Every size, download and what fits where: [docs/MODELS.md](docs/MODELS.md).

## How fast is it?

Based on a 12 GB graphics card (RTX 5070, Ryzen 5 7600, 64 GB RAM). See results from other cards:
[speed of each model](docs/MODELS.md#how-fast-is-each-size), [community results](docs/COMMUNITY_BENCHMARKS.md).

| Model | Answers appear at | Reads your prompt at |
| --- | --- | --- |
| **Q2_0** | `████████████` 94 tokens/s | `████████████` 2,650 tokens/s |
| **IQ2_XS** | `██████████░░` 79 tokens/s | `█████████░░░` 2,090 tokens/s |
| **IQ3_XXS** | `████████░░░░` 62 tokens/s | `████████░░░░` 1,750 tokens/s |
| **IQ3_S** | `███████░░░░░` 53 tokens/s | `███████░░░░░` 1,620 tokens/s |
| **Coder** | `███████░░░░░` 55 tokens/s | `██████████░░` 2,180 tokens/s |

A token is about ¾ of a word, so 60 tokens per second is faster than you can read. "Reads your prompt" is how fast Strata
takes in a long document, code or chat history.

Measured on a 16 GB AMD card (RX 9070 XT, Ryzen 9 3900X, 47 GB RAM):

| Model | Answers appear at | Reads your prompt at |
| --- | --- | --- |
| **Q2_0** | `████████░░░░` 60 tokens/s | `█████░░░░░░░` 1,160 tokens/s |
| **IQ2_XS** | `███████░░░░░` 52 tokens/s | `█████░░░░░░░` 1,110 tokens/s |
| **Coder** | `██████░░░░░░` 44 tokens/s | `██████░░░░░░` 1,420 tokens/s |

The bars use one scale for both tables. A card with more VRAM is faster: an RTX 3090 (24 GB) should write about 100-140
tokens per second. The engine version behind each number is in [DETAILS.md](docs/DETAILS.md#speed-measured).

## Using it

The fork does not ship Strata's desktop app or the Terminal's installer or signed update feed. **In the app** and **In the
Terminal** below describe upstream's app and `strata` command, which the fork has not tested. With the fork, start Strata
with `START-HERE.bat` (or `./setup.sh`) and update it with `UPDATE.bat` (or `./update.sh`); don't use `strata update`.

### In the app

The app has a **Chat**, a **Monitor** of the model and your GPU, CPU and RAM, a **Models** page and **Settings**. The chat
can work in a folder on your PC. In **Manual** mode it asks before it changes a file or runs a command. Type
`/loop 10m <what to do>` to repeat a message every 10 minutes while the chat is open.

The chat can search the web with DuckDuckGo (or Bing), with no account. You can add a search key under **Settings, Tools**.
Search is the one feature that sends something off your PC, the search words.

To run two models, turn on **Run multiple models** and give each model its own card of the same make.

<p align="center"><img src="docs/media/app-chat.png" width="900" alt="The Strata app: a chat where the agent built a small voxel pagoda garden, with the page open in the preview on the right"><br>
<sub>A chat in the Strata app: the agent wrote a small voxel pagoda garden as one HTML file, and the page opens in the preview next to the conversation</sub></p>

### In the Terminal

<p align="center"><img src="docs/media/terminal-monitor.png" width="900" alt="The Strata Terminal monitor overview while the model writes a reply"><br>
<sub><code>strata monitor</code> while the model writes a reply: speed, GPU, memory and the recent requests</sub></p>

```sh
strata launch                                  # guided screens: model, context, pictures, access, then serve
strata launch --model q2_0 --yes --no-tui     # no questions: serve, print the address, return
strata launch --plan --model q2_0              # show what would happen; nothing changes
strata launch --status                         # what is being served now
strata launch --stop                           # stop it
strata monitor --url http://127.0.0.1:8080     # watch speed, GPU, memory and requests
strata doctor                                  # check the installed engine files
```

`strata --help` lists everything. Starting and serving never download anything. Only the install and `strata launch` (when
you choose a model) do. To reach Strata from your phone or another PC, use
`strata launch --access lan`. It makes an API key and will not start on a network without one. No browser opens unless
you add `--open`. Guide: [docs/TERMINAL_LAUNCH.md](docs/TERMINAL_LAUNCH.md). Whole client: [docs/TERMINAL.md](docs/TERMINAL.md).

### With AI agents

An agent follows [docs/AI_SETUP.md](docs/AI_SETUP.md) (Option C): it gets the fork, runs setup without questions
and starts the server. The repository rules are in [AGENTS.md](AGENTS.md).

### Connect your other apps

| App type | Base URL |
| --- | --- |
| OpenAI-compatible (most apps and agents) | `http://127.0.0.1:8080/v1` (any API key, any model name) |
| Anthropic API (Claude Code and others) | `http://127.0.0.1:8080`, without `/v1`. These apps add `/v1/messages` themselves. Claude Code: `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([setup](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

`strata connect` prints the exact settings for OpenCode, Codex CLI, Claude Code, oh-my-pi, pi, Hermes Agent and OpenClaw.
`strata connect opencode --write` writes the file after asking and keeps a backup.

### Pictures

Pictures are on by default for models that can read them. Attach or paste a picture in the chat, or send it from your app.
The picture reader runs on the processor when your graphics card has less than 24 GB (a few seconds per picture, nothing
taken from the card's memory) and on the graphics card from 24 GB. The rule is the same for NVIDIA and AMD. Turn pictures
off per model, or choose the reader with `--vision off`, `--vision gpu` or `--vision cpu`.

The numbers behind the rule: on a Radeon AI PRO R9700 the card's reader took 57 ms for a 260-token picture and the
processor's took 3.1 s. On 16 GB cards (Tesla P100 and RTX A4000, Linux) the card's reader cost 3-5% of text speed,
because it holds about 1.4 GB that the model would use otherwise. On a Mac the reader runs on the Mac's GPU whatever its memory (0.45 s for a 260-token picture on an M4 with 32 GB, about 1.2 GB of the shared
memory); the processor reader needs about 50 s per picture there, so it runs only when you ask for it with `--vision cpu`.

### Good to know

- Choose the thinking level (**off, low, medium or high**) in the chat menu or in your app's "reasoning effort". Off is fastest.
- Strata answers one request at a time by default. For several at once, use `--parallel N` in `strata launch` or
  `"parallel": 2` in the config ([BATCHING.md](docs/BATCHING.md)). On a 12 GB card this makes each answer slower.
- Strata reads the first message of a chat in full, about 1 minute per 30,000 tokens. Follow-up messages start in seconds.
- Where your chats are stored and the whole API: [docs/INSTALL.md](docs/INSTALL.md#where-things-are-stored), [docs/DETAILS.md](docs/DETAILS.md#using-it).

## Build from source

<details>
<summary>Windows, Linux and Mac from the repository</summary>

[Download the fork](https://github.com/Asofwar/Strata/archive/refs/heads/main.zip) and unzip it, or run
`git clone https://github.com/Asofwar/Strata.git`. The fork has tested only Windows with an NVIDIA card; Linux, Mac, AMD and
Intel are upstream's paths, which it has not tested.
**Windows:** double-click `START-HERE.bat`. **Linux:** run `./setup.sh` in the Strata folder.

**Mac (Apple Silicon, macOS 15 or newer):** install Apple's Command Line Tools once with `xcode-select --install`
(Xcode itself is not needed). Open Terminal in the Strata folder and run `./setup.sh`. It builds the Mac engine on your
Mac (about 7 minutes), asks the same questions, downloads the model and starts it. Next time, `./setup.sh` starts it
right away. Which size fits your Mac: [docs/MAC.md](docs/MAC.md).

The installer finds your card and sets up the right engine. It asks which model and size, how much context (how much text
the model keeps in mind) and whether it should read pictures. Press Enter for the recommended answer. Then it downloads the
model (about 70 GB) and starts it. If the download stops, run it again and it continues. Your browser opens the Strata
page at `http://127.0.0.1:8080`.

> While the model starts, your PC can be slow or stop responding for 1-3 minutes (longest the first time). Strata loads
> 35-55 GB into your RAM and locks part of it for the graphics card. Wait, and don't close the window.

Next time, run `START-HERE.bat` (or `./setup.sh`) again. It starts right away and downloads nothing twice. Close its
window to stop the model. `UPDATE.bat` (`./update.sh`) updates Strata without starting it. Updating, Docker, several cards,
where the files go and every option: [docs/INSTALL.md](docs/INSTALL.md).

To measure your PC, run `BENCH.bat` (`./bench.sh`). It takes 5-10 minutes and writes a report you can share
([how](docs/COMMUNITY_BENCHMARKS.md#run-the-benchmark)).

**Optional: more speed on one card when the whole model fits in RAM.** Two opt-in settings by RubenTorney (#1904, #1905).
They help when you run one graphics card and your RAM holds every expert, for example Q2_0 or IQ3_XXS on a 64 GB PC. Open
`strata-<model>.json` in the Strata data folder ([where](docs/INSTALL.md#where-things-are-stored)) and add:

- `"--adapt-async", "1"` to the `"args"` list. The expert cache then updates on a helper thread instead of pausing the
  answer. Measured on an RTX 5070 (Windows, Q2_0): +4-5% decode, +7-10% on code and long documents. Answers can differ
  slightly from the default and stay the same from run to run.
- `"STRATA_PIN_BY_NEED": "1"` in the `"env"` block (Windows). Windows can lock only about half the RAM for the graphics
  card, and this locks the experts the card needs first. Measured on the RTX 5070: +4.4% prompt reading.

```json
"args": [ ..., "--adapt-async", "1" ],
"env": { "STRATA_PIN_BY_NEED": "1" }
```

Restart Strata after the change. To undo, remove the two entries.

</details>

## How does it work?

Models like this one usually run on servers with hundreds of gigabytes of graphics memory. Your graphics card has
12-24 GB. Strata makes the model fit by sharing the work across your whole PC. Picture a library.

- The model is a team of 24,576 small specialists ("experts"), like 24,576 reference books. Each word needs only 10 of them.
- **Your graphics card is the desk.** It is small and fast. The roughly 4,000 books used most often lie open on it.
- **Your RAM is the shelves in the reading room.** All 24,576 books are there. When a word needs a book that is not on the
  desk, your processor reads it from the shelf at once, while the card keeps working.
- **Your SSD is the archive.** It holds a 29 GB lookup table. The model reads a few rows of it per word, so it does not
  need to sit in RAM.

<p align="center"><img src="docs/media/how-it-works.svg" width="860" alt="The model's 24,576 experts: the busiest on the graphics card, all of them in RAM, a lookup table on the SSD"></p>

A small helper also guesses the next few words. The big model checks all of them at once and keeps the right ones. You get
the same answer, 1.6-1.8x sooner. Long texts are read in big pieces, up to 8,192 tokens at a time, at over 1,000 tokens
per second.

<p align="center"><img src="docs/media/guess-and-check.svg" width="860" alt="A small helper guesses the next words; the big model checks them all at once and keeps the right ones"></p>

The longer explanation: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md). Every part and its numbers:
[the details](docs/DETAILS.md#how-it-works) and the [paper](docs/paper/Strata-Paper.pdf).

## Something went wrong?

- **My PC froze the first time Strata started.** It loads the model into RAM. Wait, and don't close the window. Still
  frozen after 10 minutes? Restart the PC, close other programs and try again, or pick a smaller size.
- **It stopped while downloading or installing.** Start the app or `strata launch` again, or run `START-HERE.bat` (or
  `./setup.sh`) again. It continues where it stopped.
- **It is very slow, the disk light keeps blinking, or it says "the engine stopped unexpectedly".** Your PC does not have
  enough free RAM. Close other programs (browsers use a lot), or pick a smaller size such as Q2_0 or IQ2_XS.
- **It says there is no engine for this PC.** Run `START-HERE.bat` (or `./setup.sh`) again: it fetches the engine from the
  fork's release or builds it. Don't run `strata update`: the fork publishes no signed update feed.
- **It says port 8080 is already in use.** Strata is already running. Look for its window.

More problems and fixes: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). Still stuck? Open an
[issue](https://github.com/Asofwar/Strata/issues). In the app, attach the file from **Settings, Engine, Diagnostics, View
logs, Save logs**. In the Terminal, paste the output of `strata doctor`. From source, attach `strata-<model>.log` from the
Strata folder. For a security problem, report it privately: [SECURITY.md](SECURITY.md).

## Credits and license

The model is [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) by the Qwen team. It was compressed by
[ISTA-DASLab](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF), UkisAI (Swift 1.5), agentionai (Gyro)
and Unsloth. Strata uses parts of [llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). All credits:
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#credits). Strata is open source under the [MIT License](LICENSE). A few parts and
every model have their own licenses ([which ones](docs/HOW_IT_WORKS.md#license)).

## Contributing

Found a bug, or want to send a change or a benchmark? Read [CONTRIBUTING.md](CONTRIBUTING.md) first. It says what to
include so that others can check your work.

## Support Strata

Strata is free and MIT-licensed. I build it and test it on whatever hardware I can get. If it runs well on your PC, a coffee helps
me keep testing new cards and fixing what you report. No pressure. Using it and reporting what you find helps just as much.

<a href="https://buymeacoffee.com/strataengine"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>

Interested in sponsoring Strata? Contact me via [GitHub](https://github.com/Asofwar).
