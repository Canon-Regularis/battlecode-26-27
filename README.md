# Battlecode 26/27

## Team:

- Subhan
- Matthew
- David
- Kutay

## Development

The workspace uses **CAMBC 4.0.0**, with Python 3.13+ and a Python starter bot. SDK sources and templates are available for Python, C++, Rust, and OCaml. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```powershell
uv sync --locked
uv run --locked cambc build starter-python
uv run --locked cambc run starter-python starter-python --map 00ambush --rounds 100
uv run --locked cambc run starter-python starter-python --map 00monolith --release
```

To add another language, enable it in `cambc.toml` and create a bot with, for example, `uv run --locked cambc new starter-cpp --lang cpp`. CAMBC provisions its required compiler assets when needed. Use `uv run --locked cambc` so the CLI matches `pyproject.toml`, `uv.lock`, and `cambc.toml`; an independently installed global CLI may use another engine version. `--release` matches the platform's treatment of `debug_block`.

See the [game rules](docs/cambc/GameRules.md) and [current API additions and SDK source links](docs/cambc/api/SDK_4.0.0.md). The published competition map pool was added while preserving the original maps.

For a future upgrade, check the [official package release](https://pypi.org/project/cambc/), generate a separate reference workspace with that version's `cambc init --yes <directory>`, compare its SDK and build configuration, and update the package pin, SDK version, and lock together. Preserve bot changes and local maps, then repeat builds and local matches before using the new version on the platform.
