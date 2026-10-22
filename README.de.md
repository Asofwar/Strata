<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/strata-turbo-lockup-dark.svg">
    <img src="docs/media/strata-turbo-lockup-light.svg" alt="Strata Turbo" width="440">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <b>Deutsch</b> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">Coding-Agenten mit 262K Kontext auf einer einzigen 16-GB-Grafikkarte</h3>

<p align="center">Asofwars Fork von <a href="https://github.com/Niko1221/Strata">Strata</a> · Windows + NVIDIA · kostenlos und Open Source</p>

<p align="center"><b>16–18× schneller als Upstream-Strata bei 66K Kontext</b>, gleiche Karte und gleiches Modell</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata-Turbo/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata-Turbo?label=release" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata-Turbo" alt="MIT-Lizenz"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Fork-Dokumentation"></a>
  <a href="#unterstützung"><img src="https://img.shields.io/badge/Spenden-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata führt große Mixture-of-Experts-Modelle auf einem normalen PC aus: Die am häufigsten gebrauchten Experten liegen auf der
Grafikkarte, der Rest im RAM. Dieser Fork ist für Coding-Agenten mit langem Kontext auf den Qwen3.6-35B-A3B-Modellen
**Cyber-Tiel-Coder** und **Ornith** abgestimmt: int8-K/V, MTP-Drafts und eigene Kernel für lange Kontexte. Er spricht die
OpenAI- und die Anthropic-API, sodass sich Codex CLI, Claude Code, OpenCode und andere Agenten verbinden lassen.
Kein Konto, keine Telemetrie.

## Geschwindigkeit

Gleicher PC, gleiche Modelldatei, gleicher Tag (RTX 5080 16 GB, i9-14900K, 48 GB DDR5-7600, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS): Strata Turbo gegen den eigenen Weg von Upstream-Strata für dieses Modell.

| Kontext | Prompt lesen, Turbo / Upstream | Schreiben, Tokens/s, Turbo / Upstream |
| ---: | ---: | ---: |
| 2K | 0.5 s / 4.7 s (9×) | 291 / 71 (4×) |
| 32K | 4.4 s / 75 s (17×) | 286 / 51 (6×) |
| 66K | 10 s / 186 s (18×) | 253 / 16 (16×) |
| 128K | 25 s / 513 s (21×) | 194 / 7 (29×, ein Upstream-Lauf) |

Auf einer 16-GB-Karte startet Upstream mit höchstens 160K Kontext; Strata Turbo läuft mit 262K (bei 200K liest es den Prompt in 49 s und schreibt 161–171 Tokens/s). Methode und Logs: [bench/results/2026-10-22-rtx5080-turbo-vs-upstream](bench/results/2026-10-22-rtx5080-turbo-vs-upstream/README.md).

Der Wechsel zurück zu einer Unterhaltung mit ~123K Kontext, nachdem eine andere lief, dauert 2.5 s statt 33 s
(Unterhaltungen werden auf der NVMe abgelegt). Agenten-Benchmark: 53 von 60 Coding-Aufgaben.
Alle Messungen: [docs/FORK.ru.md](docs/FORK.ru.md).

## Installation

**Windows**, NVIDIA RTX 20 oder neuer (Treiber 580+), in PowerShell:

```powershell
irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex
```

Das Skript lädt das [neueste Release](https://github.com/Asofwar/Strata-Turbo/releases/latest) herunter, prüft es gegen
`SHA256SUMS.txt`, entpackt es nach `%LOCALAPPDATA%\Strata-Turbo` und startet das Setup, das nach dem Modell fragt und es
herunterlädt (Cyber-Tiel: etwa 17 GB). Von Hand: `Strata-Turbo-<version>-windows-cuda13.zip` in einen Ordner ohne
Leerzeichen entpacken und `START-HERE.bat --setup --family cyber-tiel` ausführen.

**Linux** (vom Fork nicht getestet; die Engine wird aus dem Quellcode gebaut):

```sh
curl -fsSL https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.sh | sh
```

**Vom Coding-Assistenten erledigen lassen:** einfach einfügen
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata-Turbo - follow docs/AI_SETUP.md in that repository.`

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
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - wenn etwas schiefgeht; Fehler gehören in die [Issues](https://github.com/Asofwar/Strata-Turbo/issues)
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

Strata Turbo ist kostenlos. Wenn es dir hilft, unterstütze die Arbeit am Fork mit Gram (TON) an sein Telegram-Wallet:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), Telegram-Wallet: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[von einer TON-Wallet senden](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(nur TON-Netzwerk: Eine Überweisung aus einem anderen Netzwerk geht verloren)
