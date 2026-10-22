<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/strata-turbo-lockup-dark.svg">
    <img src="docs/media/strata-turbo-lockup-light.svg" alt="Strata Turbo" width="440">
  </picture>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <b>Français</b> · <a href="README.es.md">Español</a> · <a href="README.pt-BR.md">Português</a></p>

<h3 align="center">Des agents de code avec 262K de contexte sur une seule carte graphique de 16 GB</h3>

<p align="center">Fork de <a href="https://github.com/Niko1221/Strata">Strata</a> par Asofwar · Windows + NVIDIA · gratuit et open source</p>

<p align="center"><b>16 à 18× plus rapide que Strata upstream à 66K de contexte</b>, même carte et même modèle</p>

<p align="center">
  <a href="https://github.com/Asofwar/Strata-Turbo/releases/latest"><img src="https://img.shields.io/github/v/release/Asofwar/Strata-Turbo?label=version" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Asofwar/Strata-Turbo" alt="Licence MIT"></a>
  <a href="docs/FORK.ru.md"><img src="https://img.shields.io/badge/docs-FORK.ru.md-2ea44f" alt="Documentation du fork"></a>
  <a href="#soutenir-le-projet"><img src="https://img.shields.io/badge/don-Gram%20(TON)-0098EA" alt="Gram (TON)"></a>
</p>

Strata fait tourner de gros modèles à mélange d'experts (MoE) sur un PC ordinaire : les experts les plus sollicités restent sur
la carte graphique, les autres en RAM. Ce fork l'optimise pour les agents de code à long contexte avec les modèles
Qwen3.6-35B-A3B **Cyber-Tiel-Coder** et **Ornith** : K/V en int8, brouillons MTP et noyaux maison pour le long contexte. Il parle
les API d'OpenAI et d'Anthropic, donc Codex CLI, Claude Code, OpenCode et d'autres agents s'y connectent. Pas de compte, pas de
télémétrie.

## Vitesse

Même PC, même fichier de modèle, même jour (RTX 5080 16 GB, i9-14900K, 48 GB DDR5-7600, Windows 11, Cyber-Tiel-Coder UD-IQ4_XS) : Strata Turbo face au chemin propre de Strata upstream pour ce modèle.

| Contexte | Lecture du prompt, Turbo / upstream | Écriture, tokens/s, Turbo / upstream |
| ---: | ---: | ---: |
| 2K | 0.5 s / 4.7 s (9×) | 291 / 71 (4×) |
| 32K | 4.4 s / 75 s (17×) | 286 / 51 (6×) |
| 66K | 10 s / 186 s (18×) | 253 / 16 (16×) |
| 128K | 25 s / 513 s (21×) | 194 / 7 (29×, un seul passage upstream) |

Sur une carte de 16 GB, upstream démarre au plus avec 160K de contexte ; Strata Turbo tourne avec 262K (à 200K, il lit le prompt en 49 s et écrit 161–171 tokens/s). Méthode et journaux : [bench/results/2026-10-22-rtx5080-turbo-vs-upstream](bench/results/2026-10-22-rtx5080-turbo-vs-upstream/README.md).

Revenir à une conversation de ~123K après une autre prend 2.5 s au lieu de 33 s (les conversations sont mises en réserve sur le
NVMe). Benchmark d'agent : 53 tâches de code sur 60. Toutes les mesures : [docs/FORK.ru.md](docs/FORK.ru.md).

## Installation

**Windows**, NVIDIA RTX 20 ou plus récent (pilote 580+), dans PowerShell :

```powershell
irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex
```

Le script télécharge la [dernière version](https://github.com/Asofwar/Strata-Turbo/releases/latest), la vérifie avec
`SHA256SUMS.txt`, la décompresse dans `%LOCALAPPDATA%\Strata-Turbo` et lance le setup, qui demande le modèle et le télécharge
(Cyber-Tiel : environ 17 GB). À la main : décompressez `Strata-Turbo-<version>-windows-cuda13.zip` dans un dossier sans
espaces et lancez `START-HERE.bat --setup --family cyber-tiel`.

**Linux** (non testé par le fork ; le moteur se compile depuis les sources) :

```sh
curl -fsSL https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.sh | sh
```

**Laissez votre assistant de code s'en charger :** collez
`Set up Strata on this PC for me: https://github.com/Asofwar/Strata-Turbo - follow docs/AI_SETUP.md in that repository.`

Pour relancer, utilisez `START-HERE.bat` ; pour mettre à jour, exécutez de nouveau la commande d'une ligne (ou `UPDATE.bat` dans un
clone). N'utilisez pas `strata update` : le fork ne publie pas de flux signé. Toutes les options, le matériel différent et
l'emplacement des fichiers : [docs/INSTALL.md](docs/INSTALL.md).

