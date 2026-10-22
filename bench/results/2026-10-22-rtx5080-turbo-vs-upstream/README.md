# Strata Turbo (форк) против пути upstream: Cyber-Tiel-Coder UD-IQ4_XS, 2026-10-22

## На чём и как мерили

- ПК: RTX 5080 16 GB (PCIe 5.0 x8), i9-14900K (8P+16E), 48 GB DDR5-7600, Windows 11, CUDA 13.4.
- Движок: один и тот же `E:\Projects\Strata-main\build\strata.exe` (сборка 2026-10-22 15:56, main `a7ac6624`, «Fork version 1.1.0»). В нём оба пути.
- Модель: `D:\Strata-data\models\cyber-tiel-coder-UD-IQ4_XS\Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf`, пак `D:\Strata-data\packs\cyber-tiel-iq4_xs`.
- **FORK**: пак-путь движка Flash-Next с аргументами и env живого сервера (`E:\Projects\Strata-integrate\strata-tiel-main.json`). Серверные ключи `--conversation-*` убраны, это CLI. Контекст 262144, `--kv int8 --kv-grow`, `--spec 4` с MTP из GGUF. Измерено CLI `--max-new 256 --greedy --tokens-file`. Путь по логу: `native pack`, `expert cache 7424-7586 slots (10.2-10.5 GiB)`, `elastic K/V`.
- **UPSTREAM**: тот же GGUF без `--pack` и без STRATA_* env. Аргументы, которые upstream-setup пишет для `--family qwen36` (`install_own_path`, ветка без пака): `--native <gguf> --max-context <ctx> --prefill auto --mtp 2`, плюс `--pool-workers 15` (`recommend_pool_workers` для 8P+16E: 8-1+16/2). По логу это путь `src/qwen35`: строки `strata-q36:`, fp32 K/V на весь контекст, гибрид, часть экспертов в VRAM, остальное на CPU.
  - Контекст upstream: 32768 для 2K и 32K (это значение setup пишет для карты 16 GB). Для 66K и 128K взят наименьший контекст, в который помещается запрос: 66560 и 129024. Setup предложил бы 131072, так что выбор в пользу upstream.
  - `strata-q36` в CLI берёт токены только списком `--tokens` в командной строке. Промпт длиннее ~4K токенов в лимит строки Windows (32K символов) не влезает. Поэтому upstream мерили через его собственный `--serve`: один запрос `GEN 256 <ids>` на процесс, жадно (без temperature), тот же код `E.process` + `spec_step`, что и в CLI. Сверка на 2K в одном окне: CLI 5.72 с / 53.7 ток/с, serve 5.22-5.63 с / 55.7-57.6 ток/с.
