# Generated-code fuel benchmark

The recovered economy investigation is documented in
[`economy-followup.md`](economy-followup.md), including exact historical baseline
reproduction, competing allocation/layout/integer experiments, new generic
passes, and combined whole-planner measurements. `--suite wrappers` exercises
small-record factories, inferred wrapper returns and integer loop facts.

The completed [20% investigation](twenty-percent.md) includes actual Wasm
disassembly, rejected prototypes, and runtime-guarded candidates. `--suite deferred`
tests generated allocation/override/finalizer paths; `--suite reductions` tests
short integer reductions and long-input, float, bigint and callback fallbacks.
`--suite shortcircuit` checks generated `any`/`all` loops, custom iterator protocols,
mutation, predicate exceptions and boolean-error finalizer lifetimes.

The earlier audited milestone saves **20.30–20.31% collision, 22.50% corners, and
22.99–23.01% lanes** at the equal-work planner boundary. Repeated measurements,
work counts, normal-budget checks and source fingerprints are archived in
[`twenty-percent-results.json`](twenty-percent-results.json).

The completed [30% investigation](thirty-percent.md) now verifies **30.44–30.45%
collision, 32.61% corners, and 33.11–33.12% lanes** at the same equal-work planner
boundary. It includes Wasm-guided loop refinements, 166 compiler tests, 71 bot tests,
240 exact planner scenarios, 47 guest fixtures, explicit expansion counts and
matching three-round normal-budget replays. Evidence and source provenance are in
[`thirty-percent-results.json`](thirty-percent-results.json); `--suite thirty`
exercises the new allocation, extrema, adjacency, insertion and cleanup paths.

Unlike `benchmarks/python-fuel`, these alternatives are **produced by the
optimiser**, not written by hand.

```sh
uv run python -m tools.bot_optimizer.benchmark \
  --output replays/bot-optimizer-check --maps collision,corners
```

Choose a new output directory for each run. The driver stages a runnable bot with
`original.py`, generated `optimized.py` and the paired runner. `src/` here is a
template, not a standalone submission; run through the driver.

Requirements: workspace root, Python 3.13, project's cambc 3.0.4 executable. Pass
`--cambc /path/to/cambc` if needed. No production bot is modified.

Each map is run in release mode for one round with a fuel quantum of 1,000,000,000.
Both draft instances check equality for all 10 kernels, warm each 20 times, and
measure five batches of 20 calls. Baseline/generated measurement order alternates.
Results include per-call allocation/setup; module import and native-key helper
initialisation occur before measurement (ordinary modules are preloaded).

`results.json` in the output contains metadata, applied compiler rewrites, all raw
samples and per-team results. Incomplete/failed probes are rejected. A ratio above
1 means generated code used less fuel. Losing alternatives are reported honestly;
the benchmark does not assert that every future pass must win every workload.

The compact [recorded results](results.json) are from 2026-10-22. Both teams had
identical samples on each map. The source SHA-256 fingerprints `src/kernels.py`.
Representative baseline/generated ratios:

| Kernel | collision | corners |
| --- | ---: | ---: |
| Integer square | 1.26x | 1.26x |
| Native map | 2.06x | 2.06x |
| Bounded sum | 1.35x | 1.33x |
| Mask count | 19.13x | 15.76x |
| Mask existence | 19.97x | 16.25x |
| Mask filtering | 5.00x | 4.82x |
| Intersection count | 30.25x | 24.36x |
| Native method key | 2.18x | 2.15x |
| Item key | 1.45x | 1.45x |
| Attribute key | 2.01x | 2.01x |

These kernels establish pass-level fuel evidence, not automatic performance gains
for arbitrary bots. In particular, small collections and runtime helper setup may
have different tradeoffs. See [`tools/bot_optimizer`](../../tools/bot_optimizer/README.md)
for the compiler contract and limitations.

## Economy-bot check (version 0.1)

The initial optimiser gave `economy-bot` **three native attribute-key rewrites**: camp
candidate sorting and the two search-result sorting sites. The freshly generated
Python matched the existing `bots/economy-optimized/` output. All 71 copied bot
tests passed, and both maps built/ran without logged errors.

An additional cold-planner comparison measured `DraftPlanner.build()` in staged
baseline and generated copies, with identical timing instrumentation. Release
self-matches used raised fuel so both variants completed the same search work,
rather than one stopping earlier at a fuel reserve. Corresponding teams produced
identical expansion counts and full ranked loop reports:

