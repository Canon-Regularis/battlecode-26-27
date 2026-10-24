# Twenty-percent planner fuel target

The starting compiler is the final candidate documented in
[`economy-followup.md`](economy-followup.md): 17.39% collision, 18.76% corners,
18.86–18.87% held-out lanes relative to the unchanged original economy bot.
The target of at least **20% on every map** is achieved at the same equal-work
`DraftPlanner.build` boundary. Two repeated raised-budget measurements, explicit
work counts, normal-budget checks and source provenance are verified. The complete
audit and 18 supporting reports are in [`twenty-percent-results.json`](twenty-percent-results.json).

| Map | Final planner fuel reduction versus original |
| --- | ---: |
| collision | **20.30–20.31%** |
| corners | **22.50%** |
| held-out lanes | **22.99–23.01%** |

Evidence: `replays/economy20-shortcircuit-raised/results.json`. Both repeats match
exactly for each team. This measures the planner call, not whole-match fuel or
win rate. The accepted additions are cached large-record factories, guarded
short integer reduction fusion, and guarded `any`/`all` comparison loops. Deferred
allocation was rejected and is absent from the compiler.

## Actual Wasm inspection

Inspected `replays/economy-cached-raised/optimized/.cambc/build/bot.wasm` with WABT:

- 42,988,823 bytes total, 10,410 defined functions and 198 imports.
- 4,526,588 bytes of code versus 38,197,391 bytes of snapshot/data.
- Names identify the CPython interpreter and native builtins, not native compiled
  planner arithmetic. The planner's Python instructions execute within that runtime.

`wasm_inspect.py` archives the module hash, selected instruction inventories and
actual disassembly excerpts in `replays/economy20-wasm-analysis`. The full local
disassembly is `/tmp/opencode/economy-cached-wasm-disassembly.txt`.

| Function | Static instructions in function body | Relevant inspected path |
| --- | ---: | --- |
| `gen_iternext` | 86 | Calls `gen_send_ex2`, handles completion/error and references |
| `gen_send_ex2` | 388 | State/error checks, frame evaluation and runtime accounting |
| `PyObject_GetAttr` | 113 | Type checks and indirect attribute dispatch |
| `_PyObject_GenericGetAttrWithDict` | 471 | Descriptor checks, type/dict lookups, errors |
| `builtin_sum` | 1,023 | Iterator advancement, native integer/float paths, generic additions |
| `_PyEval_EvalFrameDefault` | 30,358 | Bytecode dispatch and specialised execution paths |

These are **static inventories, not dynamic instruction counts or fuel estimates**.
Not every branch executes, and callees contribute additional work. The sum body
contains distinct integer and floating-point paths, reinforcing why generic
Python accumulation must not replace `sum` without exact-type proofs. Generator
and attribute paths expose plausible overhead to avoid through source transforms;
the runtime and its fuel accounting are not modified.

Reproduce with WABT installed or via its npm package:

```sh
npm exec --yes --package=wabt -- wasm-objdump -h <bot.wasm>
npm exec --yes --package=wabt -- wasm-objdump -d <bot.wasm> > <disassembly.txt>
uv run python benchmarks/bot-optimizer/wasm_inspect.py \
  <bot.wasm> <disassembly.txt> --output <fresh-directory>
```

## First 42 measured alternatives

`replays/economy20-wasm-candidates` includes both maps and all guard/setup costs:

- Prebound-allocator factories for 4/8/12/20 fields: **1.012–1.031x** versus
  current guarded initialization. Earlier uncached large factories lost; caching
  reverses the result. The generic `record-call` candidate enables only the
  measured 4–20-field range and requires allocator caching.
  The implemented candidate passes 118 optimiser tests and 240 exact host planner
  scenarios. Two-repeat whole-planner measurements save **17.47% collision and
  18.85% corners** versus original (`economy20-large-factories`), so this gain alone
  does not meet the target.
- Tuple-unpacked dict stores: approximately **0.94–0.95x**, rejected.
- Literal dict updates: approximately **0.57–0.74x**, rejected.
- Guarded fusion of three indexed exact-int reductions: wins at 0–4 selected rows
  (about 1.10x at four rows without row setup), loses at 8/32 rows. It cannot be
  enabled without a profitability size bound.
- Guarded eager reductions often lose despite the unguarded version winning.
  The guard must prove exact containers, indices, records and integer fields;
  omitting it is not a semantic solution.

```sh
uv run python benchmarks/bot-optimizer/wasm_experiments.py --output <fresh-directory>
```

