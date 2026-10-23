# Guest-fuel optimiser follow-up (2026-10-22/23)

Target: **cambc 3.0.4 / guest CPython 3.13.7**, release builds. No production bot
source was edited. Initial Git status was clean. All variants, replays and Wasm
builds use new directories. The initial
[`fuel-followup-results.json`](fuel-followup-results.json) archive preserves the
exploratory runs, including the initial direct-store candidate. The final
[`fuel-followup-guarded-results.json`](fuel-followup-guarded-results.json) archive
uses the audited record guard. Both contain raw samples and source fingerprints;
paths inside them locate full generated sources/replays in this workspace.

Earlier final audit: **102 regression tests pass**, dependency lock validation and
`git diff --check` pass, and the guarded archive contains **18 complete runs**.
Its generated guarded kernel sources reproduced byte-for-byte with the then-current
compiler; all archived engine-trajectory equality checks pass. Production bot,
SDK and original research-document source diffs are empty.

## Baseline and a concrete limitation

At the time of this earlier investigation the checkout contained only
`bots/starter-python`. The economy-bot, its tests and
previous generated bundles referenced by older research were **absent**, not merely
untracked modifications to overwrite. Consequently the recorded economy planner
gain could not be reproduced or extended then. Do not read the following kernel or
starter results as new economy measurements.

**Update:** the source has since been recovered unchanged from its separate PR.
[`economy-followup.md`](economy-followup.md) records exact historical baseline
reproduction and the subsequent investigation. The archived results below remain
the earlier investigation's evidence.

`uv sync` restored the missing virtualenv. It also corrected `uv.lock`, which
still pinned 2.1.6 despite `pyproject.toml` already requiring 3.0.4. The initial 86
tests passed. A fresh specialization suite reproduced all previously recorded
ratios on both maps, including the slightly losing subclass fallback. The old
optimiser produced no starter rewrites; a two-repeat, two-map whole-turn comparison
confirmed **exactly 0%** savings, rather than assuming a microbenchmark benefit.

## Rank by actual work, not source appearance

Instrumentation of `Bot.play_turn` and (separately) `farm_camps` found:

| Map | Whole-turn fuel, first round/team | Farming fuel, first round/team | Approximate share |
| --- | ---: | ---: | ---: |
| collision | 3.706–3.716 million (3 calls) | 2.927–2.937 million | 79% |
| corners | 10.211–10.232 million (6 calls) | 8.623–8.642 million | 84% |

These are different instrumented builds, so the share is approximate, not an
exact additive profile. Farming already uses SDK masks and native distance fields;
replacing it with general Python arithmetic or an assumed native extension is not
justified. The safe identified whole-bot opportunity was repeated state queries in
one read-only boolean expression. Allocation/callback/reduction kernels represent
other bot patterns, not the dominant starter workload.

## Implemented generic improvements

1. **Frozen-record direct stores.** Only exact instances with an empty, exact dict
   capture the existing dict and store fields directly. Avoid the temporary dict
   and merge. All other instances use original ordered `object.__setattr__`
   operations, with no extra dict reference retained during setters. This matters
   when an old field's finalizer replaces the dictionary: subsequent stores must
   follow the new dict, and other old-field finalizers must not be delayed. Dict
   subclasses' `__setitem__`/truth overrides must not be invoked either.
2. **Compound native keys.** Multi-index `itemgetter` and multi-path `attrgetter`
   remove Python callbacks returning tuple keys. Preserve left-to-right accesses,
   repeated descriptor access, errors, result tuples and stable ties. Mixed
   item/attribute keys, one-element tuples, starred keys and private names stay
   unchanged.
3. **Filtered bounded reductions.** Materialize only bounded immutable exact-int
   inputs with callback-free total integer expressions and predicates. Retain
   short-circuiting inside predicates. No floating-point reassociation, arbitrary
   filters, division filters, or eager `any`/`all`.
