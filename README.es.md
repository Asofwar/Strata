<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <b>Español</b> · <a href="README.pt-BR.md">Português</a></p>

<h1 align="center">Strata Turbo</h1>

<h3 align="center">Agentes de programación con contexto de 262K en una sola tarjeta gráfica de 16 GB</h3>

<p align="center">Fork de <a href="https://github.com/Niko1221/Strata">Strata</a> hecho por Asofwar · Windows + NVIDIA · gratuito y de código abierto</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=versi%C3%B3n" alt="Versión"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="Licencia MIT"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Documentación del fork"></a>
  <a href="#apoyar-el-proyecto"><img src="https://img.shields.io/badge/donar-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata ejecuta grandes modelos de mezcla de expertos (MoE) en un PC normal: los expertos más usados se quedan en la tarjeta
gráfica y el resto en la RAM. Este fork lo ajusta para agentes de programación con contextos largos sobre los modelos
Qwen3.6-35B-A3B **Cyber-Tiel-Coder** y **Ornith**: K/V en int8, borradores MTP y kernels propios para contexto largo. Habla las
API de OpenAI y de Anthropic, así que Codex CLI, Claude Code, OpenCode y otros agentes se conectan a él. Sin cuenta y sin
telemetría.

## Velocidad

RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS con los ajustes que escribe el setup:

| Contexto | Lectura del prompt | Generación |
| ---: | ---: | ---: |
| 130K | 25.7 s | 146-167 tokens/s |
| 200K | 49.4 s | 161-171 tokens/s |

Volver a una conversación de ~123K después de otra tarda 2.5 s en lugar de 33 s (las conversaciones se aparcan en NVMe).
Benchmark de agentes: 53 de 60 tareas de programación. Todas las mediciones: [docs/FORK.ru.md](docs/FORK.ru.md).

## Instalación

**Windows**, NVIDIA RTX 20 o posterior (controlador 580+), en PowerShell:

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

Descarga la [última versión](https://github.com/Asofwar/Strata/releases/latest), la comprueba con `SHA256SUMS.txt`, la descomprime
en `%LOCALAPPDATA%\Strata-Turbo` y lanza el setup, que pregunta por el modelo y lo descarga (Cyber-Tiel: unos 17 GB). A mano:
descomprime `Strata-Turbo-<version>-windows-cuda13.zip` en una carpeta sin espacios y ejecuta
`START-HERE.bat --setup --family cyber-tiel`.

**Linux** (el fork no lo ha probado; el motor se compila desde el código fuente):

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

**Deja que lo haga tu asistente de programación:** pega
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.`

Para volver a arrancarlo, usa `START-HERE.bat`; para actualizar, ejecuta otra vez el comando de una línea (o `UPDATE.bat` en un
clon). No uses `strata update`: el fork no publica un feed firmado. Todas las opciones, otro hardware y dónde van los archivos:
[docs/INSTALL.md](docs/INSTALL.md).

## Modelos

| Modelo | Setup | Notas |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | el predeterminado del fork: piensa menos y se encierra menos en bucles |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | misma calidad en los benchmarks, más lento |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, elegir un tamaño | el modelo de upstream: 32+ GB de RAM y VRAM entre las dos, tamaños en [docs/MODELS.md](docs/MODELS.md) |

Para respuestas en ruso, añade `--draft-vocab cyrillic`. Pruebas de calidad: [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Conectar tus aplicaciones

| Tipo de aplicación | URL base |
| --- | --- |
| Compatible con OpenAI (la mayoría de aplicaciones y agentes) | `http://127.0.0.1:8080/v1` (cualquier clave de API, cualquier nombre de modelo) |
| API de Anthropic (Claude Code) | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| API Responses de OpenAI (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([configuración](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

El servidor solo escucha en `127.0.0.1`. Antes de abrirlo a una red, define una clave de API ([docs/SAFETY.md](docs/SAFETY.md)).

## Documentación

- [docs/FORK.ru.md](docs/FORK.ru.md) - qué añade el fork, todas las mediciones, la configuración recomendada (en ruso)
- [docs/INSTALL.md](docs/INSTALL.md) - opciones de instalación, AMD / Intel / Mac / varias tarjetas (rutas de upstream, no probadas por el fork), ajustes
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - cuando algo falla; los errores van a [issues](https://github.com/Asofwar/Strata/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) - cómo cabe un modelo grande en un PC; cada parte y cada cifra: [DETAILS.md](docs/DETAILS.md), [el paper](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

La documentación está en inglés, salvo `FORK.ru.md`, `EVAL.ru.md` y `AGENT-EVAL.ru.md`, que están en ruso.

## Créditos y licencia

Strata es obra de [Niko1221](https://github.com/Niko1221/Strata); este fork añade el trabajo sobre contexto largo. Modelos: el
equipo de Qwen, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) y [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai y Unsloth (tamaños de Flash-Next). Strata usa partes de
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). Licencia MIT ([LICENSE](LICENSE)); algunas partes y cada modelo
tienen la suya ([cuáles](docs/HOW_IT_WORKS.md#license)).

## Apoyar el proyecto

Strata Turbo es gratuito. Si te sirve, apoya el trabajo del fork con Gram (TON) a su wallet de Telegram:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), wallet de Telegram: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[enviar desde una wallet de TON](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(solo red TON: una transferencia desde otra red se pierde)