## Deferred record investigation — rejected

The Wasm allocation/dictionary paths motivate avoiding records that are immediately
rejected by a caller. A source-method clone could return an internal field carrier,
with the caller materializing the original exact record only at escape. Public
methods and unknown/overridden callables must retain their original behaviour.

A reverse-order tuple carrier is **unsafe for arbitrary payloads**. Seeding a
fresh record's shared keys in `d,b,a,c` order makes ordinary instances release
fields in that order, while the carrier releases `a,b,c,d`. The earlier simple
lifecycle witness missed this case.

Consequently `replays/economy20-deferred-generated` and
`replays/economy20-deferred-raised` are **excluded unguarded-prototype evidence**.
Their 20.02% collision, 20.64–20.67% corners and 20.27–20.29% lanes results do
not establish the target. Archives are preserved rather than overwritten.

The first correction used annotations only to select exact primitive
runtime type checks. Nonprimitive payloads return ordinary records. Each caller
result has its carrier status checked anew; overridden callables use the original
path. Identity checks avoid user metaclass equality/hash hooks. The corrected
compiler passes 124 optimiser tests and 240 exact planner differential scenarios
(`economy20-guarded-deferred-differential`, observation hash
`f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6`).
Those checks alone were subsequently found insufficient; see the second witness below.

The completed guarded run (`economy20-guarded-deferred-raised`) saves only
**17.68% collision, 18.15–18.17% corners, and 17.77–17.79% lanes**, repeated
twice. It therefore fails the target and regresses on two maps relative to the
large-factory candidate. The generated deferred fixture nevertheless wins its
particular workloads: 2.36x rejected, 1.72x quarter-retained and 1.11x retained
versus original source (all enabled compiler passes, not the deferred pass alone).
Its 71 copied bot tests pass. Whole-planner costs determine acceptance.

**Second counterexample:** reject a primitive-valued first record; between producer
calls, seed the class's shared keys in `d,b,a,c` order; retain the next primitive
record and replace its fields with finalizable values. The original releases
`a,b,c,d` because the first rejected allocation established that key history.
The guarded prototype releases `d,b,a,c`. Primitive initial payloads do not prove
that skipped allocations are unobservable later.

The deferred pass has therefore been **removed from compiler execution**, with its
source preserved in `deferred_prototype.py`. Both guarded deferred archives are
also excluded from acceptance. `deferred-record` remains a compatibility disable
switch for reproducing variant commands; it performs no transformation. The new
regression preserves primitive rejection and later shared-key/finalizer history.

Design constraints for a possible implementation: use a separate producer clone;
guard resolved bound-method identity and preserve overridden/instance-supplied
callables; permit only known simple frozen record returns or `None`; preserve
constructor argument evaluation order; rewrite only nonescaping field reads and
`None` checks; materialize into the original local before its first escape so a
carrier cannot retain stale field references after user-visible mutation. Reject
private-name mangling, unsupported closures/defaults and ambiguous control flow.
Finalizer order must be validated beyond a single primitive-valued example.

```sh
uv run python benchmarks/bot-optimizer/wasm_experiments.py \
  --focus deferred --output <fresh-directory>
```

## Guarded short-reduction implementation

`short-int-reductions` recognizes three adjacent indexed field sums into fresh,
singly assigned locals. Its helper accepts only exact tuple routes of length at
most eight, exact list/tuple inputs, in-bounds exact integer indices, a known exact
hook-free record type, and exact integer field values. It checks and accumulates
in one loop; no float reassociation occurs. Unsupported inputs execute the three
original statements, after helper references have been released. Missing fields
also fall back. Source-level explicit attribute mutation disables this pass.

The restriction to fresh locals avoids moving a prior target's finalizer across
reductions. Only straight-line function-body triples qualify; nested scopes and
loop bodies stay unchanged. No source record names or planner-specific fields
are built into the matcher.

The initial combined candidate passed 128 optimiser tests and 240 exact
differential scenarios, with two fusion sites (public producer and private clone).
After rejecting deferred allocation, only the ordinary producer's fusion remains.
The four-element-limit reduction-only comparison completed with two repeats:
**17.38% collision, 19.20% corners, 19.33–19.35% lanes**. It misses the target and
slightly regresses on collision. `economy20-short-reductions-raised` is an excluded
combined deferred prototype; `economy20-short-reductions-only-raised` is the
independent reduction-only measurement.

