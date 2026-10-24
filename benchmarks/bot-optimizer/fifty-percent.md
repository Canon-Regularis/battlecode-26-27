# Generic planner fuel reduction: 50% target

Baseline: unchanged `bots/economy-bot`, fingerprint
`950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c`.
Measurements target `draft_planner:DraftPlanner.build` under cambc 3.0.4,
guest CPython 3.13.7. All snapshot setup, guards and fallback dispatch are timed.

## Wasm and dynamic evidence

The refreshed `economy50-functions-profile` shows the numeric evaluator taking
643,976,918 inclusive instrumented fuel over 6,020 collision calls and
1,912,099,254 over 20,000 corners calls. Snapshot setup is small by comparison.
These profiles include instrumentation overhead and are not savings claims.

Actual Wasm disassembly exposes the costs behind repeated operations:
`min_max` has 561 static instructions and 20 direct call sites; `float_mul`
and `float_div` include type dispatch, integer-to-double conversion, exception
checks and result construction. The structural change removes repeated visits
to these runtime routines. It does not change the runtime or its fuel accounting.
Fresh excerpts and inventories are in `replays/economy50-final-wasm-analysis`.

## Generic structural changes

* `numeric_ops.py` consumes private emitter-owned type facts after helper
  inlining. Stable two-argument extrema become single-evaluation comparisons;
  eligible integer `any`/`all` inequalities use native extrema with explicit
  empty-input handling. Floating-point predicates retain their original path.
* `derived_tables.py` recognizes arithmetic over immutable snapshot projections
  and one or two finite index domains. It computes primitive tables once per
  consumer epoch, replacing repeated field loads and arithmetic with indexed
  reads. Equal domain lengths preserve negative-index semantics. Ragged,
  overflowing, zero-dividing, absent-optional, or oversized preparations retain
  the original expression. Each table is capped at 4,096 cells.
* Adjacent single-use total numeric temporaries can be folded into their consumer
  expression, exposing a complete indexed calculation for precomputation. This
  runs only in native-index-retry entries; earlier potentially raising arithmetic
  prevents folding. Retry restores original exception order and container error
  wording. Alias tracking handles loop backedges, rebinding, annotated assignment,
  and comprehension shadowing.
* Integer reduction fusion preserves emitter metadata instead of discarding it
  through source re-parsing. Native compensated floating-point `sum` remains in
  place, including the integer-zero result for empty inputs.

Production discovery contains no planner names or formulas. Annotations select
runtime guards; only validated exact primitives establish the contracts. Tables
retain primitive copies, not mutable input aliases. Record allocation and public
signatures retain their existing behavior.

## Measured progression

| Archive | Collision | Corners | Lanes |
| --- | ---: | ---: | ---: |
| Historical audited 40% result | 43.46% | 45.05% | 45.55–45.56% |
| `economy50-numeric-ops` | 45.42% | — | — |
| `economy50-derived-tables` | 48.81% | — | — |
| `economy50-derived-v2` (two repetitions) | **52.70–52.71%** | **53.06%** | **53.59–53.60%** |

Both teams and both repetitions produce matching planner reports on every map.
The 50% baseline is the unchanged original bot, not the previous optimizer.

## Validation

Host checks currently pass **227 compiler tests**, **71 copied bot tests**, and
240 exact public planner scenarios. The public observation hash remains
`f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6`.
Explicit fast-path validation passes 240 contexts, 1,152 direct evaluations and
3,586 consumer numeric calls, with exact records and stop counts and no retained
mutable input aliases. Its emitted planner hash matches the measured candidate.

Final audit passed. Raised-work counts match exactly: **6,020 / 20,000 / 20,000**
for collision/corners/lanes on both teams. Repeated measurement replays and all
nonmeasurement stdout match. Three-round uninstrumented normal-budget replays
and stdout also match on every map. Exit-only normal-budget probes show collision
expands **88 versus 64** in the original; corners and lanes both expand once.
The snapshot tables trade additional setup for lower repeated-evaluation cost:
collision's normal-budget count is below the previous optimizer's 128 expansions.

All **36 guest fixtures** pass on collision/corners under guest CPython 3.13.7.
The new `fifty` suite covers negative indices, unequal domains, ragged matrices,
NaNs/infinities, signed zero, skipped and taken arithmetic errors, and original
index-error ordering. Tiny setup-heavy fixtures are semantic checks, not the
planner fuel claim.

`audit_fifty_percent.py` verified all 22 original files against provenance commit
`97f761f04ed3d3e85a6f2217df345629baab58c8`, unchanged public signatures and Wasm
runtime code, and byte-identical reproduction of measured and instrumented
sources. Evidence is in `fifty-percent-results.json`; compiler, benchmark tools,
baseline and generated sources are preserved in
`replays/economy50-final-audit-snapshot`. The original bot remains unchanged and
untracked. The earlier archives remain preserved. The user replaced the paused
50% goal with an 80% goal before this audit completed; this archive is the audited
starting point for that continuing work.
