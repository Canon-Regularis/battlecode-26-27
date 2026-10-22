# Python bot optimiser

A host-side, whole-folder source-to-source compiler for the project's pinned
**cambc 3.0.4 / guest CPython 3.13.7**. It emits ordinary Python source that cambc
can build into Wasm. It optimises guest fuel, not formatting or desktop timings.
No additional dependencies are needed. Version **0.2** adds whole-folder call
resolution and general record/call optimisations: no bot names, search algorithms
or strategy-specific classes are hard-coded.

## Use

Run from the workspace root, with Python 3.13:

```sh
uv run python -m tools.bot_optimizer bots/economy-bot \
  --output bots/economy-generated \
  --verify --maps collision,corners
```

- Input must contain `src/main.py` (or `main.py` for a flat source folder).
- Output must be a **new, separate folder**. Existing paths are never overwritten;
  input/output nesting is rejected. Your original bot is not edited.
- Python under `src/` is analysed and transformed. Other files, including tests
  and assets, are copied. Cached builds, virtualenvs, Git metadata, bytecode and
  root-level `build/` / `target/` directories are excluded. Symlinks are rejected.
- Unchanged Python files remain byte-for-byte identical. Changed files are
  AST-emitted Python: comments and original formatting are not retained.
- `optimizer-report.json` records input fingerprint, options, source locations,
  before/after expressions, pass counts, warnings, assumptions and validation.
- No input bot modules are imported or executed on the host during compilation.

`--verify` builds the generated bot using `cambc build --release`. Adding `--maps`
runs generated-vs-generated smoke matches (three rounds by default), checking the
replay logs for Python failures. These checks are **not behavioural equivalence
proofs or whole-bot fuel measurements**. Use `--rounds` to change their length.
The driver prefers `.venv/bin/cambc`; `--cambc` selects another executable. Runtime
checks reject versions other than 3.0.4, avoiding the old global executable noted
in the research.

```sh
uv run python -m tools.bot_optimizer --list-passes
uv run python -m tools.bot_optimizer bots/my-bot --output bots/my-generated \
  --disable bounded-sum --disable native-attrgetter
```

For an existing bot with host-side tests, run the **copied tests** against the
generated modules, for example:

```sh
uv run python -m unittest discover -s bots/economy-generated/tests -v
```

## Implemented passes

| Pass | Recognised pattern / guard |
| --- | --- |
| `integer-square` | Local exact-integer `x**2` → `x*x`; e.g. induction variables from an unshadowed `range` |
| `native-map` | Eligible `sum(abs(x) for x in range/tuple)` → native `map`; no filters or shadowed callbacks |
| `bounded-sum` | Pure exact-integer sum generator → list comprehension, with a statically bounded `range` |
| `mask-count` | `len(board.positions())` → `board.count()` |
| `mask-empty` | `bool(board.positions())` → `not board.is_empty()` |
| `mask-filter` | `[p for p in a.positions() if b.is_set(p)]` → `(a & b).positions()` |
| `mask-intersection-count` | `sum(1 for p in a.positions() if b.is_set(p))` → `(a & b).count()` |
| `native-key` | Eligible `key=lambda p: field.get(p)` → `key=field.get`, over a fresh SDK positions list |
| `native-itemgetter` | Fixed-index lambda keys → precomputed native `itemgetter` |
| `native-attrgetter` | Attribute-only lambda keys → precomputed native `attrgetter`, including nested paths |
| `identity-reduction` | `sum(x for x in values)` → `sum(values)`; also streaming `min`, `max`, `any`, `all` |
| `bounded-reduction` | Pure integer reductions over known immutable tuples; also bounded integer `min`/`max` |
| `call-positional` | Convert a leading sequence of keywords to positional arguments at resolved function/constructor calls |
| `inline-integer-helper` | Inline a small resolved arithmetic-only helper when all supplied inputs are proven exact integers |
| `record-bulk-init` | Populate an eligible frozen dataclass using one native dictionary update, with subclass fallback |
| `scalar-record` | Eliminate a primitive-valued temporary record used only by an immediately following return expression |

Key passes cover unshadowed `min`, `max`, `sorted`, and eligible list `.sort` calls.
The SDK-method pass also recognises a proven `Vec2.chebyshev_distance` callback.
Private attributes subject to class-name mangling are not rewritten.