## Modèles

| Modèle | Setup | Remarques |
| --- | --- | --- |
| [Cyber-Tiel-Coder-35B-A3B](https://huggingface.co/peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP) UD-IQ4_XS | `--family cyber-tiel` | le choix par défaut du fork : réfléchit moins longtemps, boucle moins |
| [Huihui-Ornith-1.5-35B-A3B-abliterated](https://huggingface.co/mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF) i1-IQ4_XS | `--family ornith-abl` | même qualité dans les benchmarks, plus lent |
| [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (125B) | `START-HERE.bat`, choisir une taille | le modèle d'upstream : 32 GB et plus de RAM et de VRAM réunies, tailles dans [docs/MODELS.md](docs/MODELS.md) |

Pour des réponses en russe, ajoutez `--draft-vocab cyrillic`. Contrôles de qualité : [EVAL.ru.md](docs/EVAL.ru.md),
[AGENT-EVAL.ru.md](docs/AGENT-EVAL.ru.md).

## Connecter vos applications

| Type d'application | URL de base |
| --- | --- |
| Compatible OpenAI (la plupart des applications et des agents) | `http://127.0.0.1:8080/v1` (n'importe quelle clé API, n'importe quel nom de modèle) |
| API Anthropic (Claude Code) | `http://127.0.0.1:8080` - `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` |
| API OpenAI Responses (Codex CLI) | `http://127.0.0.1:8080/v1/responses` ([configuration](docs/DETAILS.md#the-responses-api-and-codex-cli)) |

Le serveur n'écoute que sur `127.0.0.1`. Avant de l'ouvrir à un réseau, définissez une clé API ([docs/SAFETY.md](docs/SAFETY.md)).

## Documentation

- [docs/FORK.ru.md](docs/FORK.ru.md) - ce que le fork ajoute, toutes les mesures, la configuration recommandée (en russe)
- [docs/INSTALL.md](docs/INSTALL.md) - options d'installation, AMD / Intel / Mac / plusieurs cartes (chemins d'upstream, non testés par le fork), réglages
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - en cas de problème ; les bugs vont dans les [issues](https://github.com/Asofwar/Strata-Turbo/issues)
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) - comment un gros modèle tient sur un PC ; chaque élément et chaque chiffre : [DETAILS.md](docs/DETAILS.md), [l'article](docs/paper/Strata-Paper.pdf)
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

La documentation est en anglais, sauf `FORK.ru.md`, `EVAL.ru.md` et `AGENT-EVAL.ru.md`, qui sont en russe.

## Crédits et licence

Strata est l'œuvre de [Niko1221](https://github.com/Niko1221/Strata) ; ce fork y ajoute le travail sur le long contexte. Modèles :
l'équipe Qwen, [peculiar-ragdoll](https://huggingface.co/peculiar-ragdoll) (Cyber-Tiel-Coder),
[ornith-ai](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) et [huihui-ai](https://huggingface.co/huihui-ai/Huihui-Ornith-1.5-35B-A3B-abliterated)
(Ornith), ISTA-DASLab, UkisAI, agentionai et Unsloth (tailles de Flash-Next). Strata utilise des parties de
[llama.cpp / ggml](https://github.com/ggml-org/llama.cpp). Licence MIT ([LICENSE](LICENSE)) ; certaines parties et chaque modèle
ont la leur ([lesquelles](docs/HOW_IT_WORKS.md#license)).

## Soutenir le projet

Strata Turbo est gratuit. Si le fork vous aide, soutenez son travail avec des Gram (TON) sur son portefeuille Telegram :

<p><img src="docs/media/donate-gram-qr.png" alt="Gram (TON), portefeuille Telegram : QR" width="160"></p>

`UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23` ·
[envoyer depuis un portefeuille TON](https://app.tonkeeper.com/transfer/UQAdvK_4JyPGKpuD3Z27LkRZG7qmQ-03oWtUROMYNTz-Sx23?text=Strata)
(réseau TON uniquement : un transfert depuis un autre réseau est perdu)
