<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <b>Deutsch</b> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">Coding-Agenten mit 262K Kontext auf einer einzigen 16-GB-Grafikkarte</h3>

<p align="center">Asofwars Fork von <a href="https://github.com/Niko1221/Strata">Strata</a> · Windows + NVIDIA · kostenlos und Open Source</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=release" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="MIT-Lizenz"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Fork-Dokumentation"></a>
  <a href="#unterstützung"><img src="https://img.shields.io/badge/Spenden-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata führt große Mixture-of-Experts-Modelle auf einem normalen PC aus: Die am häufigsten gebrauchten Experten liegen auf der
Grafikkarte, der Rest im RAM. Dieser Fork ist für Coding-Agenten mit langem Kontext auf den Qwen3.6-35B-A3B-Modellen
**Cyber-Tiel-Coder** und **Ornith** abgestimmt: int8-K/V, MTP-Drafts und eigene Kernel für lange Kontexte. Er spricht die
OpenAI- und die Anthropic-API, sodass sich Codex CLI, Claude Code, OpenCode und andere Agenten verbinden lassen.
Kein Konto, keine Telemetrie.

## Geschwindigkeit

RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS mit den Einstellungen, die das Setup schreibt:

| Kontext | Prompt lesen | Generieren |
| ---: | ---: | ---: |
| 130K | 25.7 s | 146-167 Tokens/s |
| 200K | 49.4 s | 161-171 Tokens/s |

Der Wechsel zurück zu einer Unterhaltung mit ~123K Kontext, nachdem eine andere lief, dauert 2.5 s statt 33 s
(Unterhaltungen werden auf der NVMe abgelegt). Agenten-Benchmark: 53 von 60 Coding-Aufgaben.
Alle Messungen: [docs/FORK.ru.md](docs/FORK.ru.md).

## Installation

**Windows**, NVIDIA RTX 20 oder neuer (Treiber 580+), in PowerShell:

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

Das Skript lädt das [neueste Release](https://github.com/Asofwar/Strata/releases/latest) herunter, prüft es gegen
`SHA256SUMS.txt`, entpackt es nach `%LOCALAPPDATA%\Strata-Asofwar` und startet das Setup, das nach dem Modell fragt und es
herunterlädt (Cyber-Tiel: etwa 17 GB). Von Hand: `Strata-Asofwar-<version>-windows-cuda13.zip` in einen Ordner ohne
Leerzeichen entpacken und `START-HERE.bat --setup --family cyber-tiel` ausführen.

**Linux** (vom Fork nicht getestet; die Engine wird aus dem Quellcode gebaut):

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

**Vom Coding-Assistenten erledigen lassen:** einfach einfügen
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.`

Neu starten: `START-HERE.bat`. Aktualisieren: den Einzeiler noch einmal ausführen (oder `UPDATE.bat` in einem Klon).
`strata update` nicht verwenden: Der Fork veröffentlicht keinen signierten Feed. Alle Optionen, andere Hardware und
wohin die Dateien kommen: [docs/INSTALL.md](docs/INSTALL.md).

## Modelle

| Modell | Setup | Hinweise |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | Standard des Forks: denkt kürzer, hängt sich seltener in Schleifen |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | in den Benchmarks gleiche Qualität, aber langsamer |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, Größe wählen | Modell von Upstream: ab 32 GB RAM und VRAM zusammen, Größen in [docs/MODELS.md](docs/MODELS.md) |

Für Antworten auf Russisch `--draft-vocab cyrillic` hinzufügen. Qualitätsprüfungen: [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Apps verbinden

| App-Typ | Base-URL |
| --- | --- |
| OpenAI-kompatibel (die meisten Apps und Agenten) | `http://127.0.0.1:8080/v1` (beliebiger API-Key, beliebiger Modellname) |
| Anthropic-API (Claude Code) | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([Einrichtung](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

Der Server lauscht nur auf `127.0.0.1`. Vor dem Öffnen für ein Netzwerk einen API-Key setzen ([docs/SAFETY.md](docs/SAFETY.md)).

## Dokumentation

- [docs/FORK.ru.md](docs/FORK.ru.md) - was der Fork ergänzt, alle Messungen, die empfohlene Konfiguration (auf Russisch)
- [docs/INSTALL.md](docs/INSTALL.md) - Installationsoptionen, AMD / Intel / Mac / mehrere Karten (Upstream-Pfade, vom Fork nicht getestet), Einstellungen
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - wenn etwas schiefgeht; Fehler gehören in die [Issues](https://github.com/Asofwar/Strata/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) - wie ein großes Modell auf einen PC passt; jeder Teil und jede Zahl: [DETAILS.md](docs/DETAILS.md), [das Paper](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

Die Dokumente sind auf Englisch, nur `FORK.ru.md`, `EVAL.ru.md` und `AGENT-EVAL.ru.md` sind auf Russisch.

## Danksagung und Lizenz

Strata stammt von [Niko1221](https://github.com/Niko1221/Strata); dieser Fork ergänzt die Arbeit am langen Kontext. Modelle: das
Qwen-Team, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) und [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai und Unsloth (Flash-Next-Größen). Strata verwendet Teile von
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). MIT-Lizenz ([LICENSE](LICENSE)); einige Teile und jedes Modell
haben eigene Lizenzen ([welche](docs/HOW_IT_WORKS.md#license)).

## Unterstützung

Strata Asofwar ist kostenlos. Wenn es dir hilft, unterstütze die Arbeit am Fork mit Gram (TON) an sein Telegram-Wallet:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), Telegram-Wallet: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[von einer TON-Wallet senden](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(nur TON-Netzwerk: Eine Überweisung aus einem anderen Netzwerk geht verloren)
