<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/host/public/brand/strata-lockup-dark.svg">
    <img src="apps/host/public/brand/strata-lockup-light.svg" alt="Strata" width="380">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <b>简体中文</b> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h1 align="center">Strata Turbo</h1>

<h3 align="center">在一张 16 GB 显卡上运行 262K 上下文的编程智能体</h3>

<p align="center">Asofwar 维护的 <a href="https://github.com/Niko1221/Strata">Strata</a> 分支 · Windows + NVIDIA · 免费开源</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata?label=%E7%89%88%E6%9C%AC" alt="版本"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata" alt="MIT 许可证"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="分支文档"></a>
  <a href="#支持本项目"><img src="https://img.shields.io/badge/%E6%8D%90%E8%B5%A0-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata 让普通 PC 也能运行大型混合专家（MoE）模型：最常用的专家放在显卡上，其余放在内存里。
这个分支针对长上下文的编程智能体做了调优，面向 Qwen3.6-35B-A3B 系列的 **Cyber-Tiel-Coder** 和
**Ornith** 模型：int8 K/V、MTP 草稿，以及自研的长上下文内核。它兼容 OpenAI 和 Anthropic API，因此 Codex CLI、
Claude Code、OpenCode 等智能体都能直接连接。无需账号，没有遥测。

## 速度

RTX 5080 16 GB、i9-14900K、48 GB DDR5、Windows 11，Cyber-Tiel-Coder UD-IQ4_XS，使用 setup 写入的设置：

| 上下文 | 读取提示词 | 生成 |
| ---: | ---: | ---: |
| 130K | 25.7 秒 | 146-167 token/秒 |
| 200K | 49.4 秒 | 161-171 token/秒 |

在另一段对话之后切回约 123K 的对话，只需 2.5 秒，而不是 33 秒（对话会暂存到 NVMe 上）。
智能体基准测试：60 个编程任务完成 53 个。全部测量数据见 [docs/FORK.ru.md](docs/FORK.ru.md)。

## 安装

**Windows**，NVIDIA RTX 20 或更新的显卡（驱动 580+），在 PowerShell 中运行：

```powershell
irm https://github.com/Asofwar/Strata/releases/latest/download/install.ps1 | iex
```

脚本会下载[最新版本](https://github.com/Asofwar/Strata/releases/latest)，用 `SHA256SUMS.txt` 校验，解压到
`%LOCALAPPDATA%\Strata-Turbo`，然后启动 setup；setup 会询问要用的模型并下载（Cyber-Tiel：约 17 GB）。
手动安装：把 `Strata-Turbo-<version>-windows-cuda13.zip` 解压到不含空格的文件夹，再运行
`START-HERE.bat --setup --family cyber-tiel`。

**Linux**（本分支未测试；引擎需从源码构建）：

```sh
curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
```

**让编程助手代劳：** 粘贴下面这句
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata - follow docs/AI_SETUP.md in that repository.`

之后用 `START-HERE.bat` 再次启动；更新就是再运行一遍上面的单行命令（克隆的仓库里可用 `UPDATE.bat`）。不要使用
`strata update`：本分支没有发布签名的更新源。全部选项、其他硬件和文件位置见
[docs/INSTALL.md](docs/INSTALL.md)。

## 模型

| 模型 | Setup | 说明 |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | 本分支的默认模型：思考更简短，更少陷入循环 |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | 基准测试中质量相同，但更慢 |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`，选择尺寸 | 上游的模型：内存与显存合计需 32 GB 以上，各尺寸见 [docs/MODELS.md](docs/MODELS.md) |

若要用俄语回答，请加上 `--draft-vocab cyrillic`。质量检测：[EVAL.ru.md](docs/EVAL.ru.md)、
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md)。

## 连接你的应用

| 应用类型 | Base URL |
| --- | --- |
| 兼容 OpenAI 的应用（大多数应用和智能体） | `http://127.0.0.1:8080/v1`（任意 API key，任意模型名） |
| Anthropic API（Claude Code） | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| OpenAI Responses API（Codex CLI） | `http://127.0.0.1:8080/v1/responses`（[配置方法](docs/DETAILS.md#the-responses-api-and-codex-cli)） |

服务器只监听 `127.0.0.1`。对外开放到网络之前，请先设置 API key（[docs/SAFETY.md](docs/SAFETY.md)）。

## 文档

- [docs/FORK.ru.md](docs/FORK.ru.md)：分支新增了什么、全部测量数据、推荐配置（俄语）
- [docs/INSTALL.md](docs/INSTALL.md)：安装选项、AMD / Intel / Mac / 多卡（沿用上游的路径，本分支未测试）、各项设置
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)：出问题时看这里；bug 请提交到 [issues](https://github.com/Asofwar/Strata/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)：大模型如何放进一台 PC；每个部分和数字见 [DETAILS.md](docs/DETAILS.md)、[论文](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md)

文档均为英文，只有 `FORK.ru.md`、`EVAL.ru.md` 和 `AGENT-EVAL.ru.md` 是俄语。

## 致谢与许可证

Strata 由 [Niko1221](https://github.com/Niko1221/Strata) 开发；本分支在其基础上加入了长上下文方面的工作。模型：Qwen
团队、[peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll)（Cyber-Tiel-Coder）、
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) 和 [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
（Ornith）、ISTA-DASLab、UkisAI、agentionai 和 Unsloth（Flash-Next 各尺寸）。Strata 使用了
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp) 的部分代码。采用 MIT 许可证（[LICENSE](LICENSE)）；部分组件和所有模型
有各自的许可证（[详情](docs/HOW_IT_WORKS.md#license)）。

## 支持本项目

Strata Turbo 免费。如果它对你有帮助，欢迎用 Gram (TON) 打赏到分支的 Telegram 钱包，支持分支的工作：

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON)，Telegram 钱包：二维码" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[从 TON 钱包转账](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
（仅限 TON 网络：从其他网络转入的资金会丢失）
