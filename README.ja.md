<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/strata-turbo-lockup-dark.svg">
    <img src="docs/media/strata-turbo-lockup-light.svg" alt="Strata Turbo" width="440">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <b>日本語</b> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">16 GB のグラフィックスカード 1 枚で、262K コンテキストのコーディングエージェント</h3>

<p align="center"><a href="https://github.com/Niko1221/Strata">Strata</a> の Asofwar 版フォーク · Windows + NVIDIA · 無料のオープンソース</p>

<p align="center"><b>66K コンテキストで upstream Strata の 16〜18 倍高速</b>（同じカード・同じモデル）</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata-Turbo/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata-Turbo?label=%E3%83%AA%E3%83%AA%E3%83%BC%E3%82%B9" alt="リリース"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata-Turbo" alt="MIT ライセンス"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="フォークのドキュメント"></a>
  <a href="#支援のお願い"><img src="https://img.shields.io/badge/%E5%AF%84%E4%BB%98-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata は、大規模な Mixture-of-Experts モデルを普通の PC で動かします。よく使われるエキスパートをグラフィックスカードに、残りを RAM に置く方式です。
このフォークは、Qwen3.6-35B-A3B 系の **Cyber-Tiel-Coder** と **Ornith** で、長いコンテキストを扱うコーディングエージェント向けに
調整してあります。int8 K/V、MTP ドラフト、独自の長コンテキスト用カーネルを備えています。OpenAI と Anthropic の API に対応しているため、
Codex CLI、Claude Code、OpenCode などのエージェントから接続できます。アカウント不要、テレメトリなし。

## 速度

同じ PC・同じモデルファイル・同じ日に計測（RTX 5080 16 GB、i9-14900K、48 GB DDR5-7600、Windows 11、Cyber-Tiel-Coder UD-IQ4_XS）。Strata Turbo と、このモデルに対する upstream Strata 本来の経路を比較しています。

| コンテキスト | プロンプト読み込み（Turbo / upstream） | 生成 tokens/s（Turbo / upstream） |
| ---: | ---: | ---: |
| 2K | 0.5 s / 4.7 s (9×) | 291 / 71 (4×) |
| 32K | 4.4 s / 75 s (17×) | 286 / 51 (6×) |
| 66K | 10 s / 186 s (18×) | 253 / 16 (16×) |
| 128K | 25 s / 513 s (21×) | 194 / 7 (29×, upstream は 1 回のみ) |

16 GB のカードでは upstream は最大 160K のコンテキストでしか起動しません。Strata Turbo は 262K で動作します（200K ではプロンプト読み込み 49 秒、生成 161〜171 tokens/s）。方法とログ：[bench/results/2026-10-22-rtx5080-turbo-vs-upstream](bench/results/2026-10-22-rtx5080-turbo-vs-upstream/README.md)

別の会話を挟んだあとで約 123K の会話に戻る場合、かかる時間は 33 秒ではなく 2.5 秒です（会話は NVMe に退避されます）。
エージェントのベンチマーク：コーディングタスク 60 件中 53 件。すべての計測値は [docs/FORK.ru.md](docs/FORK.ru.md) にあります。

## インストール

**Windows**、NVIDIA RTX 20 以降（ドライバー 580 以上）、PowerShell で：

```powershell
irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex
```

スクリプトは[最新リリース](https://github.com/Asofwar/Strata-Turbo/releases/latest)をダウンロードし、`SHA256SUMS.txt` と照合して
`%LOCALAPPDATA%\Strata-Turbo` に展開し、setup を起動します。setup はモデルを尋ねてダウンロードします（Cyber-Tiel：約 17 GB）。
手動の場合は、`Strata-Turbo-<version>-windows-cuda13.zip` をスペースを含まないフォルダーに展開し、
`START-HERE.bat --setup --family cyber-tiel` を実行してください。

**Linux**（フォークでは未検証。エンジンはソースからビルドします）：

```sh
curl -fsSL https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.sh | sh
```

**コーディングアシスタントに任せる場合：** 次の 1 行を貼り付けてください。
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata-Turbo - follow docs/AI_SETUP.md in that repository.`

次回以降の起動は `START-HERE.bat` です。更新は同じワンライナーをもう一度実行します（クローンでは `UPDATE.bat`）。
`strata update` は使わないでください。このフォークは署名付きフィードを公開していません。全オプション、他のハードウェア、
ファイルの置き場所は [docs/INSTALL.md](docs/INSTALL.md) を参照してください。

## モデル

| モデル | Setup | 備考 |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | フォークの既定：思考が短く、ループしにくい |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | ベンチマークでは同等の品質、ただし遅い |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat` でサイズを選択 | upstream のモデル：RAM と VRAM の合計で 32 GB 以上が必要。サイズは [docs/MODELS.md](docs/MODELS.md) |

ロシア語で回答させるには `--draft-vocab cyrillic` を追加します。品質チェック：[EVAL.ru.md](docs/EVAL.ru.md)、
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md)。

## アプリを接続する

| アプリの種類 | ベース URL |
| --- | --- |
| OpenAI 互換（ほとんどのアプリとエージェント） | `http://127.0.0.1:8080/v1`（API キーは何でも可、モデル名も何でも可） |
| Anthropic API（Claude Code） | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API（Codex CLI） | `http://127.0.0.1:8080/v1/responses`（[設定方法](docs/DETAILS.md#the-responses-api-and-codex-cli)） |

サーバーは `127.0.0.1` のみで待ち受けます。ネットワークに公開する前に API キーを設定してください（[docs/SAFETY.md](docs/SAFETY.md)）。

## ドキュメント

- [docs/FORK.ru.md](docs/FORK.ru.md)：フォークの追加内容、すべての計測値、推奨設定（ロシア語）
- [docs/INSTALL.md](docs/INSTALL.md)：インストールのオプション、AMD / Intel / Mac / 複数カード（upstream の手順で、フォークでは未検証）、設定
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)：うまくいかないとき。バグは [issues](https://github.com/Asofwar/Strata-Turbo/issues) へ
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)：大規模モデルが PC に収まる仕組み。各部分と数値の詳細は [DETAILS.md](docs/DETAILS.md)、[論文](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md)

ドキュメントは英語です。ロシア語なのは `FORK.ru.md`、`EVAL.ru.md`、`AGENT-EVAL.ru.md` だけです。

## クレジットとライセンス

Strata は [Niko1221](https://github.com/Niko1221/Strata) によるものです。このフォークは、その上に長コンテキスト対応を加えています。
モデル：Qwen チーム、[peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll)（Cyber-Tiel-Coder）、
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) と [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
（Ornith）、ISTA-DASLab、UkisAI、agentionai、Unsloth（Flash-Next の各サイズ）。Strata は
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp) の一部を使用しています。MIT ライセンス（[LICENSE](LICENSE)）。
一部のコードと、すべてのモデルには個別のライセンスがあります（[詳細](docs/HOW_IT_WORKS.md#license)）。

## 支援のお願い

Strata Turbo は無料です。役に立ったら、Telegram ウォレットへの Gram (TON) の送金で、フォークの開発を支援してください：

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON)、Telegram ウォレット：QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[TON ウォレットから送金](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
（TON ネットワーク限定：他のネットワークからの送金は失われます）
