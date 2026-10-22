<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a> · <b>Русский</b></p>

<h2 align="center">Форк Asofwar: агенты для кода с контекстом 262K на карте 16 GB</h2>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=%D1%80%D0%B5%D0%BB%D0%B8%D0%B7%20%D1%84%D0%BE%D1%80%D0%BA%D0%B0" alt="Релиз форка"></a>
  <a href="https://github.com/Niko1221/Strata"><img src="https://img.shields.io/badge/upstream-Niko1221%2FStrata-blue" alt="Upstream: Niko1221/Strata"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Документация форка"></a>
</p>

Этот форк [Niko1221/Strata](https://github.com/Niko1221/Strata) запускает модели Qwen3.6-35B-A3B Cyber-Tiel-Coder и
Ornith на основном движке Strata из пака: int8 K/V (11 KiB на токен вместо 44), MTP-черновики и собственные ядра форка
для длинного контекста. Агент для кода получает до 262K контекста на одной карте 16 GB.

Замеры: RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS с настройками, которые пишет
setup (2026-10-21/22):

| Контекст | Чтение промпта с нуля | Генерация |
| ---: | ---: | ---: |
| 130K | 25.7 с | 146–167 ток/с |
| 200K | 49.4 с | 161–171 ток/с |

**Что добавляет форк**

- **Скорость на длинном контексте:** внимание окна проверки при генерации, INT8-внимание при чтении промпта, ядро для
  коротких окон, эксперты Q6_K через MMQ и закреплённая в RAM арена экспертов. Всё включается флагами; для моделей
  форка setup включает их сам.
- **Разговоры на NVMe:** возврат к разговору на ~123K токенов после другого такого же — 2.4–2.6 с вместо 33–34 с.
- **Для агентов:** выход из зацикленного рассуждения, `ban_scripts` (без китайских и корейских токенов в русском
  ответе), грамматика для вызовов инструментов (по флагу) и детерминированный режим для A/B-замеров.
- **Бенчмарки:** `bench/eval-ru` (короткие задачи на русском) и `bench/agent-ru` (20 многошаговых задач с кодом:
  Cyber-Tiel 53 из 60, Ornith 55 из 60).

### Установка форка

Windows, NVIDIA RTX 20 и новее, драйвер 580 и новее:

1. Скачайте `Strata-asofwar-<версия>-windows-cuda13.zip` из
   [последнего релиза форка](https://github.com/Asofwar/Strata/releases/latest) и распакуйте в папку без пробелов в
   пути. В архиве код форка и готовый движок.
2. Запустите `START-HERE.bat --setup --family cyber-tiel` (или `--family ornith-abl`). Если общаетесь на русском,
   добавьте `--draft-vocab cyrillic`.

Клон репозитория ставится так же, обновляется через `UPDATE.bat`. На Linux — `./setup.sh` с теми же ключами (форк
Linux не проверял). Не используйте для этих моделей `strata update` и установщики upstream ниже: они ставят движок
upstream, в котором нет пути `--pack` для этих моделей.

**Подробнее:** [docs/FORK.ru.md](docs/FORK.ru.md) (обзор, все замеры, рекомендуемый конфиг) ·
[ядра](docs/DETAILS.md#long-contexts-on-the-pack-path-qwen36--ornith--cyber-tiel-this-fork-opt-in) (на английском) ·
[EVAL.ru.md](docs/EVAL.ru.md) · [AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md)

<p align="center"><sub>Ниже — перевод README upstream.</sub></p>

---

<h3 align="center">Современная большая модель на вашем игровом ПК</h3>

<p align="center">NVIDIA, AMD, Intel · Windows, Linux, Mac · бесплатно и с открытым кодом</p>

<p align="center">
  <a href="https://github.com/Niko1221/Strata/releases"><img src="https://img.shields.io/github/v/release/Niko1221/Strata?include_prereleases&label=release" alt="Последний релиз"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Niko1221/Strata" alt="Лицензия MIT"></a>
  <a href="https://github.com/Niko1221/Strata/stargazers"><img src="https://img.shields.io/github/stars/Niko1221/Strata?style=flat" alt="Звёзды на GitHub"></a>
</p>

<p align="center"><a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4"><img src="docs/media/pagoda-preview.webp" width="720" alt="Воксельный сад с пагодой, который написала модель Strata, в браузере"></a><br>
<sub>Воксельный сад с пагодой: один промпт, RTX 5070 со Strata (IQ3_S, контекст 128K) ·
<a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4">видео целиком (49 с)</a></sub></p>

Strata запускает **[Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)** на обычном ПК. Это модель на
125 миллиардов параметров, которой обычно нужен сервер. Она общается, пишет код, читает картинки и работает с вашими
приложениями и агентами для кода. Ваши чаты и файлы остаются на вашем ПК.

**Впервые здесь?** Проверьте, [что нужно](#что-нужно), и [установите приложение](#вариант-a-приложение-strata).

- **Работает на игровом ПК.** Для начала хватит 32 GB RAM и видеопамяти вместе.
- **Работает с вашими инструментами.** Strata понимает API OpenAI и Anthropic, поэтому к ней подключаются Claude Code, Codex CLI, OpenCode и другие агенты.
- **Читает картинки.** Включено по умолчанию.
- **Бесплатно.** Лицензия MIT, без аккаунта, без облака.
- **Приватно.** Без телеметрии. Что Strata скачивает, когда ходит в интернет и как проверяет загрузки: [docs/SAFETY.md](docs/SAFETY.md) (на английском).

Числа записаны как в английском оригинале: запятая отделяет тысячи, точка отделяет дробную часть.

Версия 0.2.1 · движок 0.1.46

## Что нужно

**Нужно не меньше 32 GB RAM и видеопамяти (VRAM) вместе.** На Mac или Ryzen AI Max это общая (unified) память.
Больше памяти — больше или быстрее модель.

- ПК с 32 GB и картой 12-16 GB запускает Coder.
- С 64 GB RAM работает любой размер.

| Ваш компьютер | Подробности |
| --- | --- |
| **NVIDIA** GeForce RTX 20, 30, 40, 50 (12 GB и больше) | Установите приложение или Terminal. |
| **AMD** Radeon RX 6800 и новее, Radeon AI PRO R9700 (12 GB и больше) | [Карты AMD](docs/AMD_HIP.md) (на английском) |
| **Intel** Arc | [Intel Arc](docs/INTEL_ARC.md), [движок для Intel](docs/INTEL.md) (на английском) |
| **Mac на Apple Silicon** (M1 или новее, macOS 15 или новее) | [Mac](docs/MAC.md) (на английском) |
| **AMD Ryzen AI Max (Strix Halo)** и другие системы с общей памятью | [Strix Halo](docs/STRIX_HALO.md) (на английском) |
| Старые видеокарты и процессоры | [Старые GPU](docs/OLDER_GPUS.md), [старые CPU](docs/INSTALL.md#older-cpus-experimental) (на английском) |

Ещё нужно:

- около 80 GB свободного места на диске (с SSD первый запуск намного быстрее)
- Windows 10 / 11, Linux или macOS
- свежий драйвер видеокарты

Две или три карты одного производителя могут делить модель ([несколько GPU](docs/MULTI_GPU.md), на английском). Strata
никогда не делит модель между картами NVIDIA и AMD. Полный список: [docs/INSTALL.md](docs/INSTALL.md#what-you-need)
(на английском).

## Установка

> Это сборки upstream Strata, без изменений форка. Для Cyber-Tiel и Ornith с настройками форка см. [Установка форка](#установка-форка).

Выберите один вариант. Все они запускают один и тот же движок и одни и те же модели.

### Вариант A: приложение Strata

Самый простой путь. Движок уже внутри приложения: установите его, выберите модель и общайтесь. Скачайте файл для своей
системы и видеокарты со [страницы релизов](https://github.com/Niko1221/Strata/releases/latest). Не знаете, какой
нужен? Смотрите подсказку под таблицей.

| Система | Ваша видеокарта | Что скачать |
| --- | --- | --- |
| **Windows 10 / 11** | NVIDIA RTX, драйвер 580 или новее | [`Strata-0.2.1-windows-cuda13.exe`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-windows-cuda13.exe) |
| | NVIDIA, старая карта или драйвер старше 580 | [`Strata-0.2.1-windows-cuda12.exe`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-windows-cuda12.exe) |
| | AMD Radeon RX 9000 или Radeon AI PRO R9700 | [`Strata-0.2.1-windows-hip.exe`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-windows-hip.exe) |
| | AMD Radeon RX 7000 или Ryzen AI Max (Strix Halo) | [`Strata-0.2.1-windows-hip-rdna3.exe`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-windows-hip-rdna3.exe) |
| **Linux** | NVIDIA RTX, драйвер 580 или новее | [`Strata-0.2.1-linux-nvidia-cuda13.AppImage`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-linux-nvidia-cuda13.AppImage) |
| | NVIDIA, старая карта или драйвер старше 580 | [`Strata-0.2.1-linux-nvidia-cuda12.AppImage`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-linux-nvidia-cuda12.AppImage) |
| | AMD Radeon RX 9000 или Radeon AI PRO R9700 | [`Strata-0.2.1-linux-amd-rx9070.AppImage`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-linux-amd-rx9070.AppImage) |
| | AMD Radeon RX 7000 | [`Strata-0.2.1-linux-amd-rx7900.AppImage`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-linux-amd-rx7900.AppImage) |
| | AMD Ryzen AI Max (Strix Halo) | [`Strata-0.2.1-linux-amd-strixhalo.AppImage`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-linux-amd-strixhalo.AppImage) |
| **Mac** (Apple Silicon, macOS 15 или новее) | встроенная | [`Strata-0.2.1-mac.dmg`](https://github.com/Niko1221/Strata/releases/latest/download/Strata-0.2.1-mac.dmg) |

**Если не уверены:** для NVIDIA берите `cuda13`, если драйвер версии 580 или новее, иначе `cuda12`. `cuda12` нужен
для старых карт и старых драйверов. Файлы `hip` и `amd` для карт AMD. Для остальных карт AMD (RX 6000) готового
приложения пока нет: смотрите [карты AMD](docs/AMD_HIP.md) (на английском).

Дальше:

- **Windows:** запустите `.exe`. Он ставится для вашего пользователя и не требует прав администратора. Если Windows
  пишет «Система Windows защитила ваш компьютер», нажмите **Подробнее**, затем **Выполнить в любом случае** (установщик
  пока не подписан).
- **Linux:** сделайте файл исполняемым (`chmod +x`) и запустите. Нужен FUSE 2: `sudo apt install libfuse2` (Ubuntu 22.04)
  или `libfuse2t64` (Ubuntu 24.04 и новее).
- **Mac:** откройте `.dmg` и перетащите Strata в «Программы».

На первом экране приложение изучает ваш ПК и советует подходящую модель. Нажмите «Установить». Модель большая (около
40-70 GB), и если загрузка прервётся, она продолжится с того же места. Закрытие окна останавливает Strata и движок.

### Вариант B: Terminal (одна строка)

Terminal — это команда `strata` для скриптов, серверов и ИИ-агентов.

Linux и Mac:

```sh
curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 | iex
```

Скрипт проверяет ПК, скачивает Terminal, сверяет его SHA-256 и распаковывает в домашнюю папку. Права администратора не
нужны. На Windows после этого откройте новое окно терминала. Затем запустите Strata:

```sh
strata launch
```

Она задаёт вопросы по одному: модель, контекст, картинки, кто может подключаться. Потом скачивает движок для вашей
видеокарты (подписанный, перед использованием его пробно запускают) и модель, и начинает работу. Для скриптов и
ИИ-агентов есть флаги:

```sh
strata launch --model q2_0 --yes --no-tui
```

Чтобы прочитать скрипт установки до запуска, сначала скачайте его: `curl -fsSL <address> -o install.sh`, прочитайте и
запустите `sh install.sh`. Все экраны и флаги: [docs/TERMINAL_LAUNCH.md](docs/TERMINAL_LAUNCH.md) (на английском).

### Вариант C: пусть установит ваш ИИ

Вставьте это в Claude Code, Cursor, Codex, GitHub Copilot или другой помощник для кода:

```text
Set up Strata on this PC for me: https://github.com/Niko1221/Strata - follow docs/AI_SETUP.md in that repository.
```

Помощник проверит видеокарту, RAM и диск, выберет подходящую модель, установит и запустит её и скажет, как подключить
ваши приложения. ИИ-инструменты также могут ставить, запускать и останавливать Strata через её
[MCP-сервер](docs/MCP_SERVER.md) (на английском).

Хотите собрать сами? Смотрите [сборку из исходников](#сборка-из-исходников).

## Модели

Приложение и `strata launch` советуют модель под вашу память. Это одна модель в нескольких размерах, сжатая сильнее
или слабее. Меньшие размеры быстрее. Большие немного умнее.

### Мало памяти? Попробуйте Gyro

[Gyro](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-Gyro-GGUF) (от agentionai) — самый компактный способ запустить эту модель.

| Размер | Нужно памяти (RAM + VRAM) | Загрузка | Что это |
| --- | ---: | ---: | --- |
| **Gyro-S** | 27.6 GB | 58.5 GB | Для ПК, куда больше ничего не помещается. Качество ниже, чем у IQ2_XS. |
| **Gyro-M** | 35 GB | 92.0 GB | Качество примерно как у IQ3_XXS, а памяти GPU нужно примерно на 20% меньше. Пишет ответы на 17-21% медленнее, чем Q2_0, на карте 12 GB и на R9700. |

Gyro работает на картах NVIDIA и AMD (AMD экспериментально), но не на Intel Arc и не на Mac. Подробности и замеры:
[docs/GYRO.md](docs/GYRO.md) (на английском). Запуск: `strata launch --model gyro-s`.

### Остальные размеры

| Ваша память (RAM + VRAM) | Что брать | Заметки |
| --- | --- | --- |
| **32 GB** | **Gyro-S**, или **[Coder](docs/MODELS.md#coder)** для кода | Coder нужно 32 GB RAM, он оставляет половину экспертов, поэтому вне кода он слабее |
| **40 GB** | **[Swift 1.5](docs/MODELS.md#swift-15)** IQ2_XS (39.2 GB) или **Gyro-M** (35 GB) | Swift думает меньше перед ответом. Gyro-M по качеству близок к IQ3_XXS, но пишет ответы на 17-21% медленнее, чем Q2_0 |
| **48 GB** | **IQ3_XXS** (47.0 GB) | Медленнее, лучше |
| **64 GB** | **IQ3_S** (54.8 GB), оригинал или Swift 1.5 | Самый медленный и самый лучший: на опубликованных тестах совпадает с полной моделью |
| **96 GB и больше** | **UD-IQ4_XS** от Unsloth (около 72 GB RAM) до **Q8_0** (около 136 GB), от 4 до 8 бит | Ближе к полной модели. При меньшем объёме RAM Strata читает часть с SSD, а это намного медленнее |

Даже если RAM меньше, чем в строке, может сработать: Strata сама переходит в
[режим с малым объёмом RAM](docs/MODELS.md#a-big-graphics-card-and-little-ram) (на английском). Будет медленнее, а с
маленькой видеокартой намного медленнее.

Другие варианты:

- **[Swift 1.5](docs/MODELS.md#swift-15)** — дообучение, которое думает меньше перед ответом, примерно при том же качестве и RAM.
- **[NVFP4](docs/NVFP4.md)** — 4-битная версия от NVIDIA для карт NVIDIA. Чтобы держать всех экспертов в RAM, ей нужно около 80 GB RAM.
- **[Qwen3.6-35B-A3B](docs/QWEN36.md)** — другая, меньшая модель. Читает картинки и умеет отвечать на несколько запросов сразу.
- **[Huihui-Ornith-1.5-35B-A3B-abliterated](docs/QWEN36_PACK.md#huihui-ornith-15-35b-a3b-abliterated)** и **[Cyber-Tiel-Coder-35B-A3B](docs/QWEN36_PACK.md#cyber-tiel-coder-35b-a3b)** — дообучения той же архитектуры. Они работают из пака Strata с int8 KV, для длинных контекстов (100K-262K) на карте 16 GB. По-русски: [docs/FORK.ru.md](docs/FORK.ru.md).
- **[Uncensored IQ3_XXS от OrcaRouter](docs/MODELS.md#orcarouter-uncensored-iq3_xxs)** настраивается вручную.

Все размеры, загрузки и что куда помещается: [docs/MODELS.md](docs/MODELS.md) (на английском).

## Насколько быстро?

На видеокарте 12 GB (RTX 5070, Ryzen 5 7600, 64 GB RAM). Результаты на других картах:
[скорость каждой модели](docs/MODELS.md#how-fast-is-each-size), [результаты сообщества](docs/COMMUNITY_BENCHMARKS.md)
(на английском).

| Модель | Скорость ответа | Скорость чтения промпта |
| --- | --- | --- |
| **Q2_0** | `████████████` 94 tokens/s | `████████████` 2,650 tokens/s |
| **IQ2_XS** | `██████████░░` 79 tokens/s | `█████████░░░` 2,090 tokens/s |
| **IQ3_XXS** | `████████░░░░` 62 tokens/s | `████████░░░░` 1,750 tokens/s |
| **IQ3_S** | `███████░░░░░` 53 tokens/s | `███████░░░░░` 1,620 tokens/s |
| **Coder** | `███████░░░░░` 55 tokens/s | `██████████░░` 2,180 tokens/s |

Токен — это примерно ¾ слова (в английском), так что 60 токенов в секунду быстрее, чем вы читаете. «Чтение промпта» —
это скорость, с которой Strata принимает длинный документ, код или историю чата.

Замерено на карте AMD 16 GB (RX 9070 XT, Ryzen 9 3900X, 47 GB RAM):

| Модель | Скорость ответа | Скорость чтения промпта |
| --- | --- | --- |
| **Q2_0** | `████████░░░░` 60 tokens/s | `█████░░░░░░░` 1,160 tokens/s |
| **IQ2_XS** | `███████░░░░░` 52 tokens/s | `█████░░░░░░░` 1,110 tokens/s |
| **Coder** | `██████░░░░░░` 44 tokens/s | `██████░░░░░░` 1,420 tokens/s |

Полоски в обеих таблицах в одном масштабе. Карта с большей VRAM быстрее: RTX 3090 (24 GB) должна писать примерно
100-140 токенов в секунду. Версия движка для каждого числа указана в [DETAILS.md](docs/DETAILS.md#speed-measured)
(на английском).

## Как пользоваться

### В приложении

В приложении есть **Chat**, **Monitor** модели и ваших GPU, CPU и RAM, страница **Models** и **Settings**. Чат умеет
работать в папке на вашем ПК. В режиме **Manual** он спрашивает, прежде чем менять файл или запускать команду. Напишите
`/loop 10m <что делать>`, чтобы сообщение повторялось каждые 10 минут, пока чат открыт.

Чат умеет искать в интернете через DuckDuckGo (или Bing), без аккаунта. Ключ поиска можно добавить в **Settings, Tools**.
Поиск — единственная функция, которая отправляет что-то за пределы ПК: слова запроса.

Чтобы запустить две модели, включите **Run multiple models** и дайте каждой модели свою карту одного производителя.

<p align="center"><img src="docs/media/app-chat.png" width="900" alt="Приложение Strata: чат, в котором агент построил небольшой воксельный сад с пагодой, страница открыта в предпросмотре справа"><br>
<sub>Чат в приложении Strata: агент написал небольшой воксельный сад с пагодой одним HTML-файлом, и страница открывается в предпросмотре рядом с разговором</sub></p>

### В Terminal

<p align="center"><img src="docs/media/terminal-monitor.png" width="900" alt="Обзор монитора Strata Terminal, пока модель пишет ответ"><br>
<sub><code>strata monitor</code>, пока модель пишет ответ: скорость, GPU, память и последние запросы</sub></p>

```sh
strata launch                                  # guided screens: model, context, pictures, access, then serve
strata launch --model q2_0 --yes --no-tui     # no questions: serve, print the address, return
strata launch --plan --model q2_0              # show what would happen; nothing changes
strata launch --status                         # what is being served now
strata launch --stop                           # stop it
strata monitor --url http://127.0.0.1:8080     # watch speed, GPU, memory and requests
strata update --check                          # is there a new engine? (strata update installs it)
strata doctor                                  # check the installed engine files
```

По порядку: экраны с вопросами (модель, контекст, картинки, доступ) и запуск; запуск без вопросов (печатает адрес и
возвращается); показать, что произойдёт, ничего не меняя; что сейчас запущено; остановить; следить за скоростью, GPU,
памятью и запросами; есть ли новый движок (`strata update` его ставит); проверить установленные файлы движка.

`strata --help` показывает всё. Запуск и работа никогда ничего не скачивают. Скачивают только установка, `strata launch`
(когда вы выбираете модель) и `strata update`. Чтобы подключаться к Strata с телефона или другого ПК, используйте
`strata launch --access lan`. Она создаёт API-ключ и без него в сеть не запустится. Браузер открывается, только если
добавить `--open`. Руководство: [docs/TERMINAL_LAUNCH.md](docs/TERMINAL_LAUNCH.md). Весь клиент:
[docs/TERMINAL.md](docs/TERMINAL.md) (на английском).

### С ИИ-агентами

Агент ставит Strata одной командой из варианта B и запускает
`strata launch --model NAME --yes --no-tui`. Шаги, флаги и коды выхода описаны в [docs/AI_SETUP.md](docs/AI_SETUP.md)
(на английском), правила репозитория — в [AGENTS.md](AGENTS.md) (на английском).

### Подключение других приложений

| Тип приложения | Base URL |
| --- | --- |
| Совместимые с OpenAI (большинство приложений и агентов) | `http://127.0.0.1:8080/v1` (любой API-ключ, любое имя модели) |
| API Anthropic (Claude Code и другие) | `http://127.0.0.1:8080`, без `/v1`. Эти приложения сами добавляют `/v1/messages`. Claude Code: `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([настройка](docs/DETAILS.md#the-responses-api-and-codex-cli), на английском) |

`strata connect` печатает точные настройки для OpenCode, Codex CLI, Claude Code, oh-my-pi, pi, Hermes Agent и OpenClaw.
`strata connect opencode --write` записывает файл, спросив разрешения, и сохраняет резервную копию.

### Картинки

Картинки включены по умолчанию для моделей, которые умеют их читать. Прикрепите или вставьте картинку в чат или
отправьте её из своего приложения. Если у видеокарты меньше 24 GB, картинки читает процессор (несколько секунд на
картинку, память карты не занимается); от 24 GB их читает видеокарта. Правило одинаковое для NVIDIA и AMD. Картинки
можно выключить для отдельной модели или выбрать, кто их читает: `--vision off`, `--vision gpu` или `--vision cpu`.

Откуда это правило: на Radeon AI PRO R9700 чтение на карте заняло 57 ms на картинку в 260 токенов, на процессоре 3.1 s.
На картах 16 GB (Tesla P100 и RTX A4000, Linux) чтение на карте стоило 3-5% скорости текста, потому что занимает около
1.4 GB, которые иначе взяла бы модель. На Mac картинки читает GPU Mac при любом объёме памяти (0.45 s на картинку в 260
токенов на M4 с 32 GB, около 1.2 GB общей памяти); процессору там нужно около 50 s на картинку, поэтому он работает,
только если попросить `--vision cpu`.

### Полезно знать

- Уровень размышления (**off, low, medium или high**) выбирается в меню чата или в «reasoning effort» вашего приложения. Off быстрее всего.
- По умолчанию Strata отвечает на один запрос за раз. Для нескольких сразу используйте `--parallel N` в `strata launch`
  или `"parallel": 2` в конфиге ([BATCHING.md](docs/BATCHING.md), на английском). На карте 12 GB каждый ответ от этого
  медленнее.
- Первое сообщение чата Strata читает целиком, около 1 минуты на 30,000 токенов. Следующие сообщения начинаются за секунды.
- Где хранятся чаты и весь API: [docs/INSTALL.md](docs/INSTALL.md#where-things-are-stored), [docs/DETAILS.md](docs/DETAILS.md#using-it) (на английском).

## Сборка из исходников

<details>
<summary>Windows, Linux и Mac из репозитория</summary>

[Скачайте Strata](https://github.com/Niko1221/Strata/archive/refs/heads/main.zip) и распакуйте или сделайте `git clone`.
**Windows:** дважды щёлкните `START-HERE.bat`. **Linux:** запустите `./setup.sh` в папке Strata.

**Mac (Apple Silicon, macOS 15 или новее):** один раз установите Command Line Tools от Apple командой
`xcode-select --install` (сам Xcode не нужен). Откройте Terminal в папке Strata и запустите `./setup.sh`. Он соберёт
движок для Mac на вашем Mac (около 7 минут), задаст те же вопросы, скачает модель и запустит её. В следующий раз
`./setup.sh` запускает сразу. Какой размер подходит вашему Mac: [docs/MAC.md](docs/MAC.md) (на английском).

Установщик находит вашу карту и ставит нужный движок. Он спрашивает, какую модель и какой размер взять, сколько
контекста (сколько текста модель держит в голове) и читать ли картинки. Нажмите Enter, чтобы принять рекомендованный
ответ. Потом он скачивает модель (около 70 GB) и запускает её. Если загрузка остановилась, запустите снова, и она
продолжится. Браузер откроет страницу Strata по адресу `http://127.0.0.1:8080`.

> Пока модель запускается, ПК может тормозить или не отвечать 1-3 минуты (дольше всего в первый раз). Strata загружает
> 35-55 GB в RAM и закрепляет часть для видеокарты. Подождите и не закрывайте окно.

В следующий раз снова запустите `START-HERE.bat` (или `./setup.sh`). Он стартует сразу и ничего не качает повторно.
Закройте его окно, чтобы остановить модель. `UPDATE.bat` (`./update.sh`) обновляет Strata, не запуская её. Обновление,
Docker, несколько карт, куда кладутся файлы и все параметры: [docs/INSTALL.md](docs/INSTALL.md) (на английском).

Чтобы замерить свой ПК, запустите `BENCH.bat` (`./bench.sh`). Это занимает 5-10 минут и пишет отчёт, которым можно
поделиться ([как](docs/COMMUNITY_BENCHMARKS.md#run-the-benchmark), на английском).

**Необязательно: больше скорости на одной карте, когда вся модель помещается в RAM.** Две opt-in настройки от
RubenTorney (#1904, #1905). Они помогают, когда у вас одна видеокарта и RAM вмещает всех экспертов, например Q2_0 или
IQ3_XXS на ПК с 64 GB. Откройте `strata-<model>.json` в папке данных Strata
([где она](docs/INSTALL.md#where-things-are-stored), на английском) и добавьте:

- `"--adapt-async", "1"` в список `"args"`. Кэш экспертов тогда обновляется во вспомогательном потоке, а не
  приостанавливает ответ. Замерено на RTX 5070 (Windows, Q2_0): +4-5% декода, +7-10% на коде и длинных документах.
  Ответы могут немного отличаться от варианта по умолчанию и не меняются от запуска к запуску.
- `"STRATA_PIN_BY_NEED": "1"` в блок `"env"` (Windows). Windows может закрепить для видеокарты только около половины RAM,
  а эта настройка первыми закрепляет экспертов, которые нужны карте. Замерено на RTX 5070: +4.4% к чтению промпта.

```json
"args": [ ..., "--adapt-async", "1" ],
"env": { "STRATA_PIN_BY_NEED": "1" }
```

После изменения перезапустите Strata. Чтобы отменить, удалите эти две записи.

</details>

## Как это работает?

Такие модели обычно работают на серверах с сотнями гигабайт видеопамяти. У вашей видеокарты 12-24 GB. Strata
помещает модель, распределяя работу по всему ПК. Представьте библиотеку.

- Модель — это команда из 24,576 маленьких специалистов («экспертов»), как 24,576 справочников. Каждому слову нужны только 10 из них.
- **Видеокарта — это стол.** Он маленький и быстрый. На нём открыты примерно 4,000 самых ходовых книг.
- **RAM — это полки в читальном зале.** Там стоят все 24,576 книг. Когда слову нужна книга, которой нет на столе,
  процессор сразу читает её с полки, пока карта продолжает работать.
- **SSD — это архив.** В нём лежит справочная таблица на 29 GB. Модель читает из неё несколько строк на слово, поэтому
  держать её в RAM не нужно.

<p align="center"><img src="docs/media/how-it-works.svg" width="860" alt="24,576 экспертов модели: самые загруженные на видеокарте, все в RAM, справочная таблица на SSD"></p>

Небольшой помощник ещё и угадывает следующие несколько слов. Большая модель проверяет их все разом и оставляет
правильные. Ответ тот же, но в 1.6-1.8 раза быстрее. Длинные тексты читаются большими кусками, до 8,192 токенов за
раз, со скоростью больше 1,000 токенов в секунду.

<p align="center"><img src="docs/media/guess-and-check.svg" width="860" alt="Небольшой помощник угадывает следующие слова; большая модель проверяет их все разом и оставляет правильные"></p>

Подробнее: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md). Каждая часть и её числа:
[подробности](docs/DETAILS.md#how-it-works) и [статья](docs/paper/Strata-Paper.pdf) (на английском).

## Что-то пошло не так?

- **ПК завис при первом запуске Strata.** Она загружает модель в RAM. Подождите и не закрывайте окно. Всё ещё висит
  через 10 минут? Перезагрузите ПК, закройте другие программы и попробуйте снова или выберите размер поменьше.
- **Остановилось во время загрузки или установки.** Снова запустите приложение или `strata launch`, либо снова
  запустите `START-HERE.bat` (или `./setup.sh`). Всё продолжится с того же места.
- **Очень медленно, лампочка диска постоянно мигает или пишет «the engine stopped unexpectedly».** На ПК не хватает
  свободной RAM. Закройте другие программы (браузеры едят много) или выберите размер поменьше, например Q2_0 или IQ2_XS.
- **Пишет, что для этого ПК нет движка.** В приложении откройте **Settings, Engine** и нажмите **Update engine**. В
  Terminal выполните `strata update`. `strata doctor` показывает, какие файлы движка установлены.
- **Пишет, что порт 8080 уже занят.** Strata уже работает. Поищите её окно.

Другие проблемы и решения: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (на английском). Не получается? Откройте
[issue](https://github.com/Niko1221/Strata/issues). В приложении приложите файл из **Settings, Engine, Diagnostics, View
logs, Save logs**. В Terminal вставьте вывод `strata doctor`. При сборке из исходников приложите `strata-<model>.log` из
папки Strata. О проблеме безопасности сообщайте закрыто: [SECURITY.md](SECURITY.md) (на английском).

## Благодарности и лицензия

Модель — [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) от команды Qwen. Её сжимали
[ISTA-DASLab](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF), UkisAI (Swift 1.5), agentionai (Gyro)
и Unsloth. Strata использует части [llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). Все благодарности:
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#credits) (на английском). Strata распространяется с открытым кодом по
[лицензии MIT](LICENSE). У нескольких частей и у каждой модели свои лицензии
([какие](docs/HOW_IT_WORKS.md#license), на английском).

## Участие

Нашли ошибку или хотите прислать изменение или бенчмарк? Сначала прочитайте [CONTRIBUTING.md](CONTRIBUTING.md)
(на английском). Там сказано, что приложить, чтобы другие могли проверить вашу работу.

## Поддержать Strata

Strata бесплатна и распространяется по MIT. Я делаю и тестирую её на том железе, которое удаётся достать. Если на
вашем ПК она работает хорошо, чашка кофе помогает мне тестировать новые карты и чинить то, о чём вы сообщаете. Без
давления. Пользоваться и сообщать о находках помогает не меньше.

<a href="https://buymeacoffee.com/strataengine"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>

Хотите спонсировать Strata? Напишите мне через [GitHub](https://github.com/Niko1221).
