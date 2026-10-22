<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><b>English</b> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">Coding agents with 262K context on one 16 GB graphics card</h3>

<p align="center">Asofwar's fork of <a href="https://github.com/Niko1221/Strata">Strata</a> · Windows + NVIDIA · free and open source</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=release" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="MIT license"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Fork docs"></a>
  <a href="#support"><img src="https://img.shields.io/badge/donate-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata runs big mixture-of-experts models on a normal PC: the busiest experts sit on the graphics card, the rest in RAM.
This fork tunes it for coding agents with long contexts on the Qwen3.6-35B-A3B models **Cyber-Tiel-Coder** and
**Ornith**: int8 K/V, MTP drafts and its own long-context kernels. It speaks the OpenAI and Anthropic APIs, so Codex CLI,
Claude Code, OpenCode and other agents connect to it. No account, no telemetry.

## How fast

RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS with the settings setup writes:

| Context | Reading the prompt | Writing |
| ---: | ---: | ---: |
| 130K | 25.7 s | 146-167 tokens/s |
| 200K | 49.4 s | 161-171 tokens/s |

Going back to a ~123K conversation after another one takes 2.5 s instead of 33 s (conversations are parked on NVMe).
Agent benchmark: 53 of 60 coding tasks. Every measurement: [docs/FORK.ru.md](docs/FORK.ru.md).

## Install

**Windows**, NVIDIA RTX 20 or newer (driver 580+), in PowerShell:

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

It downloads the [latest release](https://github.com/Asofwar/Strata/releases/latest), checks it against
`SHA256SUMS.txt`, unpacks it into `%LOCALAPPDATA%\Strata-Asofwar` and starts setup, which asks for the model and
downloads it (Cyber-Tiel: about 17 GB). By hand: unzip `Strata-Asofwar-<version>-windows-cuda13.zip` into a folder
without spaces and run `START-HERE.bat --setup --family cyber-tiel`.

**Linux** (not tested by the fork; the engine is built from source):

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

**Let your coding assistant do it:** paste
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.`

Start it again with `START-HERE.bat`; update by running the one-liner again (or `UPDATE.bat` in a clone). Don't use
`strata update`: the fork publishes no signed feed. Every option, other hardware and where files go:
[docs/INSTALL.md](docs/INSTALL.md).

## Models

| Model | Setup | Notes |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | the fork's default: thinks shorter, loops less |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | same quality in the benchmarks, slower |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, pick a size | upstream's model: 32+ GB of RAM and VRAM together, sizes in [docs/MODELS.md](docs/MODELS.md) |

For answers in Russian add `--draft-vocab cyrillic`. Quality checks: [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Connect your apps

| App type | Base URL |
| --- | --- |
| OpenAI-compatible (most apps and agents) | `http://127.0.0.1:8080/v1` (any API key, any model name) |
| Anthropic API (Claude Code) | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([setup](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

The server listens on `127.0.0.1` only. Before opening it to a network set an API key ([docs/SAFETY.md](docs/SAFETY.md)).

## Docs

- [docs/FORK.ru.md](docs/FORK.ru.md) - what the fork adds, all measurements, the recommended config (Russian)
- [docs/ROADMAP.ru.md](docs/ROADMAP.ru.md) - plans: pictures, audio and video, speed, quality (Russian)
- [docs/INSTALL.md](docs/INSTALL.md) - install options, AMD / Intel / Mac / several cards (upstream paths, not tested by the fork), settings
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - when something goes wrong; bugs go to [issues](https://github.com/Asofwar/Strata/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) - how a big model fits on a PC; every part and number: [DETAILS.md](docs/DETAILS.md), [the paper](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

## Credits and license

Strata is by [Niko1221](https://github.com/Niko1221/Strata); this fork adds the long-context work on top. Models: the Qwen
team, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) and [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai and Unsloth (Flash-Next sizes). Strata uses parts of
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). MIT License ([LICENSE](LICENSE)); some parts and every model
have their own ([which](docs/HOW_IT_WORKS.md#license)).

## Support

Strata Asofwar is free. If it helps you, support the fork's work with Gram (TON) to its Telegram wallet:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), Telegram wallet: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[send from a TON wallet](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(TON network only: a transfer from another network is lost)
