<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <b>日本語</b> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a> · <a href="README.ru.md">Русский</a></p>

<h3 align="center">最先端のモデルを、手元のゲーミングPCで動かす</h3>

<p align="center">NVIDIA、AMD、Intel に対応 · Windows、Linux、Mac · 無料のオープンソース</p>

<p align="center">
  <a href="https://github.com/Niko1221/Strata/releases"><img src="https://img.shields.io/github/v/release/Niko1221/Strata?include_prereleases&label=upstream%20release" alt="Upstream latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="MIT license"></a>
  <a href="https://github.com/Asofwar/Strata/stargazers"><img src="https://img.shields.io/github/stars/Asofwar/Strata?style=flat" alt="GitHub stars"></a>
</p>

<p align="center"><a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4"><img src="docs/media/pagoda-preview.webp" width="720" alt="A voxel pagoda garden that Strata's model wrote, running in the browser"></a><br>
<sub>ボクセルの塔の庭園。1回のプロンプトで生成し、RTX 5070 上の Strata で動かしています（IQ3_S、128K コンテキスト） ·
<a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4">動画全体（49秒）</a></sub></p>

Strata は **[Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)** を動かします。1250億パラメータのモデルで、
ふつうはサーバーが必要ですが、Strata なら一般的なPCで使えます。チャット、コード作成、画像の読み取りができ、
お使いのアプリやコーディングエージェントとも連携します。チャットとファイルはPCの外に出ません。

