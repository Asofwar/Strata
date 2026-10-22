<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/strata-turbo-lockup-dark.svg">
    <img src="docs/media/strata-turbo-lockup-light.svg" alt="Strata Turbo" width="440">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <b>Русский</b> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">Агенты для кода с контекстом 262K на одной видеокарте 16 GB</h3>

<p align="center">Форк <a href="https://github.com/Niko1221/Strata">Strata</a> от Asofwar · Windows + NVIDIA · бесплатно и с открытым кодом</p>

<p align="center"><b>В 16–18 раз быстрее upstream Strata на контексте 66K</b> — на той же карте и модели</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata-Turbo/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata-Turbo?label=%D1%80%D0%B5%D0%BB%D0%B8%D0%B7" alt="Релиз"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata-Turbo" alt="Лицензия MIT"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Документация форка"></a>
  <a href="#поддержать"><img src="https://img.shields.io/badge/%D0%B4%D0%BE%D0%BD%D0%B0%D1%82-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata запускает большие MoE-модели на обычном ПК: самые нужные эксперты лежат на видеокарте, остальные в RAM. Форк
настроен под агентов для кода с длинным контекстом на моделях Qwen3.6-35B-A3B **Cyber-Tiel-Coder** и **Ornith**: int8
K/V, MTP-черновики и свои ядра для длинного контекста. Сервер понимает API OpenAI и Anthropic, к нему подключаются
Codex CLI, Claude Code, OpenCode и другие агенты. Без аккаунта и телеметрии.

## Скорость

Один ПК, один файл модели, один день (RTX 5080 16 GB, i9-14900K, 48 GB DDR5-7600, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS): Strata Turbo против собственного пути upstream Strata для этой модели.

| Контекст | Чтение промпта, Turbo / upstream | Генерация, ток/с, Turbo / upstream |
| ---: | ---: | ---: |
| 2K | 0.5 s / 4.7 s (9×) | 291 / 71 (4×) |
| 32K | 4.4 s / 75 s (17×) | 286 / 51 (6×) |
| 66K | 10 s / 186 s (18×) | 253 / 16 (16×) |
| 128K | 25 s / 513 s (21×) | 194 / 7 (29×, один прогон upstream) |

На карте 16 GB upstream стартует максимум с контекстом 160K, Strata Turbo работает с 262K (на 200K промпт читается за 49 с, генерация 161–171 ток/с). Методика и логи: [bench/results/2026-10-22-rtx5080-turbo-vs-upstream](bench/results/2026-10-22-rtx5080-turbo-vs-upstream/README.md).

Возврат к разговору на ~123K токенов после другого такого же — 2.5 с вместо 33 с (разговоры паркуются на NVMe).
Агентный бенчмарк: 53 из 60 задач с кодом. Все замеры: [docs/FORK.ru.md](docs/FORK.ru.md).

## Установка

**Самый простой способ** (Windows, NVIDIA RTX 20 и новее, 32 ГБ памяти): скачайте `Strata-Turbo-Install.cmd` из
[последнего релиза](https://github.com/Asofwar/Strata-Turbo/releases/latest) и запустите двойным щелчком. Он ничего не
спрашивает, ставит Cyber-Tiel-Coder и создаёт значок «Strata Turbo» на рабочем столе. По шагам: [docs/EASY_INSTALL.ru.md](docs/EASY_INSTALL.ru.md).

**Windows**, NVIDIA RTX 20 и новее (драйвер 580+), в PowerShell:

```powershell
irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex
```

Скрипт скачивает [последний релиз](https://github.com/Asofwar/Strata-Turbo/releases/latest), сверяет его с
`SHA256SUMS.txt`, распаковывает в `%LOCALAPPDATA%\Strata-Turbo` и запускает setup: тот спросит модель и скачает её
(Cyber-Tiel — около 17 GB). Вручную: распакуйте `Strata-Turbo-<версия>-windows-cuda13.zip` в папку без пробелов и
запустите `START-HERE.bat --setup --family cyber-tiel`.

**Linux** (форк не проверял, движок собирается из исходников):

```sh
curl -fsSL https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.sh | sh
```

**Через ИИ-ассистента:** вставьте в Claude Code, Codex или Cursor
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata-Turbo - follow docs/AI_SETUP.md in that repository.`

Следующий запуск — снова `START-HERE.bat`; обновление — ещё раз однострочник (или `UPDATE.bat` в клоне). `strata update`
не используйте: подписанного фида у форка нет. Все варианты, другое железо и где лежат файлы:
[docs/INSTALL.md](docs/INSTALL.md) (на английском).

## Модели

| Модель | Setup | Заметки |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | по умолчанию в форке: думает короче, реже зацикливается |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | то же качество в бенчмарках, медленнее |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, выбрать размер | модель upstream: от 32 GB RAM и видеопамяти вместе, размеры в [docs/MODELS.md](docs/MODELS.md) |

Для ответов на русском добавьте `--draft-vocab cyrillic`. Проверки качества: [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Подключение приложений

| Тип приложения | Адрес |
| --- | --- |
| Совместимые с OpenAI (большинство приложений и агентов) | `http://127.0.0.1:8080/v1` (любой ключ, любое имя модели) |
| API Anthropic (Claude Code) | `http://127.0.0.1:8080` — `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([настройка](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

Сервер слушает только `127.0.0.1`. Прежде чем открывать его в сеть, задайте API-ключ ([docs/SAFETY.md](docs/SAFETY.md)).

## Документация

- [docs/FORK.ru.md](docs/FORK.ru.md) — что добавляет форк, все замеры, рекомендуемый конфиг
- [docs/ROADMAP.ru.md](docs/ROADMAP.ru.md) — планы: картинки, звук и видео, скорость, качество
- [docs/INSTALL.md](docs/INSTALL.md) — варианты установки, AMD / Intel / Mac / несколько карт (пути upstream, форк их не проверял), настройки
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — если что-то пошло не так; ошибки — в [issues](https://github.com/Asofwar/Strata-Turbo/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) — как большая модель помещается в ПК; все детали и числа: [DETAILS.md](docs/DETAILS.md), [статья](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

Документы, кроме `*.ru.md`, на английском.

## Авторы и лицензия

Strata создал [Niko1221](https://github.com/Niko1221/Strata); форк добавляет работу над длинным контекстом. Модели:
команда Qwen, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) и [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai и Unsloth (размеры Flash-Next). Strata использует части
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). Лицензия MIT ([LICENSE](LICENSE)); у некоторых частей и у
всех моделей свои лицензии ([какие](docs/HOW_IT_WORKS.md#license)).

## Поддержать

Strata Turbo бесплатна. Если форк помогает, поддержите его работу в Gram (TON) на кошелёк в Telegram:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), кошелёк в Telegram: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[отправить из TON-кошелька](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(только сеть TON: перевод из другой сети потеряется)
