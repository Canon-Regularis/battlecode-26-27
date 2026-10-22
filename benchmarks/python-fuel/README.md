# Python/SDK fuel probes

Standalone research bot for cambc **3.0.4**. It compares equivalent operations
using actual Wasmtime fuel, not host Python timings. Production bots are not
modified. Findings are documented in
[`docs/cambc/PythonSDKPatterns.md`](../../docs/cambc/PythonSDKPatterns.md).

From the workspace root:

```sh
uv run cambc run benchmarks/python-fuel benchmarks/python-fuel \
  --release --rounds 1 --fuel 1000000000 --map collision \
  --out-dir replays/python-fuel-collision
```

Repeat with `--map corners` for the larger test map. The unusually high fuel
quantum prevents suspension from invalidating counter subtraction. **Do not put
the measurements inside `debug_block`.** This bot is a benchmark, not a sensible
game-playing submission.

The `.repl26a` output is a ZIP archive. `team-a.stdout` and `team-b.stdout` contain
newline-prefixed records:

- `META`: runtime, map dimensions and representation checks.
- `BENCH`: five sample fuel costs and the median fuel per call.
- `PAIR`: baseline/alternative costs and their ratio. Above 1 means the
  alternative used less fuel; below 1 means it was worse.
- `DONE draft` / `DONE game`: successful completion markers.

Summarize one or more replay bundles:

```sh
python3 benchmarks/python-fuel/summarize.py path/to/collision.repl26a path/to/corners.repl26a
```

Add `--json` for structured output. [`results.json`](results.json) records the
verified research runs on the 41x41 and 71x71 maps. The summarizer rejects failed
or incomplete probes.

Each case receives 20 warmup calls and five measurement batches, normally of 30
calls. Equality checks run outside measured regions. Different representations
are normalized for comparison, also outside measured regions. Stateful
snapshots are compared only while the bot takes no game actions.

Draft probes run once per team. Gameplay probes run once per champion instance,
so gameplay records repeat. Output should contain no `FATAL` or traceback lines.
The suite intentionally includes losing alternatives and crossover cases.

SDK caveats tested here: distance-field exports are typed `memoryview` snapshots;
bitboard linear buffers contain packed bits. Some bundled type annotations and
comments do not describe those runtime representations accurately.