4. **More native-map consumers.** Exact-int `abs` generators in `list`, `tuple`,
   `min`, `max`, `any`, `all`, as well as `sum`. Arbitrary objects are unsafe:
   `__abs__` raising `StopIteration` is a `RuntimeError` inside a generator (PEP
   479), but can silently terminate `map`. Such inputs remain unsupported.
5. **Integer constant membership.** Proven exact-int queries against 4–4,096
   literal ints use CPython's constant-folded frozen sets. No per-call set build or
   persistent dynamic cache. Unknown values, bool/float table entries, effectful
   table expressions and chained comparisons are retained. The configured
   materialization limit also bounds these constants.
6. **Expression-local SDK state sharing.** Only same-receiver, callback-free
   boolean trees of known SDK predicates. Bind a snapshot lazily on each necessary
   path; only dominated reads share it. Never share across actions, statements,
   unknown truth conversions, different receivers or turns.
7. **Native flag groups.** Adjacent same-polarity predicates use precomputed masks:
   `intersects` for any flags, membership for all flags, with the appropriate
   negation. No eager state queries across short-circuit boundaries. This depends
   on `sdk-state-expression`; either pass can be disabled independently.

All passes remain general; no bot/map/strategy names enter the compiler.
Focused differential tests cover the actual risks above, including all bit states
of positive/negative AND/OR groups and paths that skip the first syntactic query.

## Setup-inclusive measurements

The experiment driver compared alternatives rather than simply translating
desktop advice. Both teams completed both maps. Warmed results use five batches
of 20 calls, alternating baseline/candidate order. A separate first-call sample is
now saved before equality checks/warmup. First-call order is baseline-first and
is **not** a statistical cold-start distribution. Module initialization is
excluded: ordinary cambc modules are preloaded/snapshotted. Per-call construction
and allocation are included.

The following manual-alternative table describes the **initial fresh-instance
experiments**, not the final record guard's cost. The final compiler benchmarks
were rerun after the lifetime audit. Earlier concurrent reruns that timed out are
left marked `running` and excluded from final evidence.

| Workload | Baseline / candidate fuel |
| --- | ---: |
| Direct stores vs previous bulk update, 2–20 fields | 1.34–1.81x warm; 1.17–1.40x first call |
| Keyword dict update vs previous bulk update | only 1.03–1.16x |
| Filtered sum, 0–4,096 inputs | 1.10–1.66x |
| Compound item key, 0–128 rows, including row setup | 1.15–1.29x |
| Tuple of native `abs`, 0–128 inputs | 1.50–1.86x |
| Literal integer membership, 4 / 8 / 32 / 128 entries | 1.78 / 2.75 / 7.59 / 19.96x |
| Native flag group, early / late / no match | 1.045 / 1.44 / 1.54x |

Fresh **compiler-generated** suites also passed both maps:

| Kernel | Unmodified source fuel | Generated fuel | Ratio |
| --- | ---: | ---: | ---: |
| Frozen 4-field record | 15,027 | 8,505 | 1.77x |
| Frozen 8-field record | 26,202 | 11,022 | 2.38x |
| Frozen 12-field record | 37,362 | 13,499 | 2.77x |
| Combined decision fixture | 1,887,679–1,887,992 | 696,019–696,383 | 2.71x |

To isolate incremental gains, the trusted previous optimiser at Git commit
`e1ba7a1` was extracted into a separate `/tmp/opencode` directory. It generated
baseline modules without executing bot code. Both those modules and current
generated modules then ran together in the guest:

- 4 / 8 / 12-field construction: **1.32 / 1.45 / 1.51–1.53x** baseline/current.
- Combined decision fixture: **1.504–1.505x**, approximately **33.5% less fuel** than
  the previous optimiser's output. This fixture combines passes and allocations;
  it is **not a production bot or win-rate measurement**.
- Unchanged kernels stayed approximately 1x. Tiny differences in unchanged
  functions are snapshot/allocation-layout effects, not additional pass gains.