Native operator key objects are generated once at module scope, using uniquely
named helpers imported from built-in `_operator`. For ordinary modules, cambc's
preloader snapshots these helpers, moving their construction out of match time.
In `main.py` they are initialised at runtime instead. Small or rarely used call
sites may not amortise that setup; disable passes and measure your actual bot.

The materialisation limit is **4,096 elements**, configurable through
`--max-materialize`. A limit of `0` disables nonempty materialisations. No blanket
generator replacement occurs in `any`, `all`, or other short-circuiting searches.
Floating-point reductions are not reassociated or materialised by this pass.

### Whole-folder specialisation

`program.py` indexes stable, source-defined functions, class constructors and
simple dataclass layouts across modules, relative imports and re-exports. The
report includes resolution counts. Unknown/decorated/rebound callables stay
unknown. Dynamic module `__getattr__` disables these whole-folder specialisations;
cyclic imports prevent cross-module lookup elimination. This is **not** full
Python type inference or unrestricted inlining.

Positional-call lowering preserves argument evaluation order, positional-only and
keyword-only restrictions, and does not repair invalid calls or fill default
holes. Integer helper inlining keeps only small leaf expressions, with no globals,
user callbacks or unproven operand types.

Frozen-record bulk initialisation requires a plain, non-inheriting dataclass with
ordinary fields, no defaults/factories/hooks/custom methods/slots, and at least
**four fields** (`--min-bulk-fields`). Exact instances use `self.__dict__.update`;
subclasses execute the original per-field `object.__setattr__` operations so
subclass descriptors still work. The class type, field values, freezing, equality,
hashing, constructor argument names/annotations and generated docstring are
preserved. Arbitrary record values are allowed: field annotations are used to
identify layout, **not** assumed to prove the runtime value types.

Scalar replacement is narrower: a temporary must not escape, and its supplied
values must be proven finalizer-free primitives. Unknown field objects, captures,
later uses, hooks and nontrivial constructors are retained. This avoids changing
observable destructor lifetimes or public return types.

Immutable tuple facts come from literals and known tuple/range construction.
Opt-in supported tuple parameter annotations are also available. For a proven
integer tuple of unknown length, a reduction can use a bounded fast path:

```python
sum([x*x for x in values]) if len(values) <= 4096 else sum(x*x for x in values)
```

Identity reductions remain streaming and preserve short-circuiting. The pass does
**not** generalise to `list`, `tuple`, or `sorted` over unknown iterables, since
those consumers can consult observable length hints.

## Safety model and limits

This is a conservative compiler under a **closed-world bot/SDK contract**, not a
proof system for arbitrary reflective Python:

- Builtins, public SDK APIs and resolved bot functions/types must not be
  monkey-patched, including through external aliases. No external reflection,
  tracing, frame inspection or function/module namespace mutation is supported.
  Detected dynamic operations, star imports and imported-object writes disable
  rewriting across the submitted source folder. This detector is conservative,
  not an exhaustive security analysis.
- Types come from known constructors/public SDK returns and straight-line facts.
  Branch facts are merged conservatively; loop writes, exception edges, captured
  nonlocal writes and delayed generator bodies invalidate relevant facts. Mutable
  list contents are not assumed to retain their inferred element types.
- Annotations are **not trusted by default**. `--trust-annotations` explicitly
  treats supported SDK/int/integer-tuple parameter annotations as exact-type contracts, not
  merely Python subtype hints. Use it only if those contracts are true.
- Dynamic state is not cached or hoisted. SDK-owned masks are never mutated by a
  generated rewrite. Native masks remain in their SDK representation.
- Fuel readings, allocation identity, resource exhaustion, traceback text and
  implicit suspension timing can differ. There is no promise of identical turns
  when one version runs out of fuel. Fuel-aware search can intentionally make
  different choices after optimisation; this is flagged in the report.
- No module flattening, unrestricted inlining, general escape analysis, arbitrary
  BFS recognition, persistent dynamic caching or per-bot autotuning is implemented. Unsupported
  regions are kept rather than guessed at. A bot can legitimately get zero rewrites.

Generated source and reports are deterministic for a fixed input/options/host
Python version. Runtime smoke reports additionally contain their replay paths.
Always recompile from the original source: generated namespace writes are outside
the accepted input analysis subset, so re-optimising generated output is normally
a no-op rather than an incremental optimisation route.

## Tests and measured evidence