The generated fixture gains 2.39–2.41x empty, 1.80–1.81x one row, 1.23x four
rows, and 1.27x big integers. Guard/fallback costs lose on unsupported inputs:
0.96–0.98x long routes, 0.85–0.86x floats, and 0.97x custom protocols.

The newer check-and-accumulate loop differs from the first two-pass manual
experiment. Measuring its actual emitted code (`economy20-fused-bounds`) finds
1.149x at five rows, 1.089x at six, and 1.005x at eight; twelve and above lose.
The compiler limit is therefore extended to **eight**, with original fallback
beyond it. Two-repeat all-map measurements (`economy20-fused-eight-raised`) reach
**18.24–18.25% collision, 20.47% corners, 20.93–20.95% lanes**. Collision still
fails the target, so the goal remains open.

```sh
uv run python -m tools.bot_optimizer.benchmark --suite reductions \
  --output <fresh-directory>
```

## Short-circuit experiment

A direct helper loop may avoid generator resumptions for `any`/`all` comparisons.
This remains experimental. Its semantic audit must preserve yielded-value cleanup,
boolean exceptions versus PEP 479 predicate exceptions, input mutation, and iterator
protocol calls. Host CPython 3.13.11 executes two `GET_ITER` operations for the
original generator expression; an ordinary helper loop executes one. The candidate
therefore falls back for non-exact-list/tuple inputs rather than eliding user
`__iter__` calls. Twelve host exact-list mutation/finalizer/exception witnesses
match with explicit result cleanup and boolean-error item cleanup.

The first manual guest experiment (`economy20-shortcircuit-candidates`) omitted
the container guard and is only an upper-bound performance probe: roughly
1.45–2.41x. It is not the accepted compiler implementation.

`short-circuit-loop` now implements the guard and original generator fallback,
limited to single element-versus-literal comparisons over a local name. Nested
functions, captured/rebound cells, comprehension scopes, generic type-parameter
scopes, filters, unknown predicates and shadowed consumers remain unchanged.
The helper releases the predicate result before continuing or returning; on
boolean exceptions it also releases the element before propagating the error.
Predicate `StopIteration` is translated to `RuntimeError` with its original cause,
while boolean `StopIteration` propagates directly, matching generator/consumer
semantics. 133 optimiser tests, 71 copied bot tests and 240 exact differential
scenarios pass. The generated guest suite completes all 13 cases on both maps:
fast paths gain 1.42–1.75x; custom iterator and exception paths retain semantics
with roughly 0.99–1.01x ratios. Whole-planner gains reach the table above.

## Final verification and archive

Final jobs separately observe expansion counts at raised and normal budgets,
and compare uninstrumented three-round engine replays/stdout at normal fuel:

| Map | Raised expansions, original/generated | Normal expansions, original/generated |
| --- | ---: | ---: |
| collision | 6,020 / 6,020 | 64 / 96 |
| corners | 20,000 / 20,000 | 1 / 1 |
| lanes | 20,000 / 20,000 | 1 / 1 |

Raised runs match engine replays and full stdout. Normal counter instrumentation
exposes collision's increased search work, so its stdout differs as expected.
Separate **uninstrumented three-round** normal runs match engine replays and full
stdout on every map. Normal-budget behaviour is not the equal-work fuel metric.

The completed audit collector verifies raw report completeness,
all-map reductions, exact repeats, expansion equality, unchanged source bytes
against commit `97f761f04ed3d3e85a6f2217df345629baab58c8`, and the bot's untracked
status. It regenerates both source variants, reapplies timing instrumentation,
and requires byte-identical emitted sources to those actually measured. All 22
original files match the source commit byte-for-byte; the bot remains untracked
and the Git index is empty. Current generated sources also exactly match those
used for the 240 differential scenarios and uninstrumented normal-budget checks.
The compiler and generated sources are snapshotted in `replays/economy20-final-audit`.
Rejected prototypes are explicitly excluded in the compact archive.

The final Wasm is 43,004,984 bytes (SHA-256
`b829d47903c42af71653d4665c3377ca11632ebe6997adb52e7053f18da3b578`). Its
4,526,588-byte **runtime code section is byte-identical** to the inspected module.
The savings come from executing fewer expensive interpreter/generator operations,
not shrinking native code or changing runtime fuel accounting. The snapshot/data
section is larger because it contains the additional Python helpers.

```sh
uv run python benchmarks/bot-optimizer/audit_twenty_percent.py \
  --output benchmarks/bot-optimizer/twenty-percent-results.json \
  --snapshot replays/economy20-final-audit
```
