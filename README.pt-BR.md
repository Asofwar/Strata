<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/strata-turbo-lockup-dark.svg">
    <img src="docs/media/strata-turbo-lockup-light.svg" alt="Strata Turbo" width="440">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.fr.md">Français</a> · <a href="README.es.md">Español</a> · <b>Português</b></p>

<h3 align="center">Agentes de programação com contexto de 262K em uma única placa de vídeo de 16 GB</h3>

<p align="center">Fork do <a href="https://github.com/Niko1221/Strata">Strata</a> feito por Asofwar · Windows + NVIDIA · gratuito e de código aberto</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata-Turbo/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata-Turbo?label=vers%C3%A3o" alt="Versão"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata-Turbo" alt="Licença MIT"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Documentação do fork"></a>
  <a href="#apoiar-o-projeto"><img src="https://img.shields.io/badge/doar-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

O Strata roda grandes modelos de mistura de especialistas (MoE) em um PC comum: os especialistas mais usados ficam na placa de
vídeo e o restante na RAM. Este fork o ajusta para agentes de programação com contextos longos nos modelos Qwen3.6-35B-A3B
**Cyber-Tiel-Coder** e **Ornith**: K/V em int8, rascunhos MTP e kernels próprios para contexto longo. Ele fala as APIs da OpenAI
e da Anthropic, então Codex CLI, Claude Code, OpenCode e outros agentes se conectam a ele. Sem conta e sem telemetria.

## Velocidade

RTX 5080 16 GB, i9-14900K, 48 GB DDR5, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS com as configurações que o setup grava:

| Contexto | Leitura do prompt | Geração |
| ---: | ---: | ---: |
| 130K | 25.7 s | 146-167 tokens/s |
| 200K | 49.4 s | 161-171 tokens/s |

Voltar a uma conversa de ~123K depois de outra leva 2.5 s em vez de 33 s (as conversas ficam guardadas no NVMe).
Benchmark de agente: 53 de 60 tarefas de programação. Todas as medições: [docs/FORK.ru.md](docs/FORK.ru.md).

## Instalação

**Windows**, NVIDIA RTX 20 ou mais recente (driver 580+), no PowerShell:

```powershell
irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex
```

Ele baixa a [última versão](https://github.com/Asofwar/Strata-Turbo/releases/latest), confere com `SHA256SUMS.txt`, descompacta em
`%LOCALAPPDATA%\Strata-Turbo` e inicia o setup, que pergunta o modelo e o baixa (Cyber-Tiel: cerca de 17 GB). Manualmente:
descompacte `Strata-Turbo-<version>-windows-cuda13.zip` em uma pasta sem espaços e execute
`START-HERE.bat --setup --family cyber-tiel`.

**Linux** (não testado pelo fork; o motor é compilado a partir do código-fonte):

```sh
curl -fsSL https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.sh | sh
```

**Deixe seu assistente de programação fazer isso:** cole
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata-Turbo - follow docs/AI_SETUP.md in that repository.`

Para iniciar de novo, use `START-HERE.bat`; para atualizar, execute o comando de uma linha outra vez (ou `UPDATE.bat` em um
clone). Não use `strata update`: o fork não publica um feed assinado. Todas as opções, outros hardwares e onde ficam os arquivos:
[docs/INSTALL.md](docs/INSTALL.md).

## Modelos

| Modelo | Setup | Observações |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | o padrão do fork: pensa menos e entra menos em loop |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | mesma qualidade nos benchmarks, mais lento |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, escolher um tamanho | o modelo do upstream: 32+ GB de RAM e VRAM somadas, tamanhos em [docs/MODELS.md](docs/MODELS.md) |

Para respostas em russo, adicione `--draft-vocab cyrillic`. Verificações de qualidade: [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Conectar seus aplicativos

| Tipo de aplicativo | URL base |
| --- | --- |
| Compatível com OpenAI (a maioria dos aplicativos e agentes) | `http://127.0.0.1:8080/v1` (qualquer chave de API, qualquer nome de modelo) |
| API da Anthropic (Claude Code) | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| API Responses da OpenAI (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([configuração](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

O servidor escuta apenas em `127.0.0.1`. Antes de abri-lo para uma rede, defina uma chave de API ([docs/SAFETY.md](docs/SAFETY.md)).

## Documentação

- [docs/FORK.ru.md](docs/FORK.ru.md) - o que o fork acrescenta, todas as medições, a configuração recomendada (em russo)
- [docs/INSTALL.md](docs/INSTALL.md) - opções de instalação, AMD / Intel / Mac / várias placas (caminhos do upstream, não testados pelo fork), configurações
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - quando algo dá errado; bugs vão para as [issues](https://github.com/Asofwar/Strata-Turbo/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) - como um modelo grande cabe em um PC; cada parte e cada número: [DETAILS.md](docs/DETAILS.md), [o artigo](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

A documentação está em inglês, exceto `FORK.ru.md`, `EVAL.ru.md` e `AGENT-EVAL.ru.md`, que estão em russo.

## Créditos e licença

O Strata é de [Niko1221](https://github.com/Niko1221/Strata); este fork acrescenta o trabalho com contexto longo. Modelos: a
equipe Qwen, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) e [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai e Unsloth (tamanhos do Flash-Next). O Strata usa partes do
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). Licença MIT ([LICENSE](LICENSE)); algumas partes e cada modelo
têm a sua ([quais](docs/HOW_IT_WORKS.md#license)).

## Apoiar o projeto

O Strata Turbo é gratuito. Se ele ajuda você, apoie o trabalho do fork com Gram (TON) para a carteira dele no Telegram:

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), carteira do Telegram: QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[enviar de uma carteira TON](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(apenas rede TON: uma transferência de outra rede é perdida)