**はじめての方へ。** まず[必要な環境](#必要な環境)を確認して、[インストール](#インストール)してください。

- **ゲーミングPCで動きます。** RAMとグラフィックスメモリの合計が32 GBあれば始められます。
- **お使いのツールと連携します。** OpenAI と Anthropic の API に対応しているので、Claude Code、Codex CLI、OpenCode などのエージェントから接続できます。
- **画像を読めます。** 初期設定でオンです。
- **無料です。** MIT ライセンス。アカウントもクラウドも不要です。
- **プライバシーを守ります。** テレメトリはありません。Strata が何をダウンロードするか、いつインターネットを使うか、ダウンロードをどう検証するかは [docs/SAFETY.md](docs/SAFETY.md) に書いてあります。

バージョン 0.2.1 · エンジン 0.1.46

## 必要な環境

**RAMとグラフィックスメモリ（VRAM）の合計が、少なくとも32 GB必要です。** MacやRyzen AI Maxでは、ユニファイドメモリがその量にあたります。
メモリが多いほど、大きなモデルを使えたり、速く動いたりします。

- RAM 32 GBのPCに12〜16 GBのグラフィックスカードがあれば、Coder が動きます。
- RAM 64 GBなら、どのサイズも動きます。

| お使いのPC | 詳細 |
| --- | --- |
| **NVIDIA** GeForce RTX 20、30、40、50 シリーズ（12 GB以上） | [インストール](#インストール)（Windows: リリースの zip）。 |
| **AMD** Radeon RX 6800 以降、Radeon AI PRO R9700（12 GB以上） | [AMD のカード](docs/AMD_HIP.md) |
| **Intel** Arc | [Intel Arc](docs/INTEL_ARC.md)、[Intel エンジン](docs/INTEL.md) |
| **Apple Silicon の Mac**（M1 以降、macOS 15 以降） | [Mac](docs/MAC.md) |
| **AMD Ryzen AI Max（Strix Halo）** などのユニファイドメモリ搭載機 | [Strix Halo](docs/STRIX_HALO.md) |
| 古いカードやプロセッサ | [古いGPU](docs/OLDER_GPUS.md)、[古いCPU](docs/INSTALL.md#older-cpus-experimental) |

そのほかに必要なもの:

- 約80 GBの空きディスク容量（SSDなら初回の起動がずっと速くなります）
- Windows 10 / 11、Linux、または macOS
- 最新のグラフィックスドライバー

同じメーカーのカードを2〜3枚使って、1つのモデルを動かせます（[マルチGPU](docs/MULTI_GPU.md)）。NVIDIA と AMD のカードにまたがってモデルを分けることはありません。
一覧は [docs/INSTALL.md](docs/INSTALL.md#what-you-need) にあります。

## インストール

これは Asofwar のフォークです。以下はすべて、upstream ではなくフォークの[リリース](https://github.com/Asofwar/Strata/releases)からインストールします。フォークが提供するのは、NVIDIA RTX 20 以降（ドライバー 580 以降）向けの Windows ビルドです。Strata アプリのインストーラー（`.exe`、`.AppImage`、`.dmg`）、ターミナル版の署名付き更新フィード（`strata update`）、Mac・AMD（HIP）・Intel 向けのビルドは提供しません。これらは[ソースからビルド](#ソースからビルド)してください。フォークはテストしていません。

3つの方法から1つ選んでください。どれも同じエンジンを起動し、同じモデルを使います。

### 方法A: リリースの zip（Windows、NVIDIA）

Windows でいちばん簡単な方法です。zip にはフォークのコードと用意済みのエンジンが入っているので、コンパイルは要りません。[最新リリース](https://github.com/Asofwar/Strata/releases/latest)からファイルをダウンロードしてください。

| OS | グラフィックスカード | ダウンロードするファイル |
| --- | --- | --- |
| **Windows 10 / 11** | NVIDIA RTX 20 シリーズ以降、ドライバー 580 以降 | `Strata-Asofwar-<バージョン>-windows-cuda13.zip` |

**迷ったら:** この zip は、ドライバーがバージョン 580 以降の NVIDIA RTX カード向けです。それより古いカードやドライバーは、[古い GPU](docs/OLDER_GPUS.md) を見て、ソースからビルドしてください。リリースには `strata-windows-x64.zip`（エンジンだけ）もありますが、setup が自動でダウンロードするので、自分で取る必要はありません。

そのあとは:

1. ファイルを、パスに空白を含まないフォルダーに展開します。
2. `START-HERE.bat` をダブルクリックします。カードを見つけて、モデルとサイズ、コンテキストの長さ、画像を読むかどうかを尋ね、モデルをダウンロードして起動します。おすすめの答えでよければ Enter を押してください。フォークのモデルを使うには、`START-HERE.bat --setup --family cyber-tiel`（または `--family ornith-abl`）を実行します（[Install the fork](README.md#install-the-fork)、英語）。

モデルは大きく（約 40〜70 GB）、中断しても続きから再開します。ウィンドウを閉じると、Strata とエンジンが止まります。

### 方法B: 1行

Windows（PowerShell）、NVIDIA RTX 20 以降:

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

最新リリースから方法Aの zip をダウンロードし、`SHA256SUMS.txt` で確認して展開し、`START-HERE.bat` を実行します。

Linux（フォークは Linux をテストしていません）:

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

リリースのソースをダウンロードして `./setup.sh` を実行し、お使いのPCでエンジンをソースからビルドします。

実行前にスクリプトを読みたいときは、先にダウンロードして（`curl -fsSL <address> -o install.sh`、PowerShell では `irm <address> -OutFile install.ps1`）、内容を読んでから実行してください。

### 方法C: AI にセットアップを任せる

Claude Code、Cursor、Codex、GitHub Copilot などのコーディングアシスタントに、次の文を貼り付けます。

```text
Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.
```

グラフィックスカード、RAM、ディスクを確認し、合うモデルを選んでインストールと起動をし、ほかのアプリのつなぎ方を教えてくれます。AI ツールは [MCP サーバー](docs/MCP_SERVER.md)から Strata のインストール、起動、停止もできます。

自分でビルドしたい場合は、[ソースからビルド](#ソースからビルド)を見てください。

## モデル

アプリと `strata launch` は、メモリ量に合うモデルをすすめます。モデルは1つで、圧縮の度合いが違う複数のサイズがあります。
小さいサイズは速く、大きいサイズは少し賢くなります。

### メモリが少ないなら Gyro

[Gyro](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-Gyro-GGUF)（agentionai 製）は、このモデルをいちばん小さく動かせる方法です。

| サイズ | 必要なメモリ（RAM + VRAM） | ダウンロード | 内容 |
| --- | ---: | ---: | --- |
| **Gyro-S** | 27.6 GB | 58.5 GB | ほかのサイズが入らないPC向け。品質は IQ2_XS より下がります。 |
| **Gyro-M** | 35 GB | 92.0 GB | 品質は IQ3_XXS 程度で、GPUメモリの使用量は約20%少なくなります。12 GBのカードと R9700 では、回答の書き出しが Q2_0 より17〜21%遅くなります。 |

Gyro は NVIDIA と AMD のカードで動きます（AMD は実験的）。Intel Arc と Mac では動きません。詳細と測定結果は
[docs/GYRO.md](docs/GYRO.md) にあります。`strata launch --model gyro-s` で起動します。

### ほかのサイズ

| メモリ（RAM + VRAM） | 選ぶモデル | 備考 |
| --- | --- | --- |
| **32 GB** | **Gyro-S**、またはコード向けの **[Coder](docs/MODELS.md#coder)** | Coder はRAM 32 GBが必要で、エキスパートを半分だけ保持するため、コード以外は弱くなります |
| **40 GB** | **[Swift 1.5](docs/MODELS.md#swift-15)** IQ2_XS（39.2 GB）、または **Gyro-M**（35 GB） | Swift は答える前に考える時間が短くなります。Gyro-M は品質が IQ3_XXS に近いものの、回答の書き出しは Q2_0 より17〜21%遅くなります |
| **48 GB** | **IQ3_XXS**（47.0 GB） | 遅くなりますが、品質は上がります |
| **64 GB** | **IQ3_S**（54.8 GB）、オリジナルまたは Swift 1.5 | いちばん遅く、いちばん高品質です。公開されているテストでは完全版と同等です |
| **96 GB 以上** | Unsloth の **UD-IQ4_XS**（RAM 約72 GB）から **Q8_0**（約136 GB）まで、4〜8ビット | 完全版に近づきます。RAM が足りないと、Strata は一部を SSD から読むため、ずっと遅くなります |

表の行より RAM が少なくても動くことがあります。Strata は自動で[低RAMモード](docs/MODELS.md#a-big-graphics-card-and-little-ram)に切り替わります。
速度は落ち、グラフィックスカードが小さいとさらに大きく落ちます。

そのほかの選択肢:

- **[Swift 1.5](docs/MODELS.md#swift-15)** はファインチューン版で、答える前に考える時間が短くなります。品質と RAM の必要量はほぼ同じです。
- **[NVFP4](docs/NVFP4.md)** は NVIDIA カード向けの NVIDIA 製4ビット版です。すべてのエキスパートを RAM に置くには、約80 GBの RAM が必要です。
- **[Qwen3.6-35B-A3B](docs/QWEN36.md)** は、より小さい別のモデルです。画像を読め、複数のリクエストに同時に答えられます。
- **[OrcaRouter の Uncensored IQ3_XXS](docs/MODELS.md#orcarouter-uncensored-iq3_xxs)** は手動で設定します。

すべてのサイズ、ダウンロード、どの構成で何が動くかは [docs/MODELS.md](docs/MODELS.md) にあります。

## どのくらい速い？

12 GBのグラフィックスカード（RTX 5070、Ryzen 5 7600、RAM 64 GB）での数値です。ほかのカードの結果は
[各モデルの速度](docs/MODELS.md#how-fast-is-each-size)、[コミュニティの結果](docs/COMMUNITY_BENCHMARKS.md)を見てください。

| モデル | 回答が出る速さ | プロンプトを読む速さ |
| --- | --- | --- |
| **Q2_0** | `████████████` 94 tokens/s | `████████████` 2,650 tokens/s |
| **IQ2_XS** | `██████████░░` 79 tokens/s | `█████████░░░` 2,090 tokens/s |
| **IQ3_XXS** | `████████░░░░` 62 tokens/s | `████████░░░░` 1,750 tokens/s |
| **IQ3_S** | `███████░░░░░` 53 tokens/s | `███████░░░░░` 1,620 tokens/s |
| **Coder** | `███████░░░░░` 55 tokens/s | `██████████░░` 2,180 tokens/s |

1トークンは英単語の約¾にあたるので、毎秒60トークンは読む速さより速くなります。「プロンプトを読む速さ」は、長い文書やコード、チャット履歴を Strata が取り込む速さです。

16 GBの AMD カード（RX 9070 XT、Ryzen 9 3900X、RAM 47 GB）での測定値:

| モデル | 回答が出る速さ | プロンプトを読む速さ |
| --- | --- | --- |
| **Q2_0** | `████████░░░░` 60 tokens/s | `█████░░░░░░░` 1,160 tokens/s |
| **IQ2_XS** | `███████░░░░░` 52 tokens/s | `█████░░░░░░░` 1,110 tokens/s |
| **Coder** | `██████░░░░░░` 44 tokens/s | `██████░░░░░░` 1,420 tokens/s |

バーは2つの表で同じ目盛りです。VRAM が多いカードほど速くなり、RTX 3090（24 GB）なら毎秒100〜140トークンほどになるはずです。各数値のエンジンのバージョンは
[DETAILS.md](docs/DETAILS.md#speed-measured) にあります。

## 使い方

フォークは、Strata アプリも、ターミナル版のインストーラーや署名付き更新フィードも提供しません。以下の**アプリで**と**ターミナルで**は upstream のアプリと `strata` コマンドの説明で、フォークはテストしていません。フォークでは、`START-HERE.bat`（または `./setup.sh`）で Strata を起動し、`UPDATE.bat`（または `./update.sh`）で更新します。`strata update` は使わないでください。

### アプリで

アプリには、**チャット**、モデルとGPU・CPU・RAMの状態を見る**モニター**、**モデル**ページ、**設定**があります。チャットはPC上のフォルダで作業できます。
**手動**モードでは、ファイルを変更したりコマンドを実行したりする前に確認します。`/loop 10m <やること>` と入力すると、チャットを開いている間、メッセージを10分ごとに繰り返し送ります。

チャットは DuckDuckGo（または Bing）でウェブ検索ができ、アカウントは不要です。**設定、ツール**で検索キーを追加することもできます。
検索は、PCの外に何かを送る唯一の機能で、送られるのは検索語です。

2つのモデルを動かすには、**複数のモデルを実行**をオンにして、それぞれのモデルに同じメーカーのカードを1枚ずつ割り当てます。

<p align="center"><img src="docs/media/app-chat.png" width="900" alt="The Strata app: a chat where the agent built a small voxel pagoda garden, with the page open in the preview on the right"><br>
<sub>Strata アプリでのチャット。エージェントが小さなボクセルの塔の庭を 1 つの HTML ファイルとして書き、そのページが会話の横のプレビューで開きます</sub></p>

### ターミナルで

<p align="center"><img src="docs/media/terminal-monitor.png" width="900" alt="The Strata Terminal monitor overview while the model writes a reply"><br>
<sub>モデルが返信を書いている間の <code>strata monitor</code>。速度、GPU、メモリ、最近のリクエストが表示されます</sub></p>

```sh
strata launch                                  # ガイド付きの画面: モデル、コンテキスト、画像、アクセス、そして開始
strata launch --model q2_0 --yes --no-tui     # 質問なし: 開始し、アドレスを表示して戻る
strata launch --plan --model q2_0              # 実行内容を表示するだけで、何も変更しない
strata launch --status                         # 今、何が動いているか
strata launch --stop                           # 停止する
strata monitor --url http://127.0.0.1:8080     # 速度、GPU、メモリ、リクエストを見る
strata doctor                                  # インストール済みのエンジンファイルを調べる
```

`strata --help` ですべてのコマンドを確認できます。起動とサーバーの稼働では、何もダウンロードしません。ダウンロードするのは、インストールと
`strata launch`（モデルを選んだとき）だけです。スマートフォンや別のPCから Strata に接続するには、
`strata launch --access lan` を使います。API キーが作られ、キーがない状態ではネットワーク上で起動しません。`--open` を付けない限り、ブラウザは開きません。
ガイド: [docs/TERMINAL_LAUNCH.md](docs/TERMINAL_LAUNCH.md)。クライアント全体: [docs/TERMINAL.md](docs/TERMINAL.md)。

### AI エージェントと使う

エージェントは [docs/AI_SETUP.md](docs/AI_SETUP.md)（方法C）に従って、フォークを取得し、質問なしで setup を実行し、サーバーを起動します。リポジトリのルールは [AGENTS.md](AGENTS.md) にあります。

### ほかのアプリをつなぐ

| アプリの種類 | ベース URL |
| --- | --- |
| OpenAI 互換（ほとんどのアプリとエージェント） | `http://127.0.0.1:8080/v1`（API キーもモデル名も何でも可） |
| Anthropic API（Claude Code など） | `http://127.0.0.1:8080`、`/v1` は付けません。これらのアプリは `/v1/messages` を自分で付けます。Claude Code: `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API（Codex CLI） | `http://127.0.0.1:8080/v1/responses`（[設定方法](docs/DETAILS.md#the-responses-api-and-codex-cli)） |

`strata connect` は、OpenCode、Codex CLI、Claude Code、oh-my-pi、pi、Hermes Agent、OpenClaw の正確な設定を表示します。
`strata connect opencode --write` は、確認したうえでファイルを書き込み、バックアップを残します。

### 画像

画像を読めるモデルでは、画像は初期設定でオンです。チャットに画像を添付または貼り付けるか、アプリから送ってください。
グラフィックスカードが24 GB未満のときは、画像リーダーがプロセッサで動きます（画像1枚につき数秒、カードのメモリは使いません）。24 GB以上のときはグラフィックスカードで動きます。
このルールは NVIDIA と AMD で同じです。画像はモデルごとにオフにでき、`--vision off`、`--vision gpu`、`--vision cpu` でリーダーを選べます。

このルールの根拠となる数値です。Radeon AI PRO R9700 では、カードのリーダーは260トークンの画像に57 ms、プロセッサのリーダーは3.1秒かかりました。
16 GBのカード（Tesla P100 と RTX A4000、Linux）では、カードのリーダーを使うとテキストの速度が3〜5%下がりました。
本来モデルが使う約1.4 GBをリーダーが占めるためです。Mac ではメモリ量にかかわらず GPU が読み取ります（32 GB の M4 で260トークンの画像に0.45秒、共有メモリを約1.2 GB使います）。プロセッサでは1枚あたり約50秒かかるため、`--vision cpu` を指定したときだけ使います。

### 知っておくと便利なこと

- 思考のレベル（**off、low、medium、high**）は、チャットのメニューか、お使いのアプリの「reasoning effort」で選びます。off がいちばん速くなります。
- Strata は初期設定では、一度に1つのリクエストに答えます。同時に複数処理するには、`strata launch` で `--parallel N` を使うか、設定に
  `"parallel": 2` を書きます（[BATCHING.md](docs/BATCHING.md)）。12 GBのカードでは、1つずつの回答が遅くなります。
- Strata はチャットの最初のメッセージを全文読みます。30,000トークンあたり約1分かかります。続きのメッセージは数秒で始まります。
- チャットの保存場所と API 全体: [docs/INSTALL.md](docs/INSTALL.md#where-things-are-stored)、[docs/DETAILS.md](docs/DETAILS.md#using-it)。

## ソースからビルド

<details>
<summary>リポジトリから Windows、Linux、Mac 用にビルドする</summary>

[フォークをダウンロード](https://github.com/Asofwar/Strata/archive/refs/heads/main.zip)して展開するか、`git clone https://github.com/Asofwar/Strata.git` を実行します。フォークがテストしたのは NVIDIA カードを使う Windows だけです。Linux、Mac、AMD、Intel は upstream の手順で、フォークはテストしていません。
**Windows:** `START-HERE.bat` をダブルクリックします。**Linux:** Strata フォルダで `./setup.sh` を実行します。

**Mac（Apple Silicon、macOS 15 以降）:** 最初に一度、`xcode-select --install` で Apple のコマンドラインツールをインストールします
（Xcode 本体は不要です）。Strata フォルダでターミナルを開き、`./setup.sh` を実行します。Mac 用エンジンをお使いの Mac 上でビルドし
（約7分）、同じ質問をして、モデルをダウンロードし、起動します。2回目以降は `./setup.sh` ですぐに起動します。
お使いの Mac に合うサイズは [docs/MAC.md](docs/MAC.md) を見てください。

インストーラーはカードを見つけて、合うエンジンを設定します。どのモデルとサイズにするか、コンテキストをどれだけにするか（モデルが一度に覚えておけるテキストの量）、
画像を読ませるかを聞かれます。おすすめの答えでよければ Enter を押します。そのあとモデル（約70 GB）をダウンロードして起動します。
ダウンロードが止まったら、もう一度実行すると続きから再開します。ブラウザで `http://127.0.0.1:8080` の Strata ページが開きます。

> モデルの起動中は、PCが1〜3分ほど（初回がいちばん長い）遅くなったり、応答しなくなったりすることがあります。Strata は35〜55 GBをRAMに読み込み、
> その一部をグラフィックスカード用に固定するためです。ウィンドウを閉じずに待ってください。

次回からは `START-HERE.bat`（または `./setup.sh`）をもう一度実行するだけです。すぐに起動し、同じものを2回ダウンロードすることはありません。ウィンドウを閉じるとモデルが止まります。
`UPDATE.bat`（`./update.sh`）は、起動せずに Strata を更新します。更新、Docker、複数のカード、ファイルの保存先、すべてのオプションは
[docs/INSTALL.md](docs/INSTALL.md) にあります。

PCの性能を測るには、`BENCH.bat`（`./bench.sh`）を実行します。5〜10分かかり、共有できるレポートが作られます
（[方法](docs/COMMUNITY_BENCHMARKS.md#run-the-benchmark)）。

**オプション: モデル全体がRAMに入るとき、1枚のカードをさらに速くする。** RubenTorney による、自分でオンにする2つの設定です（#1904、#1905）。
グラフィックスカードが1枚で、RAM がすべてのエキスパートを保持できるときに効果があります。たとえば64 GBのPCでの Q2_0 や IQ3_XXS です。
Strata のデータフォルダにある `strata-<model>.json`（[場所](docs/INSTALL.md#where-things-are-stored)）を開いて、次を追加します。

- `"args"` のリストに `"--adapt-async", "1"` を追加します。エキスパートキャッシュが、回答を止めずに補助スレッドで更新されます。
  RTX 5070（Windows、Q2_0）での測定: デコードが4〜5%、コードや長い文書では7〜10%速くなりました。回答は初期設定と少し違うことがありますが、実行ごとの結果は変わりません。
- `"env"` ブロックに `"STRATA_PIN_BY_NEED": "1"` を追加します（Windows）。Windows ではグラフィックスカード用に固定できる RAM が半分ほどしかありません。
  この設定は、カードが最初に必要とするエキスパートを優先して固定します。RTX 5070 での測定: プロンプトの読み取りが4.4%速くなりました。

```json
"args": [ ..., "--adapt-async", "1" ],
"env": { "STRATA_PIN_BY_NEED": "1" }
```

変更したら Strata を再起動してください。元に戻すには、2つの項目を削除します。

</details>

## 仕組み

このようなモデルは、ふつう数百GBのグラフィックスメモリを持つサーバーで動きます。お使いのグラフィックスカードは12〜24 GBです。Strata は、PC全体で作業を分担して、モデルを収めます。
図書館にたとえてみます。

- モデルは、24,576人の小さな専門家（「エキスパート」）からなるチームです。24,576冊の参考書のようなものです。1つの単語に必要なのは、そのうち10冊だけです。
- **グラフィックスカードは机です。** 小さくて速く、最もよく使う約4,000冊が開いて置いてあります。
- **RAM は閲覧室の書棚です。** 24,576冊すべてがここにあります。単語に必要な本が机になければ、プロセッサがすぐに書棚から読み、その間もカードは作業を続けます。
- **SSD は書庫です。** 29 GBの参照テーブルがしまってあります。モデルは単語ごとにその数行だけを読むので、RAM に置いておく必要はありません。

<p align="center"><img src="docs/media/how-it-works.svg" width="860" alt="The model's 24,576 experts: the busiest on the graphics card, all of them in RAM, a lookup table on the SSD"></p>

小さな助手が、次の数単語も予想します。大きなモデルがそれをまとめて確認し、正しいものだけを残します。答えは同じで、1.6〜1.8倍早く返ります。
長い文章は、一度に最大8,192トークンの大きな塊で、毎秒1,000トークンを超える速さで読みます。

<p align="center"><img src="docs/media/guess-and-check.svg" width="860" alt="A small helper guesses the next words; the big model checks them all at once and keeps the right ones"></p>

詳しい説明は [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) にあります。各部分と数値は
[詳細](docs/DETAILS.md#how-it-works)と[論文](docs/paper/Strata-Paper.pdf)を見てください。

## うまくいかないとき

- **Strata を初めて起動したときに、PCが固まりました。** モデルを RAM に読み込んでいます。ウィンドウを閉じずに待ってください。10分たっても固まったままなら、
  PCを再起動し、ほかのプログラムを閉じてからもう一度試すか、小さいサイズを選んでください。
- **ダウンロードやインストールの途中で止まりました。** アプリか `strata launch` をもう一度起動するか、`START-HERE.bat`（または
  `./setup.sh`）をもう一度実行してください。止まったところから再開します。
- **とても遅い、ディスクのランプが点滅し続ける、または「エンジンが予期せず停止しました」と表示される。** PCの空き RAM が足りません。
  ほかのプログラムを閉じるか（ブラウザはメモリを多く使います）、Q2_0 や IQ2_XS のような小さいサイズを選んでください。
- **このPCに合うエンジンがないと表示される。** `START-HERE.bat`（または `./setup.sh`）をもう一度実行します。フォークのリリースからエンジンをダウンロードするか、ビルドします。`strata update` は実行しないでください。フォークは署名付きの更新フィードを公開していません。
- **ポート 8080 はすでに使われていると表示される。** Strata がすでに動いています。ウィンドウを探してください。

そのほかの問題と対処法は [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) にあります。それでも解決しない場合は、
[issue](https://github.com/Asofwar/Strata/issues) を作成してください。アプリでは、**設定、エンジン、診断、ログを見る、ログを保存**で作られるファイルを添付します。
ターミナルでは、`strata doctor` の出力を貼り付けます。ソースから動かしている場合は、Strata フォルダの `strata-<model>.log` を添付してください。
セキュリティ上の問題は、非公開で報告してください: [SECURITY.md](SECURITY.md)。

## クレジットとライセンス

モデルは Qwen チームの [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) です。圧縮は
[ISTA-DASLab](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF)、UkisAI（Swift 1.5）、agentionai（Gyro）、
Unsloth が行いました。Strata は [llama.cpp / ggml](https://github.com/ggml-org/llama.cpp) の一部を使っています。すべてのクレジットは
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#credits) にあります。Strata は [MIT ライセンス](LICENSE)のオープンソースです。一部のコンポーネントと
すべてのモデルには、それぞれのライセンスがあります（[該当するもの](docs/HOW_IT_WORKS.md#license)）。

## コントリビューション

バグを見つけた、変更やベンチマークを送りたい、という方は、先に [CONTRIBUTING.md](CONTRIBUTING.md) を読んでください。
ほかの人があなたの成果を確認できるように、何を書くべきかが説明してあります。

## Strata を応援する

Strata は無料で、MIT ライセンスです。私が入手できるハードウェアで開発とテストをしています。お使いのPCで快適に動いたなら、コーヒー1杯分の支援は、
新しいカードのテストと、報告いただいた不具合の修正を続ける助けになります。無理のない範囲で大丈夫です。使って、気づいたことを報告してもらえるだけでも同じように助かります。

<a href="https://buymeacoffee.com/strataengine"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>

Strata のスポンサーに関心がある方は、[GitHub](https://github.com/Asofwar) から連絡してください。