| Map | Expansions per team | Observed planner fuel reduction |
| --- | ---: | ---: |
| collision | 6,020 | 0.0035–0.0088% |
| corners | 20,000 | 0.0266–0.0280% |

These are the two team observations from one cold run per variant/map, **not
confidence intervals**. Allocation/snapshot effects are not isolated. The observed
benefit is negligible, not evidence of a meaningful whole-bot improvement.
Microbenchmark ratios above must not be applied to the bot as a whole: almost all
its measured build fuel was spent inside search, where scoring and route expansion
dominate rather than the three rewritten key callbacks.

Separate, uninstrumented three-round runs at the normal fuel budget also produced
identical ranked loop reports on both sides of both maps. The production bot and
existing generated folder were not edited. Detailed values and measurement scope
are recorded in [`economy-results.json`](economy-results.json).

## Generic specialisation suite (version 0.2)

```sh
uv run python -m tools.bot_optimizer.benchmark --suite specialization \
  --output replays/bot-optimizer-specialization --maps collision,corners
```

This compiles [`src/specialization.py`](src/specialization.py), using the same
paired runner and setup-inclusive measurements. It tests generic Python patterns,
not economy-bot-specific class names or algorithms. Recorded
[specialization-results.json](specialization-results.json) contains the source
fingerprint and medians; the driver emits all raw samples when rerun.

| Kernel | Approximate baseline/generated fuel |
| --- | ---: |
| Identity sum generator | 5.40x |
| Bounded immutable-tuple reduction | 1.50x |
| Native map over integer tuple | 1.90x |
| Integer helper inlining | 1.60x |
| Resolved keyword calls | 1.27x |
| Frozen record, 4 / 8 / 12 fields | 1.34x / 1.65x / 1.84x |
| Non-escaping temporary record | 4.34x |
| Subclass correctness fallback | **0.994x (slightly worse)** |

The losing fallback is deliberately included: retaining subclass semantics adds
a type guard to the original field-setting path. Disable `record-bulk-init` for
subclass-heavy workloads if actual measurements show a regression.

## Economy-bot check (version 0.2)

The generic passes now produce **13 rewrites**: five bulk frozen-record
initialisers, five resolved keyword-call conversions and the original three
native keys. The public data types and strategy code are retained.

Use the generic comparison driver to reproduce the measured planner experiment:

```sh
uv run python -m tools.bot_optimizer.compare bots/economy-bot \
  --target draft_planner:DraftPlanner.build \
  --output replays/economy-optimizer-v2 \
  --maps collision,corners --repeats 2 \
  --require-equal-prefix 'SQUAD_LOOPS_DATA '
```

Two repeated release self-match comparisons, with reversed baseline/generated
order on the second repeat, produced:

| Map | Observed planner fuel reduction |
| --- | ---: |
| collision | 13.6145–13.6179% |
| corners | 14.4945–14.5005% |

Both teams printed identical complete ranked-loop reports; repeated measurements
matched exactly per team. A separate expansion-count probe verified equal work
(6,020 / 20,000 expansions on collision / corners). Normal-budget, uninstrumented
three-round checks also matched both teams' ranked reports. All 71 copied bot
tests passed. There are now 86 optimiser/measurement regression tests.

A collision ablation disabling bulk initialisation still saved approximately
**6.24%**, supporting the value of generic call optimisation separately from bulk
record construction. See [`economy-v2-results.json`](economy-v2-results.json).

These measurements cover the cold `DraftPlanner.build()` call, not fallback-plan
construction, drawing, gameplay or win rate. Snapshot/allocation effects and
instrumentation can shift exact costs: a separately instrumented search-count
probe observed roughly 13.5–14.4% savings. This is evidence of a real improvement
on this bot, **not a guaranteed saving for arbitrary bots**. No production source
or existing `bots/economy-optimized/` output was overwritten; the verified new
submission copy is `bots/economy-optimized-v2/`.

## Fuel follow-up

The [2026-10-22/23 follow-up](fuel-followup.md) adds direct record stores,
compound native keys, filtered integer reductions, more native-map consumers,
constant-integer membership and expression-local native SDK state optimizations.
It includes cold/warm competing implementations, incremental comparisons against
the previous compiler, generated combined kernels, whole starter-bot turn fuel,
normal-budget and held-out checks, and documented losing cases. Raw measured
reports for the audited implementation are archived in
[fuel-followup-guarded-results.json](fuel-followup-guarded-results.json); the initial
[exploratory archive](fuel-followup-results.json) is retained separately.
No new economy-bot planner gain is claimed: its source is absent in this checkout.