- Промпты: 2K = `ornith_2048_0.txt` (2048); 32K = первые 32000 токенов `ornith_ctx66000.txt`; 66K = `ornith_ctx66000.txt` (66000); 128K = 66000 + следующие 62000 токенов того же текста из `t130k.txt` (128000, без повторов). Токены как есть, без шаблона чата. Файлы лежат в `tok\`.
- Каждый прогон идёт в отдельном процессе, FORK и UPSTREAM чередуются. «Промпт» у FORK — строка движка `prefill ... ms`, у UPSTREAM — `read in ... ms`. В обоих случаях это чтение промпта без прогрева. TTFT FORK из CLI дан отдельно: в нём ещё 1.0-1.9 с разовой записи CUDA-графов окон проверки. Upstream делает её в прогреве до замера (5-7 с), сервер форка — один раз за запуск.
- VRAM: пик `nvidia-smi memory.used` всей карты, раз в секунду. Без движка карта занята на 0.75-1.1 GB.

## Результаты (медианы)

| Размер | Арм | Прогонов | Промпт, с | Промпт, ток/с | Генерация, ток/с (прогоны) | Пик VRAM, MiB | Заметки |
|---|---|---:|---:|---:|---|---:|---|
| 2K (2048) | FORK | 3 | 0.52 | 3941 | 290.8 (292.9, 290.8, 289.1) | 15471 | TTFT 1.51 с; черновики приняты 157-161 из 203-212 |
| 2K (2048) | UPSTREAM | 3 | 4.72 | 434 | 71.2 (72.2, 66.4, 71.2) | 15607 | ctx 32768; 110 из 256 экспертов на слой в VRAM (6.24 GiB); 45% строк экспертов на GPU; MTP 145/220 |
| 32K (32000) | FORK | 3 | 4.41 | 7253 | 285.9 (285.9, 283.9, 287.6) | 15423 | TTFT 5.42 с |
| 32K (32000) | UPSTREAM | 3 | 74.68 | 428 | 50.6 (50.8, 50.6, 50.5) | 15448 | ctx 32768; 110/256 в VRAM; 41% строк на GPU |
| 66K (66000) | FORK | 3 | 10.34 | 6385 | 252.9 (246.1, 254.8, 252.9) | 15443 | TTFT 11.45 с; K/V выросли до 73728 ячеек (0.82 GiB) |
| 66K (66000) | UPSTREAM | 3 | 185.88 | 355 | 15.6 (15.6, 15.6, 15.0) | 15559 | ctx 66560; 82/256 в VRAM (4.65 GiB); 31% строк на GPU |
| 128K (128000) | FORK | 2 | 24.80 | 5162 | 193.9 (193.9; второй 115.3 под чужой нагрузкой CPU) | 15310 | TTFT 26.56 с; K/V до 131072 ячеек (1.42 GiB) |
| 128K (128000) | UPSTREAM | 1 | 512.68 | 250 | 6.7 | 15025 | ctx 129024; 19/256 в VRAM (1.08 GiB); 8% строк на GPU |

2K и 32K — окно B (CPU свободен), 66K и 128K — окно C (strata.exe с приоритетом AboveNormal, см. оговорки). Контрольная пара 32K в окне C: FORK 4.53 с / 279.9 ток/с, UPSTREAM 74.45 с / 50.5 ток/с, то есть совпадает с окном B в пределах 3%.

### Во сколько раз FORK быстрее

| Размер | Промпт (prefill) | Промпт по TTFT FORK | Генерация |
|---|---:|---:|---:|
| 2K | 9.1x | 3.1x | 4.1x |
| 32K | 16.9x | 13.8x | 5.7x |
| 66K | 18.0x | 16.2x | 16.2x |
| 128K | 20.7x | 19.3x | 28.9x (17.2x по второму прогону FORK) |

### Предельный контекст на карте 16 GB

- FORK: 262144. Все прогоны FORK шли с `--max-context 262144`; K/V int8 растут вместе с контекстом.
- UPSTREAM: стартует и отвечает на 2K-промпт максимум при **163840**. При этом в VRAM 0 из 256 экспертов на слой, все эксперты считаются на CPU: промпт 2K 274 ток/с, генерация 33.7 ток/с. На 172032, 180224, 196608 и 262144 не стартует: `not enough VRAM left for the hybrid experts' buffers and slots (128 MiB needed, 0 MiB free after the weights, the context and the sessions)`. Шаг поиска 8192.

### Совпадение текста

Жадные токены FORK и UPSTREAM совпадают в первых 32 из 32 на 2K, 32K и 66K. На 128K они расходятся после 6-12 токенов. Два прогона FORK на 128K расходятся и между собой: эксперты на CPU и на GPU округляют по-разному. Вывод не вырожден: 52-70 разных токенов из 256, без NaN.

## Оговорки

