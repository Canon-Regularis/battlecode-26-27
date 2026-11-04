# Battlecode 26/27

## Team:
- Subhan
- Matthew
- David
- Kutay
## Development

The workspace uses **CAMBC 4.0.0**, with Python 3.13+ and Python/C++ bots. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```powershell
uv sync --locked
uv run --locked cambc build starter-python
uv run --locked cambc run starter-python starter-python --map 00ambush --rounds 100
uv run --locked cambc run starter-python starter-python --map 00monolith --release
```

CAMBC provisions its required compiler assets when needed. Use `uv run --locked cambc` so the CLI matches `pyproject.toml`, `uv.lock`, and `cambc.toml`; an independently installed global CLI may use another engine version. `--release` matches the platform's treatment of `debug_block`.

The preferred C++ bot is [leader_party_tuned](bots/leader_party_tuned/README.md), the combined configuration champion `g07_search` after two full configurable-stat sweeps. It won **409–107** on 86 published maps against untuned Subhan, D1 and gold_diamond. See the [complete tuning report](docs/strategy/leader_party/config_tuning_all_stats.md) and [current strategy](docs/strategy/leader_party/README.md). Build with `uv run --locked cambc build leader_party_tuned --release`; native tests run with `& bots/leader_party_tuned/tests/run.ps1`.

The original [leader_party](bots/leader_party/README.md), untuned Subhan bot and all tuning generations remain available. The former custom state-machine bot is preserved in the [dated archive](bots/archive/state-machine-2026-11-04/README.md). The tuned bot was subsequently submitted to CAMBC as version 7; see the [publication receipt](docs/strategy/leader_party/evaluation/2026-11-04/tuning/publication.json).

See the [game rules](docs/cambc/GameRules.md) and [current API additions and SDK source links](docs/cambc/api/SDK_4.0.0.md). The published competition map pool was added while preserving the original maps.

For a future upgrade, check the [official package release](https://pypi.org/project/cambc/), generate a separate reference workspace with that version's `cambc init --yes <directory>`, compare its SDK and build configuration, and update the package pin, SDK version, and lock together. Preserve bot changes and local maps, then repeat builds and local matches before using the new version on the platform.