```sh
uv run python -m unittest discover -s tools/bot_optimizer/tests -v
uv run python -m tools.bot_optimizer.benchmark \
  --output replays/bot-optimizer-check --maps collision,corners
uv run python -m tools.bot_optimizer.benchmark --suite specialization \
  --output replays/bot-optimizer-specialization --maps collision,corners
```

The benchmark compiles real source kernels with this optimiser, then runs
**original and generated implementations together inside the Wasm guest**.
It checks results (including positions ordering), warms both implementations,
alternates measurement order, and records five batches of 20 calls. Both teams
must complete all cases. The raised fuel prevents suspension during measurement;
no private engine imports or debug fuel exemptions are used.

All 10 initial kernels improved on both maps: approximately **1.26–30.25x**
baseline/generated fuel, with per-call setup included. These are workload-specific
ratios, **not whole-bot speedups**. See the recorded
[results](../../benchmarks/bot-optimizer/results.json) and
[benchmark instructions](../../benchmarks/bot-optimizer/README.md).

The new specialization suite tests records of different widths, tuple reductions,
helper calls, keyword binding and temporary elimination, plus a losing subclass
fallback case. New measured kernel ratios were **1.27–5.40x** for the improving
cases, with setup included. The subclass fallback was approximately **0.994x**:
correct, but slightly slower. Measure your bot; no pass is universally profitable.

Version 0.2 produced **13 rewrites** on economy-bot (five bulk initialisers, five
call conversions, three native keys). The generated bot passed all **71** copied
tests and normal-budget two-map smoke checks with identical ranked reports. A
repeatable, raised-budget whole-planner comparison found approximately **13.6–14.5%
less fuel** for equal reported work, not the negligible benefit of version 0.1.
See [recorded v2 results](../../benchmarks/bot-optimizer/economy-v2-results.json).
The starter bot still had no applicable default rewrites and built/ran correctly.

## Compare your own bot

The comparison tool accepts **any source-defined synchronous function/method** as
the measurement boundary; it is not tied to economy-bot:

```sh
uv run python -m tools.bot_optimizer.compare bots/economy-bot \
  --target draft_planner:DraftPlanner.build \
  --output replays/economy-optimizer-comparison \
  --maps collision,corners --repeats 2 \
  --require-equal-prefix 'SQUAD_LOOPS_DATA '
```

It stages baseline and generated copies, adds identical public fuel-counter
instrumentation, alternates variant order between repeats, runs release
self-matches, and compares corresponding teams. An optional printed-record prefix
requires identical output lines. Mismatched call counts, missing measurements,
invalid intervals and logged failures are rejected. `results.json` must have
`status: "complete"`; partial runs remain marked `running`.

Choose a stable outer boundary that is not itself removed by inlining. Targets
must fit within their fuel budget and must not yield/end turns. Direct generator,
async and `end_turn` targets are rejected; hidden suspension inside callees cannot
be proven absent. Equality of printed records is a useful check, **not proof of
all actions or semantics**. Different random scenarios or fuel-limited search work
must not be mistaken for a speedup. The default high fuel is for controlled
measurement; always test normal budgets separately.

`--disable PASS` supports ablation (for example `--disable record-bulk-init`), and
`--trust-annotations` uses the same opt-in contracts as the compiler. None of this
automatically selects passes for a production bot.

The foundation is the repository research; read both documents before extending
the optimiser:

- [`PythonPerformance.md`](../../docs/cambc/PythonPerformance.md)
- [`PythonSDKPatterns.md`](../../docs/cambc/PythonSDKPatterns.md)
- [`python-fuel` probe and losing alternatives](../../benchmarks/python-fuel/README.md)

## Layout

- `analysis.py`: lexical bindings, conservative exact-type facts, dynamic hazards.
- `program.py`: cross-module symbol/signature and simple-record layout index.
- `records.py`: guarded frozen-record construction and narrow scalar replacement.
- `passes.py`: guarded AST rewrites and build-time native-key helpers.
- `compiler.py`: source/folder compilation, assets, deterministic diagnostics.
- `runtime.py`: pinned cambc build and replay-log smoke checks.
- `benchmark.py`: generated-code paired fuel experiments and completeness checks.
- `compare.py`: user-selected whole-bot function fuel comparisons and output checks.
- `tests/`: differential, scope, mutation, exception, folder and CLI regressions.
