# AGENTS.md

Strata runs the Qwen3.8-Flash-Next mixture-of-experts model (and its Coder, Swift 1.5, Unsloth, Gyro and NVFP4
variants, and Qwen3.6-35B-A3B) on a normal PC: one NVIDIA or AMD graphics card plus system RAM on Windows or Linux,
or an Apple Silicon Mac. It is Strata Turbo, Asofwar's fork of Niko1221/Strata (base: upstream 0.2.1.1, engine 0.1.46.1; the fork's
releases have their own versions from v1.0.0). It has three parts:

- **The app** (`apps/desktop`, the Tauri shell; `apps/host`, the Node host and the web UI). It is for people who do
  not want a terminal. The installer has the engine inside; the fork does not publish installers.
- **The Terminal** (`strata.py`, `strata_cli/`, `strata_control/`): the `strata` command. It sets up a model, serves
  it and watches it. The fork ships no installer or signed feed for it.
- **The engine and the server** (`src/`, `include/`, `metal/`, `sycl/` for the C++/CUDA/HIP/SYCL/Metal engine;
  `serve/` for the Python server with an OpenAI- and Anthropic-compatible API and a web page). `setup.py`, started by
  `START-HERE.bat` or `setup.sh`, is the older one-click installer from source.

## Installing Strata for a user

This is Strata Turbo, Asofwar's fork (https://github.com/Asofwar/Strata). Follow **[docs/AI_SETUP.md](docs/AI_SETUP.md)**. For an agent
that has a shell, the short version is:

1. Get the fork. Setup downloads the ready engine on Windows with an NVIDIA RTX 20 series card or newer (driver 580 or newer);
   on other systems it builds the engine from source, which the fork has not tested.

   ```sh
   git clone https://github.com/Asofwar/Strata.git
   ```

   Without git, download https://github.com/Asofwar/Strata/archive/refs/heads/main.zip and unzip it. On Windows the release
   zip `Strata-Turbo-<version>-windows-cuda13.zip` from https://github.com/Asofwar/Strata/releases/latest holds the same
   code and a ready engine.
2. Check the PC. Nothing is installed except Python and the `.venv`:

   ```sh
   START-HERE.bat --check      # Windows
   ./setup.sh --check          # Linux, Mac
   ```

3. Set up without questions. It downloads the engine (if there is none) and the model (tens of GB) and writes a start
   script. `--no-start` keeps the server from blocking your shell:

   ```sh
   START-HERE.bat --yes --family cyber-tiel --no-start     # Windows; the fork's model, or --family ornith-abl
   ./setup.sh --yes --family qwen --model IQ2_XS --no-start # Linux, Mac; a Flash-Next size
   ```

   All flags: `START-HERE.bat --help` (or `./setup.sh --help`). Then start the script setup printed (`run-<model>.bat` or
   `run-<model>.sh`) and check `curl http://127.0.0.1:8080/health`.
4. Connect the user's apps: base URL `http://127.0.0.1:8080/v1` (OpenAI), `http://127.0.0.1:8080` (Anthropic). The steps are in
   [docs/AI_SETUP.md](docs/AI_SETUP.md).

Do not use `strata launch` or `strata update` to install or update the fork: the fork ships no Terminal installer and no
signed update feed, and upstream's would install upstream's engine, which has no pack path for the fork's models. Never
expose the server beyond `127.0.0.1` without an API key (`--host 0.0.0.0 --api-key KEY`). Strata's MCP server
([docs/MCP_SERVER.md](docs/MCP_SERVER.md)) offers the same steps as tools.

## Working on the code

- How the engine works, every measured number, the API and all settings: [docs/DETAILS.md](docs/DETAILS.md) and
  the [paper](docs/paper/Strata-Paper.pdf).
- The Terminal: [docs/TERMINAL.md](docs/TERMINAL.md) and [docs/TERMINAL_LAUNCH.md](docs/TERMINAL_LAUNCH.md). The app,
  the packages and the update feed: [packaging/README.md](packaging/README.md) and [packaging/UPDATES.md](packaging/UPDATES.md).
- AMD (HIP) build and validation: [docs/AMD_HIP.md](docs/AMD_HIP.md); multi-GPU: [docs/MULTI_GPU.md](docs/MULTI_GPU.md);
  Mac (Metal): [docs/MAC.md](docs/MAC.md).
- Tests: the Terminal and Control tests are in `tests/terminal` (`python -m pytest tests/terminal`). The app's UI
  tests run with `npm test` in `apps/host`. Setup's own tests run without a GPU or downloads:
  `python tools/test_setup_<name>.py` (for example `tools/test_setup_amd.py`, `tools/test_setup_choices.py`).
- Keep the docs' style: plain words, short sentences, written for non-technical users first. Give measured numbers
  with what they were measured on. Make no claim without a measurement.

## Contributing a change or report

The rules are in **[CONTRIBUTING.md](CONTRIBUTING.md)**. Read it before you open an issue or a pull request, and
follow it whether a person or an agent writes the text. The short version:

- Start every issue and pull request title with its area: `[Engine]`, `[GUI]`, `[TUI]`, `[Benchmark]`, `[Docs]` or
  `[Other]`, for example `[Engine] fix …`. A check on GitHub fails a pull request whose title has no area.
- Search the open and closed issues and pull requests first, and add to a thread that already covers your point.
- Agree the scope in an issue before a large feature, a refactor or a change to a default.
- One problem per pull request. Lead with the problem and the result, then the approach, then the validation
  (passed, failed and not run, kept apart) and the limits.
- A new feature is opt-in, and the default path stays byte-identical to the last release. Say how you checked.
- Build every backend a file touches (CUDA, HIP, SYCL) before asking for review.
- Change a default only where you measured it faster, and show the numbers with what they were measured on.
- Never submit measurements, logs or reproduction steps you did not produce. Mark a finding from reading code as
  unconfirmed static analysis.
- A report from hardware the maintainers do not have is welcome. Follow
  [docs/COMMUNITY_BENCHMARKS.md](docs/COMMUNITY_BENCHMARKS.md), compare against a same-day run of the build you are
  testing, and say what you did not test.
- Open test requests and the hardware that is wanted are listed in [docs/TEST_REQUESTS.md](docs/TEST_REQUESTS.md).