- На ПК параллельно шли чужие задачи: GitHub Actions `Asofwar/GsmNotify` (Android CI на self-hosted runner), Gradle-сборки и Android-эмуляторы (`qemu-system-x86_64-headless`) других сессий Claude, а также `pool_native_bench`. Иногда они занимали 3-24 ядра. Пул экспертов на CPU от этого замедлялся в 2-3 раза: строка `pool multi` падала с 45-56 до 15-19 GB/s. Окно A (19:58-20:16) целиком шло под CI, его числа отброшены (они в `runs-A\`). Окно B прервано на 66K из-за эмуляторов. В окне C оба арма запускались с приоритетом AboveNormal: под 2.8 ядрами чужой нагрузки upstream 66K замедлился только на 3%.
- 128K: UPSTREAM n=1 (по решению координатора), во время прогона чужие процессы занимали 4.4 ядра. У upstream на 128K 92% строк экспертов считается на CPU, поэтому его число может быть немного занижено, а ускорение FORK завышено. Второй прогон FORK 128K (115 ток/с) шёл под 3.2 ядрами чужой нагрузки, пул был 14.9 GB/s против 56.4 в первом. В таблице генерация FORK 128K взята по первому, чистому прогону.
- `--pool-workers`: FORK 7 (откалибровано, как на живом сервере), UPSTREAM 15 (рекомендация setup). Upstream `--calibrate` не запускался.
- Пик VRAM у обоих армов близок к полной карте: оба отдают свободную память под эксперты. Разница в том, на что уходит VRAM. У FORK это 7400-7600 слотов экспертов (10.2-10.5 GiB) и K/V int8 по мере роста. У UPSTREAM это fp32 K/V на весь контекст сразу (44 KiB на токен), поэтому экспертов в VRAM 110 → 82 → 19 → 0 на слой при 32K → 66K → 129K → 164K.
- Промпты — сырой текст без шаблона чата. Генерация — 256 жадных токенов (FORK `--spec 4`, UPSTREAM `--mtp 2`). Доля принятых черновиков: FORK 0.75-0.90, UPSTREAM 66-82%.
- Не измерено: режим `--serve` форка (здесь CLI), сэмплинг (temperature 0.6), параллельные запросы, другие карты.

## Простой 8096

| Окно | Остановка | Снова loaded | Простой |
|---|---|---|---:|
| попытка 1 (ошибка харнесса) | 19:58:51 | 19:59:38 | 47 с |
| A (под CI, отброшено) | 20:04:21 | 20:16:53 | 752 с |
| B | 20:19:22 | 20:44:40 | 1517 с |
| C | 20:50:38 | 21:35:48 | 2710 с |
| **итого** | | | **5026 с ≈ 84 мин** |

Между окнами сервер работал. Каждый раз его останавливали, когда `/status` показывал busy false и queued 0, и поднимали через `run-tiel-main.bat`, после чего `/v1/models` отвечал `loaded`. GPU-лок брали через `strata_control.tune_session.FileLock` (`locked_run.py`).

## Точные команды (cwd `E:\Projects\Strata-main`, в PATH CUDA 13.4 `bin` и `bin\x64`)

FORK (env: `STRATA_ATTN_SPLITS=256 STRATA_ADAPT_OVERLAP=1 STRATA_SYSMEM_PROBE=1 STRATA_ATTN_WINDOW=1 STRATA_ATTN_WINDOW_PREC=2 STRATA_IQ3S_MT1=1 STRATA_PROMPT_ATTN_DENSE_IMMA=4 STRATA_ATTN_WINDOW_SMALL=1 STRATA_MMQ_KQ=1 STRATA_ARENA_WSLOCK=1`):

```
strata.exe --pack D:\Strata-data\packs\cyber-tiel-iq4_xs --native D:\Strata-data\models\cyber-tiel-coder-UD-IQ4_XS\Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf --expert-profile E:\Projects\Strata-main\data\expert-profile-qwen36.bin --expert-cache auto --prefill auto --spec 4 --mtp D:\Strata-data\models\cyber-tiel-coder-UD-IQ4_XS\Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf --mtp-draft-vocab E:\Projects\Strata-main\data\draft_vocab_cyrillic.bin --max-context 262144 --kv int8 --pcie-frac 0.00 --spec-min-p 0.50 --pool-workers 7 --adapt-every 1 --adapt-swaps 160 --adapt-decay 0.97 --kv-grow --max-new 256 --greedy --tokens-file <scratchpad>\tok\p{2k,32k,66k,128k}.txt
```

UPSTREAM (без STRATA_* env; `<ctx>` = 32768 / 32768 / 66560 / 129024; stdin — одна строка `GEN 256 id,id,...`):

```
strata.exe --native D:\Strata-data\models\cyber-tiel-coder-UD-IQ4_XS\Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf --max-context <ctx> --prefill auto --mtp 2 --pool-workers 15 --serve < <scratchpad>\tok\p{2k,32k,66k,128k}.req
```

Сверка upstream CLI (2K): тот же набор, но `--max-context 32768 ... --max-new 256 --greedy --tokens 18295,2600,...` (2048 id).

Проба предельного контекста (`<ctx>` = 262144, 196608, 163840, 180224, 172032; stdin `GEN 64 <2048 id из ornith_2048_0>`, файл `tok\p2k-probe.req`; в логах прогона он называется `tok\p4k.req`, потому что файл был перезаписан перед пробой):

```
strata.exe --native <gguf> --max-context <ctx> --prefill auto --mtp 2 --pool-workers 15 --serve < <scratchpad>\tok\p4k.req
```

`<scratchpad>` = `C:\Users\Admin\AppData\Local\Temp\claude\E--Projects-Strata-fork\8b992b3f-15b1-4b4f-bbf8-0699725394a0\scratchpad`. Сырые логи каждого прогона (`.cmd.txt`, `.out`, `.err`, `.vram.csv`, `.meta` с чужой нагрузкой CPU): `runs2\` (окно B), `runs3\` (окно C), `runs-A\` (окно A, отброшено). Журнал — `progress.txt`, нагрузка CPU чужими процессами — `cpu_foreign.csv`, таблицы — `final.py runs2|runs3`.
