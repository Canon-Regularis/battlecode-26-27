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

The preferred C++ bot is [leader_party_subhan](bots/leader_party_subhan/README.md), which adds Subhan's camp-loop planner to our existing strategy. It beat the unchanged [leader_party baseline](bots/leader_party/README.md) **93–79** across 86 maps; see the [comparison and limitations](docs/strategy/leader_party/subhan_comparison.md) and [current strategy](docs/strategy/leader_party/README.md). Build it with `uv run --locked cambc build leader_party_subhan --release`. Native decision tests run with `& bots/leader_party_subhan/tests/run.ps1`; planner translation tests run with `.venv/Scripts/python.exe bots/leader_party_subhan/tests/verify_translation.py`.

The baseline remains available as a fallback. The former custom state-machine bot is preserved in the [dated archive](bots/archive/state-machine-2026-11-04/README.md). Platform submission was not changed by the planner experiment.

See the [game rules](docs/cambc/GameRules.md) and [current API additions and SDK source links](docs/cambc/api/SDK_4.0.0.md). The published competition map pool was added while preserving the original maps.

To bulk-download platform replays for a team, optionally filtered by map, see the [replay downloader](tools/download_replays.md).

For a future upgrade, check the [official package release](https://pypi.org/project/cambc/), generate a separate reference workspace with that version's `cambc init --yes <directory>`, compare its SDK and build configuration, and update the package pin, SDK version, and lock together. Preserve bot changes and local maps, then repeat builds and local matches before using the new version on the platform.