These are the **final guarded implementation** numbers, not the initially faster
but incomplete candidate. The audit guard costs roughly 633–658 fuel per fresh
construction in these probes. Both teams also completed guest lifetime tests for
dictionary replacement/finalizer ordering and dictionary-subclass overrides, with
matching results and the transformation actually applied.

## Actual whole-bot measurements

Expression sharing alone (before native flag grouping), three rounds and two
repeats with reversed variant order:

| Map/team | Baseline total turn fuel | Candidate total | Reduction |
| --- | ---: | ---: | ---: |
| collision A | 8,905,036 | 8,780,629 | 1.397% |
| collision B | 9,773,744 | 9,650,237 | 1.264% |
| corners A | 27,617,358 | 27,321,967 | 1.070% |
| corners B | 27,671,570 | 27,375,035 | 1.072% |

Repeated corresponding samples and printed `shared round:` records matched.
The held-out `lanes` map at normal fuel saved about **0.90%** with sharing alone.
Final mask-group and normal-budget results are archived separately in the results
file. With **both state passes enabled**, the final raised-budget totals were:

| Map/team | Baseline | Final generated | Reduction |
| --- | ---: | ---: | ---: |
| collision A | 8,905,036 | 8,689,908 | 2.416% |
| collision B | 9,773,744 | 9,554,470 | 2.244% |
| corners A | 27,617,358 | 27,236,602 | 1.379% |
| corners B | 27,671,570 | 27,292,962 | 1.368% |

Normal-budget repeated comparisons confirmed **2.244–2.416%** on collision and
**1.368–1.379%** on corners. The held-out `lanes` map saved **1.211%**. Raw engine
replay payloads and nonmeasurement stdout matched, not just selected print lines.
A separate **uninstrumented**, default-fuel, three-round comparison also produced
byte-identical engine replay payloads and complete stdout on all three maps.
These observations establish equal sampled trajectories, not equivalence on all
possible inputs. Small counter-instrumentation costs vary with counter magnitude
between raised/normal quantum; absolute saved fuel was consistent.

These are function-boundary fuel measurements, not all-match savings;
imports, drawing outside the boundary, win rates and generalization to other bots
are not claimed. Printed records are witnesses, not full equivalence proofs.

## Regressions, rejected ideas, and remaining work

- **Subclass fallback still loses vs original:** approximately 0.996x warmed and
  0.947–0.948x first-call in the specialization fixture. The guard is necessary for
  descriptor semantics. Disable `record-bulk-init` for subclass-heavy workloads.
- **Repeated initialization loses:** the lifetime kernel's 32 reinitializations
  cost 632,336 versus 582,029 fuel (0.9204x, **8.64% more fuel**). Empty dict
  subclasses also cost about 0.7–0.8% more. These must take the ordered setter
  fallback for correctness. Disable `record-bulk-init` for reinitialization-heavy
  workloads; the lifetime suite includes a separate disabled-pass ablation.
- **Cold early flag match:** the first native-mask probe costs about 2.7% more
  than the original first-predicate short circuit (0.973x); warmed early matches
  improve by 4.5%, and late/no matches improve more. Disable `sdk-state-mask` for
  cold, early-match-heavy code; expression-local sharing remains available.
- The paired previous/current identity sum is 0.9990x, with identical generated
  arithmetic; some unchanged first-call kernels also move slightly. These are
  reported snapshot/layout costs, not suppressed or claimed as pass-level gains.
- **Replacing `__dict__`** outright was rejected on semantic grounds, regardless
  of possible speed: aliases and extra fields on reinitialization would break.
- The initial exact-instance-only direct-store candidate was also rejected as a
  complete generic implementation: reinitialization finalizers can replace the
  dict, and holding a dict reference in fallback delays other finalizers. The
  final empty/exact-dict guard and reference release address both. Focused tests
  compare actual destructor event order, not merely final field values.
- **Keyword dict update** was measured, but direct stores were substantially
  better. No reason to retain a second default initializer strategy.
- **Constant set lookup is not a universal cost theorem.** Huge integer queries,
  adversarial hash collisions or main-module setup can change tradeoffs. Unknown
  types are never hashed speculatively. Use pass ablation on the real workload.
- **Broader shape inference/escape analysis:** the cross-module index identifies
  record layouts and call signatures, not arbitrary runtime field types. Annotations
  do not prove exact values. Repeated attributes/indexes can invoke descriptors,
  and escaping or finalizer-bearing records cannot be scalarized safely by a
  naive substitution. Existing narrow scalar replacement remains narrow.
- **Loop-invariant work** is safe only with proven immutable inputs and no
  observable callbacks. The added constant sets/native masks exploit ordinary
  module snapshots; no live SDK state is persistently cached.
- **Custom native/WASI kernels:** the actual 42,958,023-byte generated Wasm was
  inspected: about 4.53 MB code and 38.17 MB snapshot/data, consistent with an
  interpreter, not native Python loops. The bundled preloader compiles fresh
  `.py` files; bundled CMake builds C++ separately. Public `submit` uploads source;
  no supported mixed Python/custom-native link configuration was found.
  A guest probe confirms `Py_ENABLE_SHARED == 0`, unavailable `_ctypes`/`ctypes`
  and `wasmtime`, while `_operator`, `array` and `_struct` are built in. The guest
  nevertheless reports `.so` extension suffixes: **suffixes are not proof of a
  usable loader/build/submission path**. No arbitrary `.wasm` import route is
  assumed. Supported static builtins/SDK operations remain the evidenced route.
- The then-current blocker was absent economy/planner source and representative
  additional real bots. Recover those inputs before extrapolating record gains
  into whole-planner claims. The economy-source blocker is now resolved in the
  linked follow-up. No measured global plateau is claimed by this earlier work.

## Reproduce

Choose fresh output directories:

```sh
uv sync
uv run python -m unittest discover -s tools/bot_optimizer/tests -q
uv run python benchmarks/bot-optimizer/experiments.py --output replays/fuel-alternatives-new
uv run python -m tools.bot_optimizer.benchmark --suite specialization --output replays/fuel-records-new
uv run python -m tools.bot_optimizer.benchmark --suite advanced --output replays/fuel-advanced-new
uv run python -m tools.bot_optimizer.benchmark --suite core --output replays/fuel-core-new
uv run python -m tools.bot_optimizer.benchmark --suite lifetimes --output replays/fuel-lifetimes-new
uv run python -m tools.bot_optimizer.benchmark --suite lifetimes \
  --disable record-bulk-init --output replays/fuel-lifetimes-disabled-new
uv run python -m tools.bot_optimizer.compare bots/starter-python \
  --target bot:Bot.play_turn --output replays/fuel-starter-new \
  --maps collision,corners --rounds 3 --repeats 2 --require-equal-prefix 'shared round:'
```

Repeat the comparison with `--fuel 100000` for the normal engine quantum (Python
receives its language multiplier), and `--maps lanes` for the held-out scenario.
`--disable sdk-state-mask` measures sharing without grouping;
`--disable sdk-state-expression` disables both. `--baseline-source <file>` on the
kernel benchmark compares an existing equivalent implementation against current
generated code without re-optimizing the supplied baseline. Archives preserve its
exact generated-source hash. To recreate the previous optimiser, extract
`git archive e1ba7a1 tools/bot_optimizer` into a **new** temporary directory and
run its `optimize_source` there on the unchanged kernel fixture.

For separate uninstrumented, engine-default budget checks:

```sh
uv run python benchmarks/bot-optimizer/normal_budget.py bots/starter-python \
  --output replays/fuel-normal-uninstrumented-new --maps collision,corners,lanes --rounds 3
```

`collect.py --output <new.json> label=path/to/results.json ...` archives complete
two-map kernel reports and completed comparison reports, preserving raw fuel
samples and source hashes. It rejects partial reports and never overwrites output.
An earlier foreground starter run timed out and remains `status: running` in its
original directory; it is intentionally excluded from the completed archive.
