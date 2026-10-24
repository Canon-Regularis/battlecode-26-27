# Verified 80% planner fuel savings

The target is achieved: **80.02099–81.34400% less `DraftPlanner.build` guest Wasm
fuel** versus the unchanged original economy-bot on collision, corners and lanes.
Two repeats have identical fuel counts for every map/team pair, with explicit
equal work and matching engine replays. Final evidence is in
[`eighty-percent-results.json`](eighty-percent-results.json) and
`replays/economy80-final-audit-snapshot`; see the final audit section below.
The fully audited starting point was **52.70–53.60%**, preserved in
`fifty-percent-results.json` and `replays/economy50-final-audit-snapshot`.
The following research log retains intermediate results and historical statuses.

## Remaining hotspots

`economy80-numeric-profile-v2` instruments the emitted numeric evaluator rather
than its original public fallback. Section timings include substantial probe
overhead; they rank opportunities rather than measure savings.

Collision side-a inclusive section fuel over 6,020 evaluations:

| Section | Instrumented fuel |
| --- | ---: |
| Input setup | 41,769,343 |
| Edge materialization/validation | 129,621,760 |
| Integer totals | 128,086,600 |
| Timing arithmetic | 52,669,129 |
| Scoring arithmetic | 41,118,874 |
| Risk calculation | 175,720,071 |
| Final scoring and record allocation | 88,373,171 |

Routes grow to length 10 on collision and length 8 on corners. Only 233/6,020
collision evaluations and 644–649/20,000 corners evaluations repeat their exact
argument tuples. Whole-evaluator memoization is therefore not the first candidate.
Actual Wasm `object_new`, `float_mul`, and `float_div` excerpts were also inspected;
record allocation remains required at its original point because shared dictionary
key history can affect later finalizer ordering.

## Integer reduction reuse

The first candidate preserves emitter contracts on fused integer reductions and
caches their primitive outputs by the complete sorted index tuple. This key keeps
duplicate and negative indices distinct while sharing work across permutations.
The cache belongs to one validated consumer epoch and is capped at 4,096 entries.
Its input table must resolve to an immutable snapshot path independent of runtime
indices. Floating-point calculations and record allocation retain their original
execution paths.

`economy80-reduction-memo` measures **55.52–55.53% collision savings**, with matching
reports. Validation passes 228 compiler tests and 240 explicit fast contexts,
including 1,152 direct evaluations and 3,586 consumer numeric calls. New regression
coverage checks permutation hits, duplicate/negative-index distinctions and fresh
caches after a new snapshot epoch.

## Setup check hoisting

The next candidate checks each distinct snapshot length only over indices on which
that length depends. It omits tautological checks and avoids unrelated Cartesian
products. The previous table setup reduced normal-budget collision expansions
from the older optimizer's 128 to 88 (original: 64); recovering setup cost matters
in addition to raised-budget fuel savings.

Targeted tests pass. `economy80-memo-hoisted-setup` measures **55.65% collision,
55.39–55.40% corners, and 55.97–55.98% lanes** savings with matching reports.
`economy80-memo-hoisted-normal` records **104 collision expansions versus 64**
in the original, with an identical engine replay.

## Prefix projections and scalar invariants

Projection facts now survive the fixed positive prefix of a certified owned
numeric list across append/extend operations. Equivalent constant-index reads of
an immutable integer tuple share one precomputation index domain. Negative list
indices are not inferred from a prefix. Rebinding an index or tuple invalidates
dependent facts. Snapshot-only scalar arithmetic can also be prepared once, with
the original expression retained when preparation fails.

This exposes complete indexed products/divisions instead of caching only an
inner addition. `economy80-prefix-projections` measures **56.59% collision savings**
with matching reports. Full compiler tests passed before two additional targeted
tuple-alias regressions; those also pass. Explicit fast validation again records
240 contexts, 1,152 direct evaluations and 3,586 consumer calls.

## Numeric-entry inlining prototype

`eighty_inline.py` is a research-only post-compilation transform. It reuses the
numeric helper inliner with an explicit larger size limit, maps return branches
to the consumer result, retains native-index retry and the public fallback, and
releases the returned record's extra temporary alias. Production integration is
pending actual guest profitability and a broader semantic audit.

Host-only in-memory instrumentation in `generic_region_differential.py` verifies
240 contexts and 3,586 inlined entries without changing staged source files.
Complete records, stop counts and mutable-input retention checks pass.
`economy80-inline-prototype` measures **57.29–57.30% collision savings** with
matching reports. A follow-up hoists single-assignment validated snapshot-root
loads out of the repeated consumer loop. It excludes rebound/deleted locals;
its explicit fast-path host checks also pass. Its guest measurement is running
in `economy80-inline-hoisted-prototype`. Neither prototype is yet integrated.

### Integrated inlining validation

The inliner and guarded snapshot-load hoisting are now integrated under
`numeric-entry-inline`, authorized by emitter-owned metadata. Validation passes
238 compiler tests, 240 exact public scenarios, 240 fast contexts, 1,152 direct
evaluations and 3,586 observed inline entries. `economy80-inline-integrated`
measures **58.95–58.96% collision, 58.94–58.96% corners, and 59.54–59.55% lanes**
with matching reports. All ten `fifty` guest fixtures pass on collision/corners.
`economy80-inline-normal` records **112 versus 64** collision expansions with
an identical engine replay.

## Native prepared projection collection

Actual Wasm `itemgetter_call_impl` (disassembly line 1746710, address `3e6e8e`)
constructs multi-index tuples natively. `eighty_projection.py` tests replacing
a prepared projection comprehension with `itemgetter(*indices)(table)` for
more than one index. Native compensated `sum` remains unchanged; empty/singleton
inputs use a comprehension and failed preparation uses the original expression.
The prototype measures **59.678–59.679% collision savings** with matching reports
in `economy80-native-projection` and passes explicit fast checks.

This is now integrated in `DerivedTables`, using its own prepared-table metadata,
the numeric emitter's native-sum proof and exact integer-tuple schema. New tests
cover empty/singleton inputs, cancellation-sensitive float sums, duplicate and
negative indices, failed preparation, exception ordering and missing contracts.
All **241 compiler tests**, 240 public scenarios and 240 fast contexts pass.
`economy80-projection-integrated` measures **59.62% collision, 59.40–59.42%
corners, and 60.00–60.01% lanes**, with matching reports. The `fifty` guest suite
passes all ten fixtures on collision/corners in `economy80-projection-guest-fifty`.

`section_profile.py --inline-sections` now inserts benchmark-only straight-line
boundary and early-return probes before production inlining. This profiles the
executed consumer rather than the unused canonical numeric entry. Its dry-run
verifies that all seven sections survive inlining; guest profiling is next.

The completed `economy80-inlined-section-profile` confirms all **6,020 / 20,000**
numeric evaluations on collision/corners. Collision section fuel (including
probes) is: inputs 28.87M, edges 131.99M, totals 88.85M, timing 53.25M, scoring
41.89M, risk 152.31M, record 85.61M. The whole consumer is 1,056.62M, versus
1,071.54M for the whole build. Costs outside the numeric sections are still
substantial, so `--consumer-sections` now separately measures generator
resumption, checks, numeric dispatch, candidate handling and beam selection.

## Native pairwise traversal prototype

`eighty_native_edges.py` is a separate research-only transform. For prepared
pairwise tables and routes longer than two elements, native `itemgetter` selects
rows, `map(getitem, rows, indices)` selects values, and `reduce(add, ..., initial)`
performs the original sequential additions. This intentionally keeps ordinary
left-to-right float rounding. The original loop remains for short routes and
failed preparation. Actual Wasm `functools_reduce`, `map_next`, `_operator_add`
and `_operator_getitem` were located; `functools_reduce` reuses its two-argument
tuple while traversing the native iterator.

The prototype passes 240 fast contexts, 1,152 direct evaluations and 3,586 observed
inline entries in `economy80-native-edges-fast`, but **regresses collision savings
to 56.48–56.49%** in `economy80-native-edges`. It is rejected for production.
Native callback dispatch costs outweigh the avoided Python loop work here.
The script and measurements remain preserved as negative evidence.

## Consumer costs and prepared-table specialization

`economy80-consumer-section-profile` separates generator resumption from the work
performed while each yielded route is suspended. Collision probe-inclusive fuel:
generation 42.07M, checks 37.95M, numeric dispatch 454.80M, candidate handling
88.26M, and beam selection 2.24M. Corners records 20,001 generated candidates
and checks but 20,000 evaluations, matching the expansion-limit stop point.
Numeric evaluation remains the main cost; beam selection is relatively small.

`eighty_ready_tables.py` tests one-time preparation-state checks and a duplicated
numeric path with redundant per-expression None checks removed. Original retry,
failed-preparation and dirty-consumer fallback paths remain present. A second
variant also uses the original zip traversal inside the prepared numeric path,
avoiding the adjacent-iterator transform's per-pair Python assignments. Both
research variants pass 240 contexts, 1,152 direct calls and 3,586 inline entries.
Guest measurements are running sequentially in `economy80-ready` and
`economy80-ready-zip`; neither is production-integrated yet.

Results: preparation-state specialization measures **60.057–60.058% collision
savings** with matching reports; zip traversal regresses to **58.287–58.292%**
and is rejected. Preparation-state specialization is now integrated under
`numeric-prepared-versions`. Both the preparation test and its hoisted table
binding require emitter metadata; the pass retains its original protected
fallback and limits code growth. Focused tests cover partially failed preparation,
skipped/taken arithmetic errors, empty routes, optional inputs and missing proofs.
The integrated version passes 240 public scenarios and 240 fast contexts, with
1,152 direct evaluations and 3,586 inline entries. All **243 compiler tests** pass.
`economy80-ready-integrated` measures **60.06–60.07% collision, 59.79–59.81%
corners, and 60.37–60.38% lanes**, with matching reports. All ten `fifty` guest
fixtures pass on collision/corners in `economy80-ready-guest-fifty`.

## Producer-side invariant keys

`eighty_insertion_keys.py` explores a larger producer/consumer structural change.
A private clone of the certified insertion generator computes the complete sorted
index tuple and frozenset once per inserted value, sharing those keys across all
insertion positions. Route tuples and result records retain fresh allocations.
This avoids sorting and hashing the same multiset separately for each position.
The prototype passes 240 fast contexts, 1,152 direct evaluations and 3,586 inline
entries in `economy80-insertion-keys-fast`; guest profitability is being measured
in `economy80-insertion-keys`.
Production would require generic producer invariance and nonescaping-key proofs;
the prototype's emitted-source matching is research-only.

The prototype measured **64.2049–64.2068% collision savings**, with matching
reports. Production integration is now implemented as `insertion-invariant-keys`.
The solved consumer type/effect proof certifies integer tuples and integer inserted
values; original tuple-slicing insertion loops supply positional-invariance facts.
The ordinary insertion-buffer pass preserves those facts. A late pass clones the
public generator privately and replaces only emitter-tagged multiset reductions
and proven nonobserved frozenset construction. Set sharing is rejected when its
identity, iteration order, or escaping value could be observed; multiset sharing
can still proceed. The public generator retains its signature and output type.

All **247 compiler tests** pass, including new generic-name, duplicate/negative
index, native-error retry, early callback stop, public custom-payload generator,
set identity/iteration/escape, unbuffered fallback, close/throw, and missing-proof
checks. Public and fast differential checks pass for the integrated source. A new
seven-case `eighty` guest suite exercises the actual producer specialization;
its host outputs match exactly, including signed zero, NaN/infinity, failed
preparation and index errors. Final-source host checks, all-map measurements,
the guest suite and a normal-budget collision probe are running sequentially
under `economy80-insertion-integrated*`, `economy80-insertion-guest-eighty`, and
`economy80-insertion-normal`.

Next structural research should exploit the same producer provenance to avoid
rebuilding adjacent-edge aggregates for every insertion position. Exact integer
totals/negative counts may admit local updates; order-sensitive float additions
must retain their original sequence, and arithmetic must remain after callback
checks with original failure paths. This is not yet implemented or measured.

### Completed insertion-key validation

`economy80-insertion-integrated` measures **64.18% collision, 63.53–63.54%
corners, and 64.12% lanes** with matching reports. Final-source public and explicit
fast checks pass with planner hash
`65f42d14aee3b61a8cbc260eb45220d9a89602acd6ec0a8d30646bcb181e21f6`.
All seven initial `eighty` guest fixtures pass on collision/corners.
Normal-budget collision expands **120 versus 64**, with an identical engine replay.

## Rolling private edge lists

`eighty_incremental_edges.py` measures **67.1655–67.1686% collision savings**
with matching reports and passing explicit fast checks. Instead of rebuilding
the whole private integer list at every insertion position, it updates the at
most three changed edges. The first/nonconsecutive position uses original
construction. Native min/sum and all ordered floating-point operations remain
unchanged, and indexed access stays after callback checks.

Generic integration now lives in `incremental_edges.py`. Before lowering, numeric
type and alias facts certify integer endpoints, an adjacent-pair matrix projection,
immutable snapshot sources, and a list with no aliases, later mutation or escape.
Insertion provenance supplies the actual position and a private per-group state.
The runtime guards consecutive positions and unchanged table identities/axis;
different static sequences have distinct state slots. Unsupported shapes retain
their original code. Focused tests cover negative/duplicate indices, native error
order, changing axes, skipped positions, list mutation/alias rejection and missing
contracts. The guest `eighty` suite now has ten cases including ragged, negative
and large-integer edges; host outputs match and the new pass is confirmed active.

Full compiler, final-source host checks, all-map guest measurements and the ten-case
guest suite are running sequentially under `economy80-rolling-integrated*` and
`economy80-rolling-guest-eighty`. Production profitability is not yet accepted.

A separate `eighty_group_cache.py` prototype bypasses repeated tuple-key hashing
with one reduction-cache slot per insertion group. It passes explicit fast checks
but only reaches **64.2966–64.2984% collision savings** over the insertion-key
baseline. This marginal candidate is preserved and deferred while rolling edges
receive production validation.

### Integrated rolling-edge result and invariant checks

`economy80-rolling-integrated` measures **66.69% collision, 65.51–65.53%
corners, and 66.11–66.12% lanes**, with matching reports. All **251 compiler tests**,
240 public scenarios, 240 fast contexts/1,152 direct evaluations/3,586 inline
entries, and all ten guest `eighty` fixtures pass. Final-source planner hash:
`ebd18e5f506bd2b95fc3af9044d451ba561d116bab8ee0daa0e56865cc9ca99f`.

A follow-up records emitter-owned snapshot-hoist facts and removes context checks
only for single-assignment hoisted table aliases and axis values not written by
the route loop. Changing axes retain their runtime guards. Sixteen targeted tests
pass, including an explicit stable-versus-changing-axis regression. Full compiler,
public/fast, and all-map measurements are running in `economy80-rolling-invariants*`.

That validation completed: **252 compiler tests** and both 240-scenario host checks
pass. Savings are **67.12% collision, 65.95–65.97% corners, and 66.55–66.56%
lanes**, with matching reports. Planner hash:
`39205132c6e81d526d679e8fbf1a8376196cb074fa3af1737d45aa4d1cb2ce75`.

## Rolling ordered contributions

`eighty_rolling_fold.py` is a new research-only prototype for the remaining risk
traversal. It caches prepared pairwise contributions, changes at most three values
per adjacent insertion, and performs the original sequential additions over the
updated list. Endpoint arithmetic and the addition order remain unchanged; it
does not replace the fold with compensated `sum`. The prototype passes 240 fast
contexts, 1,152 direct evaluations and 3,586 inline entries. Guest profitability
is now being measured in `economy80-rolling-fold`.

The rolling-contribution list **regressed to 65.907–65.911% collision savings**
and was rejected. A `--prefix-fold` variant reused unchanged partial sums, with
full-fold fallback for changed/zero/NaN initial accumulators. It passed 240 fast
contexts plus **25,543 bitwise evaluations across 4,000 cases**, including NaN
payloads, signed zero, skipped positions and changed initial values, but also
regressed to **65.4097–65.4100%**. Both remain research-only negative evidence.

## Bounded native compensated-sum reuse

Actual Wasm `builtin_sum` (starting disassembly line 800413) was inspected again,
including its high/low finish at lines 801318–801340. A new research-only candidate,
`eighty_compensated_cache.py`, reuses native float sums across insertion positions
only under a bounded binary-grid certificate. It keeps the first native `sum`
evaluation and the original fallback for every uncertified case.

The certificate requires CPython 3.13, exact nonnegative finite floats, at most
16 terms, common-grid maximum integer magnitude `K < 2**80`, and a finite `32*K`
upper bound. With these bounds, each error-free correction is below
`64*K/2**52` grid units and the accumulated correction magnitude is below `2**38`
units. All low-accumulator additions are therefore exact on the common grid;
native final high+low rounds the exact rational total, independently of permutation.
This does not authorize reordering an ordinary sequential float fold.

`compensated_grid_differential.py` verifies **40,392 permutations of 6,732 accepted
tables** against exact rational reference rounding, with 5,268 random tables
rejected and explicit nonfinite, negative, mixed-type, size and range rejections.
Host planner checks pass all 240 contexts, 1,152 direct evaluations and 3,586
inline entries; instrumentation observes **2,110 eligible calls and 815 cache
hits**, with unchanged source files and exact output hashes. Guest measurement
in `economy80-compensated-cache` completed at **68.8016–68.8048% collision savings**,
with matching reports.

### Wasm audit and generic integration

The exact-float branch at Wasm lines 801023–801046 computes `t = high + x`, then
selects `(high-t)+x` or `(x-t)+high` according to `abs(high) >= abs(x)`.
Lines 801080–801083 add that correction to low; lines 801318–801340 return high
when low is zero/nonfinite, otherwise high+low. These are separate binary64
operations, with no fused expression or extended accumulator. On the accepted
nonnegative grid, high stays below `32*K` units for <=16 inputs. FastTwoSum's
correction is exact; gradual underflow preserves grid multiples (the grid is at
least the minimum subnormal). Each correction is below `64*K/2**52` units, so
all low partial sums have fewer than 38 magnitude bits and are exactly representable.
Thus high+low represents the exact total until the final single rounding. All-zero
inputs produce positive zero from sum's integer-zero start; empty sums retain int 0.

`tools/bot_optimizer/compensated_sums.py` now integrates reuse under emitter-owned
native-sum/prepared-projection, single-write hoisted snapshot table, and private
insertion-group contracts. Each static site has its own private slot. Only sums
immediately consumed by numeric addition qualify, preventing shared result
identity from escaping. Failed preparation, uncertified tables, >16-term routes,
and original nonprepared paths keep their original native calculation. The runtime
certificate also checks CPython 3.13 and binary64 round-to-nearest properties.

Five focused tests pass, covering grid/size/version boundaries, native compensation,
subnormals, signed zero, negative/nonfinite inputs, duplicate/negative indices,
missing contracts, failed preparation/error paths, and explicit native-call counts:
3 instead of 9 on accepted groups, all 9 on rejected tables, and all 51 on long routes.
Integrated public/fast checks pass with **815 observed cache hits** and planner hash
`7eb82db9025b5aa0c0a74be8c250916bad54785cc72c8df1883854a6350f5692`.
Full compiler, production-grid, all-map and actual guest-fixture validation is next.

Those checks are now running sequentially in `economy80-compensated-integrated*`
and `economy80-compensated-guest-eighty`.

Completed: **257 compiler tests**, **40,392 production-grid permutations**, and
all ten guest fixtures on collision/corners pass. Integrated savings are
**68.74–68.75% collision, 67.38–67.39% corners, 67.98–67.99% lanes**, with matching
reports. The 80% target and final repeated/equal-work audit remain outstanding.

## Ordered record-population prototype

`eighty_record_batch.py` retains original numeric-record allocation and dictionary
access, then tests native `dict.update(zip(keys, values))` in place of consecutive
individual primitive stores. The sequential pair-insertion path keeps the same
key order and instance dictionary; Wasm `PyDict_MergeFromSeq2` at line 336310 was
inspected. The prototype passes 240 fast contexts, 1,152 direct calls and 3,586
inline entries, including 815 compensated-cache hits. Guest profitability is
pending after current validation. This candidate remains research-only.

Its guest measurement is now running in `economy80-record-batch`.

Completed: record batching regresses collision savings to **64.859–64.862%**,
so it is rejected. Native sequence-pair conversion and update overhead outweigh
the removed interpreted stores.

## Short ordered-fold specialization

`eighty_unrolled_fold.py` specializes prepared pairwise folds for tuple lengths
2–12. It unpacks primitive values once, preserves each sequential addition, and
keeps original code for other lengths. The prototype passes the 240-context fast
check and measures **69.396–69.401% collision savings** with matching reports.

Generic integration in `ordered_folds.py` requires a numeric-emitter-certified
single-add pair loop, prepared table provenance and a single-write hoisted table.
The adjacency pass carries the proof through lowering; only the prepared consumer
version is specialized. Final loop targets are preserved; failed preparation,
long/short tuples and native-index retry retain the old paths. Three focused tests
cover bitwise cancellation, signed zero, subnormals, nonfinite/NaN payloads,
tuple lengths around both bounds, loop-target uses, arithmetic/index errors and
missing contracts. The integrated public check passes 240 scenarios; full checks
and guest measurement are next.

## Insertion-group scalar reuse prototype

`eighty_group_scalars.py` groups multiset reductions with dependent ceiling,
maximum and reward arithmetic. First computations stay at their original points;
the private group is populated only after all invariant computations succeed.
The prototype passes 240 fast contexts and measures **69.7755–69.7762% collision
savings**, over the compensated-sum integration (before ordered-fold integration).
Generic dataflow/exception/primitive-observation proofs are required before any
production integration. This remains research-only.

### Verified ordered-fold integration

All **260 compiler tests**, 240 public scenarios and 240 fast contexts pass, with
1,152 direct evaluations, 3,586 inline entries and 815 compensated-cache hits.
All ten guest fixtures pass on collision/corners. Integrated savings are
**69.39–69.40% collision, 68.07–68.08% corners, and 68.67–68.68% lanes**, with
matching reports. Planner hash:
`b4633d6317e576c92881f199019247feeaf8e8d38fd9dd72f39f51e5cfcd67af`.

### Generic scalar integration

`group_scalars.py` now uses numeric-emitter reduction/initializer metadata and
primitive invariant dataflow. Dependencies must originate in the immutable
snapshot or the same insertion-route multiset reduction; scalar targets must be
single-write, and inference stops at control-flow joins. The pass retains first
computations at their original points and publishes private state only after the
last invariant computation succeeds. Each static site has an independent slot.

Three focused tests pass changing selectors, duplicate/negative indices, huge and
nonfinite values, original exception order, failed cache publication, missing
proofs and explicit **6 hits in 9 calls**. Public and fast planner checks pass with
**1,249 scalar-group hits in 3,197 calls**, plus 815 compensated-sum hits. Planner:
`3df111252cd44d3b5443bb39b43a065c5cc17e591a1b650c40c2c64403c9dc20`.

The first full run stopped on two insertion-key tests that assumed a fixed private
generator tuple arity. Their assertions now inspect the preserved key fields and
verify that prohibited set sharing still produces no frozenset payload, allowing
additional private state. Other tests passed. Full compiler, all-map fuel, ten
actual guest fixtures and normal-budget collision checks are rerunning sequentially
in `economy80-scalars-integrated*`, `economy80-scalars-guest-eighty`, and
`economy80-scalars-normal`. The 80% result is still unachieved.

## Consumer invariant-load research

`eighty_consumer_invariants.py` tests nonempty-route specialization for the private
insertion producer, an invariant expansion-limit load, and a per-generator
candidate-bucket lookup. It passes 240 fast contexts, 1,152 direct calls and 3,586
inline entries, including 815 compensated-cache and 1,249 scalar-group hits.
Guest profitability is pending after scalar validation. Production would require
generic snapshot/false-continuation, producer nonemptiness and private bucket
invariance/lifetime proofs. Refreshing the current consumer profile is also next.

## Next structural opportunities

### Latest measured checkpoint and unique-key integration

Scalar integration passed **263 compiler tests**, all ten guest fixtures and
all-map comparisons: **70.37% collision, 68.98–69.00% corners, 69.66% lanes**.
Normal-budget collision reaches **112 versus 64 original expansions**, with an
identical engine replay. Consumer-invariant research measures **70.8218–70.8230%**
collision savings. The refreshed profile remains dominated by numeric dispatch
(319.36M probe-inclusive fuel versus 68.22M generation and 51.03M candidates).

Native-scan certificate research passes **66,426 permutations / 11,071 accepted
tables** and preserves 815 planner cache hits; collision savings are
**70.3841–70.3846%**. Normal-budget benefit remains unmeasured.

Unique-key research measures **70.7510–70.7526% collision savings**, with exact
fast checks and **23 unique / 21 duplicate-negative** producer witnesses.
`insertion-unique-keys` is now integrated: an existing private frozenset becomes
the reduction key only when its cardinality equals the full joined tuple length.
Duplicate-containing routes retain sorted multiset keys. Public generators retain
their signatures and fresh tuple outputs. Eight targeted insertion/scalar tests
pass; all ten updated guest-fixture host observations match with both unique and
duplicate bases. Final-source host, full compiler, all-map guest, fixture and
normal-budget checks are next. The **80% target remains unachieved**.

Completed unique-key validation: **264 compiler tests**, 240 public scenarios,
240 fast contexts and all ten guest fixtures pass. Savings are **70.75% collision,
69.38–69.40% corners, 70.03–70.04% lanes**, with matching reports. The integrated
planner is byte-identical to research hash
`e91de01b1a0a081a9b600c49ffbedff7df1aca877ac0ce9ab0d4e7918f814d6a`.
Normal-budget collision remains **112 versus 64 original expansions**, with
identical engine replay. Evidence is in `economy80-unique-integrated*`,
`economy80-unique-guest-eighty`, and `economy80-unique-normal`.

* Investigate repeated traversals and native tuple guards in emitter-proven regions.
* Assess whether consumer-level inlining enables useful invariant hoisting and
  further loop fusion without changing record allocation or floating-point order.

These are research directions, not implemented or accepted performance claims.
All earlier archives and the original untracked bot remain preserved.

## Private producer fusion research

`eighty_inline_producer.py` fuses the private primitive insertion producer into its
closed consumer. Fresh route tuples and original evaluation/callback order remain;
cache metadata stays in locals instead of a seven-element yielded wrapper. A halt
flag propagates consumer breaks through the producer loops; buffer removal remains
finally-protected on continue/break. The optional `--invariants` variant additionally
reuses the fixed insertion-route length and removes proven empty-route branches.
Both variants pass 240 fast contexts with identical stop counts, 1,152 direct
evaluations, 3,586 inline entries, 815 compensated hits and 1,249 scalar hits.
Planner hashes are `41aae5fc83b9f0fce85bbe836637901821d2572a1b542b78d92cf369efeea89b`
and `bc24faafc93e61e63cb7feb5fcd1b4665eb221654e1b232f7d571da405a49c39` respectively.
Guest profitability remains pending after unique-key validation.

Actual runtime Wasm inspection locates `gen_iternext` at line 247489 and
`gen_send_ex2` at 247577. Lines 247714–247751 update generator/thread state and the
value stack; 247776 enters runtime GC accounting and 247792 calls the interpreter
frame evaluator. This motivates eliminating repeated generator transitions at the
source level while retaining the engine's unchanged accounting. Generic production
fusion still needs explicit primitive-local/lifetime, producer-effect, and nested
break/continue/exception proofs; these scripts remain research-only.

`producer_fusion_differential.py` additionally passes **20 fixture observations
and 36 explicit fast contexts**, exercising callback stops, exceptions, and
true-branch mutation followed by later outer-loop work. Records, error messages,
callback counts and mutations match. Both guest-fuel experiments are running
sequentially in `economy80-inline-producer` and
`economy80-inline-producer-invariants`.

Completed research measurements: **71.51996–71.52022% collision savings** for plain
fusion and **71.95063–71.95273%** with fixed-length/nonempty invariants, with
matching reports.

### Generic producer fusion integration

`producer_fusion.py` requires source-emitter certification of a two-level primitive
range/insertion generator with only an optional membership skip. Bounds use checked
integer parameters or literals; extra/default arguments and other producer effects
are rejected. Exact buffer branches and reusable length calls carry emitter metadata.
The late pass checks global/local capture and consumer rebinding before fusing
private metadata locals, fresh route tuples and finally-protected buffer cleanup.
Consumer breaks propagate through the producer loop; nested consumer loops keep
their own break/continue semantics. The original public generator remains intact.

Three focused tests pass empty/duplicate/negative bases, count bounds, buffer and
non-hoisted fallbacks, nested control, early return, callback throws and true-branch
mutation, fresh route identity, and missing/unsafe proofs. Integrated public240 and
fast240 checks pass with unchanged hashes and 815 compensated / 1,249 scalar hits.
Planner: `5d7a5ef1fbac0cb75a1a51d2a0f47d6866e96c448867be97111c1a22638efbbe`.
Full compiler, production semantic witnesses, all-map guest fuel, ten guest fixtures
and normal-budget collision are running in `economy80-fusion-integrated*`,
`economy80-fusion-guest-eighty`, and `economy80-fusion-normal`.

## Fused cache scalar replacement research

`eighty_fused_slots.py` removes private fixed-size cache-slot lists after producer
fusion, replacing constant-index accesses with locals. Its `--resident-scalars`
variant also tests retaining already-computed invariant outputs directly in the
fused frame, replacing tuple publication/unpacking with a ready flag. The latter
checks that all output writes are inside cache computations and that the shared
prepared/nonprepared selector has a single assignment outside the loops.

Both variants pass 240 fast contexts with unchanged records, stop counts and cache
hit counts. Planner hashes: slot-only
`4d0728efae71edce598585639b3140032c0f1c10a1bc88ceaef3bd7efc2f38a8`, resident
`c20c37996a5ec21352805579ef7f56ffc6bb51bc599e351d970a8f52a39c2985`.
Guest profitability is pending after fusion validation. These remain research
transforms; generic integration needs emitter-owned cache provenance and invariant
output-write/branch-selection proofs.

Fusion integration completed all checks: **267 compiler tests**, ten production
semantic fixtures plus 18 explicit fast callback contexts, and all ten guest
fixtures. Savings: **71.95% collision, 70.66–70.68% corners, 71.31–71.32% lanes**.
Normal-budget collision reaches **120 versus 64 original expansions**, with an
identical engine replay.

Cache research completed at **72.5713–72.5729% collision savings** for scalar slots
and **72.89708–72.89717%** with resident outputs. Both also pass ten fixture
observations and 18 explicit stop/throw/true-mutation contexts.

### Generic fused-cache integration

`fused_caches.py` now requires emitter-owned private-cache and fused-consumer
provenance, checking all slot references for constant in-range indices and no
alias escape. Resident-output reuse requires cache read/miss/publication metadata,
a common immutable prepared-version selector with one site per branch, every
output write confined to cache computations, and no observable state/flag uses.
Six targeted cache/group tests pass, including perturbed selectors, extra output
writes, observed state, aliasing, dynamic indices and missing source contracts.

Integrated public240 and fast240 checks pass with the original observation hashes,
815 compensated hits and 1,249 scalar hits. Planner hash:
`8c28d08660eb7a24e5d93176e8eae72aea5a9e9e85e1eb6211a8bb252f1c070f`.
Full compiler, production semantic checks, all-map guest fuel, ten guest fixtures
and normal-budget collision are running in `economy80-cache-integrated*`,
`economy80-cache-guest-eighty`, and `economy80-cache-normal`. **80% remains unachieved.**

## Resident rolling-edge research

`eighty_resident_edges.py` keeps the private rolling edge list in its fused local,
using only the last insertion position as cache state. It checks immutable prepared
version selection and all list rebindings, retaining skip/nonconsecutive rebuilds.
The prototype passes 240 fast contexts with unchanged records/stop counts and
815 compensated / 1,249 scalar hits. Planner:
`0d5f299ebcdaaee525f17b89735fc83ceb9da115ac05b6e1cb78a266ecec15f5`.
Guest profitability and generic integration remain pending after cache validation.

Cache integration completed **270 compiler tests**, public240/fast240, ten semantic
fixtures plus 18 callback contexts, and all ten guest fixtures. Savings are
**72.89% collision, 71.76–71.78% corners, 72.42% lanes**. Normal-budget collision
reaches **128 versus 64 original expansions**, with identical replay.

Post-optimization profiling (`section_profile.py --fused-sections`) preserves the
final emitted structure before inserting probes. Collision probe-inclusive fuel:
edges **67.18M**, totals **42.38M**, timing **60.08M**, risk **107.55M**, record
**94.18M** across 6,020 evaluations. Corners has 20,000 evaluations, with risk
335.86M and record 310.36M. Risk and record construction are now the largest
measured numeric sections; instrumented totals are not savings claims.

Resident-edge research completed at **73.16856–73.16888% collision savings**.
Ten stable-selector fixtures and 18 explicit callback contexts also match. Generic
integration now requires emitter edge-cache provenance, scalar cache locals,
absence of additional context guards, immutable prepared dispatch, all list
rebindings inside edge computations, and complete state/cache-use validation.
Four focused cache tests pass, including changing-axis fallback and nonconsecutive
skip/error cases. All ten updated fixture host observations match with the pass
active. Full validation is running in `economy80-resident-edge-integrated*`,
`economy80-resident-edge-guest-eighty`, and `economy80-resident-edge-normal`.

## Exact-mapping record-store research

`eighty_record_batch.py --mapping` tests dictionary-literal/native-dictionary merge
instead of the rejected zip-pair update. Record allocation and original dictionary
access stay at their original points. The prototype passes 240 fast contexts;
planner `3fb5a2b7170fc249e754228cfff0ed6474782c6936460b7f038edca83934cdea`.
`record_mapping_differential.py` passes **656** prior-class-key/instance-count/
field-width cases with identical field order and later field-finalizer order.

CPython 3.13.11 `dict_dict_merge` was reviewed against the actual Wasm: lines
337372–337381 prevent the clone shortcut for split target dictionaries;
337506–337555 resize only when full table capacity is insufficient. The class-key
allocator at 344893 stores `0x0606`, giving 64 buckets and usable capacity 42.
Thus the research bound of at most 16 fields avoids bulk-resize for split tables;
ordered insertion remains the key-history requirement. Runtime/layout and generic
emitter proofs are still pending. Guest profitability will be measured after
resident-edge validation. This candidate remains research-only.

## Resident-edge validation and rejected native operations

Resident-edge integration completed **271 compiler tests**, 240 public scenarios,
240 fast contexts, ten semantic fixtures plus 18 callback/error contexts, and all
ten actual guest fixtures. Savings are **73.1686–73.1689% collision,
72.0590–72.0726% corners, 72.7106–72.7157% lanes**, with matching reports.
Normal-budget collision remains **128 versus 64 original expansions**, with an
identical engine replay. Planner hash:
`0d5f299ebcdaaee525f17b89735fc83ceb9da115ac05b6e1cb78a266ecec15f5`.
Final repeated/equal-work and reproducibility audits remain pending.

Exact-mapping batching regressed collision savings to **69.6355–69.6377%** despite
passing planner and 656 shared-key/finalizer cases. Native ordered
`functools.reduce(operator.add, ...)` also regressed to **71.3947–71.3951%**.
Both experiments are rejected; results are archived in `economy80-record-mapping`
and `economy80-native-fold`.

## Adjacent-insertion rolling prefix research

`eighty_rolling_prefix.py` retains one ordered prefix scalar across adjacent
interior insertion positions. Interior endpoints are fixed, and the reusable
prefix grows by one base edge. Publication follows successful completion of the
fold; nonconsecutive positions recompute their prefix and endpoint positions use
the full fold. This remains a research transform requiring generic producer,
immutable-table, endpoint, and publication proofs before integration.

The candidate passes 240 fast contexts with unchanged observation and cache-hit
counts, ten semantic fixtures plus 18 explicit callback/error contexts, and
**38,730 bitwise comparisons across 6,000 cases**, exercising **21,196 prefix
hits**, skipped positions, duplicate/negative indices, endpoint changes, signed
zero, infinities and NaN payloads. Planner hash:
`a892175c90502d06794f4a1f2503bd82030bdce6c9c1a468fbd4dd7ffc4a9675`.
Guest profitability is running in `economy80-rolling-prefix`. **80% remains
unachieved.**

Rolling-prefix guest measurement completed at **72.8261–72.8266% collision
savings**, below resident-edge production; the candidate is rejected.

## Exact insertion-edge algebra

`eighty_edge_algebra.py` lazily computes the base route's integer tour total at
the original evaluation point, then derives each insertion total by replacing one
edge or endpoint. Certified nonnegative immutable tables and valid integer indices
allow removal of private edge-list construction, updates and scans. Uncertified
tables and invalid indices retain original code. No float reassociation is used.

Research savings: **76.0409–76.0419% collision, 74.9992–75.0153% corners,
75.6440–75.6475% lanes**, with matching reports. Fast240 checks retain the original
observation hash and 815 compensated / 1,249 scalar hits. The actual emitted edge
block also passes **76,678 comparisons across 4,000 cases**, including **44,680
algebra evaluations**, skipped positions, duplicate/negative indices, empty bases,
ragged and negative tables, huge integers and out-of-range errors. Research planner:
`ed95fb344ad38c874a9adfa5419fd3a788826a02c12483cb3d791735d32dfdce`.

### Generic integration

`edge_algebra.py` consumes emitter-owned fused-insertion and integer-edge
contracts. It requires single-write hoisted snapshot tables, invariant selection
axis, a prepared-version edge site, intact edge-construction metadata, and only
certified sums, first-edge reads and negative-edge rejection uses. A bounded
runtime certificate checks exact integer tuple tables, dimensions and nonnegative
entries, with at most 4,096 scanned entries. Per-base checks retain invalid-index
fallbacks; the base total is lazy and reset for each fused base-route traversal.
The remaining original rejection predicates are still evaluated.

Three focused tests pass duplicate/negative/empty bases, skipped positions,
ragged/negative/huge tables and errors, certificate limits, disabled passes,
changing axes, observed list reads, table rebinding and missing emitter proofs.
Integrated public240 and fast240 checks pass, plus ten semantic fixtures and
18 explicit callback/error contexts. Planner:
`c565c371f2284c1f5a318de87ed18f52dd0afb37e450c411facc6a546f715e9e`.
Full compiler, all-map guest fuel, ten actual guest fixtures and normal-budget
collision validation are running in `economy80-algebra-integrated`,
`economy80-algebra-guest-eighty`, and `economy80-algebra-normal`.
**80% remains unachieved; final repeated/equal-work and provenance audits remain.**

Integrated algebra validation completed **274 compiler tests** and all ten guest
fixtures. Savings: **75.77–75.78% collision, 74.73–74.74% corners, 75.37% lanes**,
with matching reports. Normal-budget collision is **120 versus 64 original
expansions**, with an identical replay, but below the preceding integration's 128.
The extra certificate setup is a measured normal-budget concern, not a semantic
mismatch. Evidence: `economy80-algebra-integrated`, `economy80-algebra-guest-eighty`,
and `economy80-algebra-normal`.

## Base-prefix reuse and certificate setup research

`eighty_base_prefix.py` tests sharing ordered risk prefixes across all insertions
of one base route, using binary position dispatch. The initial unkeyed version
passed economy checks but failed a semantic fixture whose initial accumulator
depends on the inserted item. It was corrected to key prefixes by the initial
float value, distinguishing signed zero and rebuilding for NaNs. The corrected
candidate passes public fast240, ten fixtures/18 callback contexts, and **114,096
bitwise evaluations**, including changing initial values and **50,253 cache hits**.
Nevertheless it regressed collision savings to **75.3519–75.3527%** and is rejected.
Artifacts preserve both the failed unkeyed witness and corrected keyed results.

`eighty_edge_certificate.py` now tests replacing per-element Python checks with
native row minima for already-validated integer snapshots. The research transform
passes fast240 with unchanged observations/cache hits; planner hash:
`cd5702d9776e1a16de48d483dd8257cd14d3070b5157942260749b71bad79a70`.
High-work and normal-budget collision measurements are running sequentially in
`economy80-edge-native-certificate` and `economy80-edge-native-certificate-normal`.
Generic integration still needs explicit source-integer/snapshot provenance; this
candidate remains research-only.

Native edge-certificate research completed at **75.81746–75.81751% collision
savings**, and normal-budget collision recovered to **136 versus 64 original
expansions**, with an identical replay. This removes the earlier 120-expansion
setup regression.

The generic `insertion-edge-native-certificate` pass now requires an additional
source-emitter contract: both endpoint and pair lookups return checked integers
from homogeneous sequence rows. Combined with the existing immutable snapshot
and single-write proofs, this permits native minima for nonnegative validation.
Missing proofs keep full per-element type checks; dimensions and the 4,096-entry
bound remain enforced. Three focused algebra tests pass, including absent proof,
disabled native certificate and invalid certificate inputs. Integrated public240
and fast240 checks match with unchanged cache hits; planner hash:
`619e7621bcfaa6b79ed9072fddaf6721d085466d0c5a544cd2e58b71991372ee`.
Full compiler, semantic witnesses, all-map guest fuel, guest fixtures,
normal-budget collision and a refreshed final-code profile are running under
`economy80-native-edge-cert-*`. **80% remains unachieved.**

Native certificate integration completed **274 compiler tests**, ten semantic
fixtures/18 callback contexts, all ten actual guest fixtures and all-map fuel
checks. Savings: **75.82% collision, 74.75–74.76% corners, 75.39–75.40% lanes**.
Normal-budget collision reaches **136 versus 64 original expansions**, with an
identical replay. Refreshed collision probe-inclusive numeric costs across 6,020
evaluations: edges **57.76M**, totals **42.38M**, timing **48.78M**, risk **107.56M**,
record **94.19M**. Risk and record construction remain dominant.

## Rejected score-bound pruning research

`eighty_score_pruning.py` tested skipping total risk arithmetic for provably losing
private records while retaining fresh object allocation and all original field
stores, preserving shared-key history. A simple base-score upper bound passed
fast240 but regressed collision savings to **73.4526–73.4552%**.

The stronger `--risk-bound --certified-domain` experiment uses nonnegative bounded
integer durations, risks/tolerance in [0,1], at most 16 terms and a conservative
`2**-40` floating-point error margin. The bound passed **20,000** generated-domain
checks. Its first guest run exposed a downstream comparison bug: the skipped
record retained base score instead of its tighter bound and could be promoted.
The corrected version stores the proven losing bound, passes fast240 and **96
additional domain-rich planner scenarios** with equal records, stable ties,
callbacks, errors and mutation. Nonetheless it regressed collision savings to
**73.2615–73.2618%**, so both variants are rejected. No pruning is integrated.
Failed and corrected artifacts remain archived under `economy80-score-domain*`.

## Actual guest snapshot capture

`snapshot_profile.py` captures the private numeric snapshot at consumer entry for
host analysis of actual map risk tables and additional realistic differential
scenarios. It reports binary-grid widths and exact-addition eligibility, not fuel
savings. Collision/corners/lanes capture is running in
`economy80-native-edge-cert-snapshots`; further exact arithmetic opportunities will
be selected from those values. **80% and final repeated-work/provenance audits
remain outstanding.**

Snapshot capture completed for both teams on all three maps. Pair-risk tables
contain 400/576/576 values and require **58 scaled significant bits** on every map;
the 16-term exact-addition certificate fails. Thus ordinary reassociation of these
ordered sums is not justified. Raw risks and service-risk terms also fail the
53-bit exact-addition bound. The six snapshots and their hashes are archived for
further realistic host checks.

`itertools.accumulate` research passed fast240 but regressed collision savings to
**72.7139–72.7151%**, so it is rejected. Actual runtime Wasm
`accumulate_next` at line 1668236 directly calls `PyNumber_Add` at 1668351 when no
callback is supplied, but its iterator/list overhead still loses guest fuel.

`eighty_native_fold.py --generic-sum` now tests CPython's generic sequential sum
loop using a private, slotless float-subclass initial value with no overridden
arithmetic. This bypasses the exact-float compensated path; the first addition
produces an exact float, and the generic loop continues sequentially. Actual
runtime Wasm checks exact float type at 800969–800972, and its generic addition
path calls `PyNumber_Add` at 801382. The candidate passes fast240 and **20,000
bitwise emitted-fold comparisons**, including NaN payloads, signed zero, infinities
and exact float result types. Planner:
`d400deaed1079278e4133780d84a54dfaccf398d1ee9ffa1c7b92651c9bc8eb6`.
Guest profitability is running in `economy80-generic-sum`. Runtime/lifetime proofs
and actual guest edge cases remain prerequisites for any integration.

## Losing-record field-store research

`eighty_losing_stores.py` keeps every original result allocation and `__dict__`
materialization, then omits the twelve field stores only when a live previous
same-type winner already exists and the computed exact score cannot replace it.
The original downstream comparison uses that same decision; losing skeletons
remain private. This differs from rejected allocation deferral: allocation order
and count are retained, as are dictionary creation and the first full record's
field insertion order.

The prototype passes fast240 and 96 domain-rich planner scenarios with unchanged
records, ties, callbacks and mutation. All original cache-hit counts remain.
`losing_store_differential.py` passes **1,968** prior-key/instance-count/field-width/
loser-count cases with equal later key growth, deletion/reinsertion and field
finalizer order. Planner:
`2733420bf4ab8426e4a70e82618afea26d9f47500cde2d200623350284293d35`.

Actual Wasm `_PyObject_InitInlineValues` (344958) decrements shared-key capacity
at 344974–344979, explaining why allocation count must remain intact.
`insert_split_key` returns existing-key lookups at 332193–332197 and rejects
missing keys at exhausted capacity at 332200–332206. A fully populated previous
record therefore supplies a potential monotone-key-history proof, but generic
same-type, complete-store, nonescape, comparison and lifetime proofs remain
pending. Guest profitability follows the running generic-sum measurement.

Generic sequential sum completed at **74.3183–74.3196% collision savings** and is
rejected. Losing stores initially reached **77.1107–77.1116% collision**. Audit
found an unnecessary retained previous-record alias; the corrected prototype
deletes that alias immediately after its exact comparison. It passes fast240 and
rich96 again, with planner hash
`8540619341f5fb21ce63cc68a42221d22de718b836fd53dd3777d1cca29f8476`.
Corrected all-map savings are **77.0936–77.0954% collision,
75.8112–75.8350% corners, 76.2582–76.2613% lanes**, with matching reports.

### Generic losing-store integration

`tools/bot_optimizer/losing_stores.py` certifies the source selection suffix using
the solved consumer type/effect proof. It requires a numeric result with all
declared primitive fields, no other result uses, an exact strict comparison, and
publication only through the winning branch. The previous result must be the
same complete record type. Fresh empty bucket origins and no bucket aliases are
also required: type equality alone is insufficient because a borrowed object's
combined dictionary might never have populated its class's shared keys.

The late pass requires fused producer, prepared inlined evaluator, an existing
insertion key, intact allocation metadata, complete ordered field stores, exact
record/dictionary use counts, and the intact selection suffix. It preserves
allocation and dictionary creation, releases its temporary previous alias
immediately, and uses the exact early comparison downstream. Original fallbacks
remain fully populated. A first winner always receives every field store. With
the same allocation count and no intervening user mutation, later stores cannot
add shared keys that the complete winner did not already add: exhausted capacity
cannot grow again. Only discarded private instance dictionaries lose entries.

Focused tests pass actual losing-store hits, stable ties, NaNs/infinities, missing
and perturbed emitter proofs, observed result aliases, prepopulated/aliased
buckets, disabled dependencies and fallback errors. Integrated public240,
fast240, rich96, ten semantic fixtures and 18 callback/error contexts match.
Planner hash:
`69498b65535420083414dcd6d27ca2fbeb0fd80cad5612fef77496dd6cf4f370`.
The stricter fresh-bucket proof reproduces this source byte-for-byte.

Full compiler tests, all-map guest measurements, the new ten-case `losing` guest
suite (confirmed to emit this pass), the existing ten-case `eighty` suite, and
normal-budget collision are running sequentially under `economy80-losing-*`.
**80% remains unachieved; final repeated/equal-work/provenance audits remain.**

Losing-store integration completed **282 compiler tests**, both ten-case guest
suites, and all-map fuel checks: **77.09% collision, 75.81–75.83% corners,
76.26% lanes**. Normal-budget collision remains **136 versus 64 original
expansions**, with an identical replay.

## Width dispatch outside the insertion group

`eighty_width_dispatch.py` duplicates the fused producer for widths 2–12 and
selects the matching ordered fold once per base route. The numeric addition order,
fresh tuple and record allocation, callbacks, exceptions and fallback stay intact.
Research passes fast240/rich96 with unchanged counts and improves guest savings
to **77.6952–77.6966% collision, 76.3427–76.3665% corners,
76.7915–76.7954% lanes** with matching reports.

Generic `insertion-width-dispatch` consumes emitter-owned fused-size and ordered
width-chain contracts, requires single-write sizes and an intact comparison chain,
and caps expanded AST size at 100,000 nodes. Generic output is byte-identical to
the measured research planner:
`c02d8a5d452179badd649765ff8f2ea43996122ca17c52c898898c40d65da963`.
Focused tests cover widths 1, 2, 3, 11, 12 and 13, all ten guest fixture shapes,
disabled dependencies, changed bindings/comparisons, missing contracts and code
growth limits. Public240, fast240, rich96, ten semantic fixtures and 18 callback
contexts match. Full compiler, both guest suites and normal-budget collision
validation are running under `economy80-width-*`.

Actual snapshot route-reuse analysis found only **211/6,020 collision** and
**414/20,000 corners / 421/20,000 lanes** hits for a bounded 4,096-entry full-route
cache. This is insufficient to justify full-result caching overhead as the next
candidate; no such cache is integrated. Counts and inputs are reproducible through
`route_reuse_profile.py` and `economy80-route-reuse-profile/results.json`.

## Direct fresh-route tuple research

`eighty_direct_routes.py` uses width-specialized base scalars and balanced insertion
position dispatch to construct each fresh route tuple directly. It removes the
private list insert/copy/delete roundtrip, retaining original fallback and
callback/evaluation ordering. The prototype passes fast240 and rich96 with all
original numeric/cache counts. Planner:
`096cd85beff3febc69c0c89f86087db5ea81ff5ccdfb71cd5e6a2e7301cc66cf`.
Guest measurement is pending the sequential width-validation batch. Generic
buffer-nonescape, exact-tuple, route-identity and protected-control-flow proofs are
required before integration. **80% remains unachieved.**

Width integration completed **284 compiler tests**, both ten-case guest suites
and normal-budget collision (**136 versus 64 expansions**, identical replay).
`economy80-width-reproduction` verifies all 20 Python sources match both measured
research archives byte-for-byte and preserves the unchanged original fingerprint.

Direct tuple research completed at **77.8681–77.8705% collision,
76.5751–76.5989% corners, 77.0248–77.0266% lanes**, with matching reports.
It also passed **77,000 actual emitted route factories**, checking exact route
contents, fresh tuple identity and unchanged element identities, plus ten fixture
observations and 18 callback/error contexts.

## Bounded position unrolling

`eighty_direct_routes.py --unroll` replaces each width-specialized position loop
with constant positions. One-iteration loops preserve source `continue`; the
fusion emitter's halt flag propagates source `break` out of the surrounding item
loop. Exact integer positions/widths permit branch and addition/subtraction
folding. Float arithmetic remains unchanged.

Research savings: **78.1831–78.1840% collision, 76.9919–77.0167% corners,
77.4511–77.4548% lanes**, with matching reports. Normal collision remains **136
versus 64 expansions**, identical replay. Fast240/rich96 and ten fixtures/18
callback contexts match with unchanged counts. Generated planner size is
**2,281,023 bytes**; hash:
`ea7a5b3a2ee9ce843d641ff9da0c48f3029cbc70a3faa863c1ebe7c4505ed487`.

### Generic integration and current validation

`direct_routes.py` requires emitter-owned width and native tuple/range/len
contracts, exact insert/copy/delete shapes and complete private-buffer use checks.
The outer buffer allocation and cleanup remain intact. `unroll_positions.py`
requires emitter-owned direct positions/halt state, no position/size rebinding,
and explicit halt publication before every escaping break. Nested loop bodies
retain their breaks; handlers and loop-else regions are checked at the correct
control-flow boundary. Projected function expansion is capped at **262,144 AST
nodes** before copying, with all-or-none acceptance for one consumer.

Focused boundary, fallback, disabled-pass, changed-native-call, buffer escape,
cleanup, break/handler/loop-else, rebinding and growth-limit checks pass. Direct
integration passes the 77,000 tuple identity checks. Both integrations pass
public240, fast240, rich96 and ten semantic fixtures/18 callback contexts. Latest
unrolled planner:
`a28e8f3289f7f57e1c4b6852cdb251ecf1934c9337abf852ab4f9ace7c1efd47`.
Full compiler, all-map guest measurements, both guest suites and normal-budget
collision validation are running sequentially under `economy80-unrolled-*`.
**80% remains unachieved; final repeated equal-work, raised-work, all-map normal
budget and source/runtime-accounting/provenance audits remain pending.**

## Separate losing-dictionary research

`eighty_losing_dicts.py` tests omitting dictionary materialization only for private
losing records while keeping each record allocation. This is separate from the
integrated store pass, which still materializes every dictionary. It passes
fast240/rich96 and **1,968 future-key/finalizer witnesses**, with unchanged numeric
cache counts. Planner:
`6bd3e612c3bad6c7560db5c57b4952c545ff941252e9a992f94e30eeb83c23b6`.
Actual Wasm `make_dict_from_instance_attributes` at 345137 increments the shared
key reference count, scans values, allocates a dictionary, assigns its version
and possibly links GC state; it does not perform the allocation-time shared-key
capacity decrement. These observations motivate the experiment but do not yet
prove managed-dictionary, GC or lifetime equivalence. Guest profitability is
now measured at **78.7002–78.7013% collision savings**, with matching reports.
Other-map measurement and managed-dictionary/GC/lifetime proofs remain pending.
No dictionary omission is integrated.

Unrolled production validation completed: **288 compiler tests**, both ten-case
guest suites, and matching all-map reports. Savings are **78.18% collision,
76.99–77.02% corners, 77.45–77.46% lanes**. Normal-budget collision remains
**136 versus 64 original expansions**, with identical engine replay. The final
repeated equal-work and provenance audits remain outstanding.

Dictionary omission completed other maps at **77.4498–77.4754% corners** and
**77.8812–77.8853% lanes**. It remains research-only: shared-key witnesses do not
establish GC equivalence. Actual Wasm `_PyObject_GC_New` at 934927 calls `gc_alloc`
at 935016; allocation participates in collection scheduling, so preserving record
allocation alone is not a complete proof for removing dictionary allocation.

## Base-edge scalars after position unrolling

`eighty_base_edges.py --cache` forwards constant route indices and ordered-unpack
locals from the already-created direct tuple, then lazily caches base-only pair
table values in scalars reset for each base traversal. The first lookup stays at
its original use; all floating additions remain in order. This avoids repeated
unpacking and nested table indexing without omitting record dictionaries.

Research passes fast240/rich96 with unchanged counts. Planner:
`779a1ca56da92dd77fce35cff54cec9c02890b87b8cb2dc212f3be7661ec3da9`.
Savings: **79.5279–79.5286% collision, 78.2705–78.2939% corners,
78.7315–78.7353% lanes**, with matching reports.

`--prefix` additionally caches the unchanged leading sequential sum for each
interior insertion position. End insertions retain their original calculation;
their initial boundary contributions can depend on the inserted item. Caches
are lazy and local to one base, eliminating the dictionary/key overhead of the
earlier rejected generic prefix experiment. Host fast240/rich96 match, plus
**194,928 actual emitted bitwise fold/error comparisons**, including **23,559
index errors**, nonconsecutive positions, changing inserted items, negative and
duplicate indices, signed zeros, infinities and NaN payloads. Planner:
`5cbfe74198636072c3c756e7f1a1c1019af7385a8629476c2ef743921bb60120`.
Savings: **80.0389% collision, 78.6874–78.7107% corners,
79.1523–79.1554% lanes**, with matching reports. This crosses 80% on collision
only; the overall target remains unmet.

Generic `insertion-base-edge-scalars` is drafted with emitter-owned direct-base,
direct-tuple, unrolled-position and ordered-fold contracts. It requires immutable
hoisted table provenance, no base/item/route rebinding, intact ordered-unpack and
update blocks, and no outside uses of removed aliases. It preserves the original
fallback. Focused validation is running; prefix reuse is still research-only.

Base-edge focused tests passed, followed by public240/fast240/rich96 and ten
semantic fixtures/18 callback contexts. The generic prefix pass is now integrated
as `insertion-base-prefix-scalars`. It requires derived-table numeric result and
integer-index contracts, complete base-invariant lookup dependencies, immutable
per-base slots, unchanged slot writes and an interior position. It rejects
inserted-item-dependent initial accumulators. First-use arithmetic stays intact;
cache hits retain the otherwise skipped integer housekeeping assignments.

Prefix-focused tests pass generic widths, all guest fixture shapes, disabled
dependencies and perturbed lookup/index/cache proofs. Integrated fast240/rich96,
ten semantic fixtures/18 callbacks, and the **194,928 bitwise/error comparisons**
match, with unchanged evaluator/cache counts. Planner:
`92d064c50bff953282734612a43f55bd93cafc51193dbfc89996ae63cd51c116`.
Full compiler, public240, all-map guest measurements, a new ten-case `prefix`
guest suite plus `losing`/`eighty`, and normal collision validation are running
sequentially under `economy80-base-prefix-*`.

## Next integer-reduction experiment

Actual snapshot profiling found adjacent repeated timing inputs in only
**122/6,020 collision, 404/20,000 corners and 1,900/20,000 lanes** evaluations.
The timing cache is not implemented; `economy80-timing-reuse-profile` preserves
the evidence.

The edge/prefix production batch completed **292 compiler tests**, public240,
all three ten-case guest suites and matching all-map reports. Integrated savings
are **80.02% collision, 78.67–78.69% corners, 79.13% lanes**. Normal-budget
collision improves to **144 versus 64 original expansions**, with identical
engine replay. The integer-reduction guest experiment is now running under
`economy80-base-integer-totals`.

`eighty_base_totals.py` instead tests lazy base-local exact integer sums and a
maximum, adding one inserted contribution on existing multiset-cache misses.
It retains that cache's original lookup/publication, the reduction-loop final
locals and invalid-index fallback. Bounds/length guards precede the alternative;
all floating arithmetic and dictionary/record allocations remain unchanged.
Fast240/rich96 pass with unchanged cache/evaluation counts. Research planner:
`39a3bb0f1cc07252e7b9042eaac604b1a642a241e1846b1ad05ff2da445b2701`.
Guest profitability and generic integer-reduction/dependency proofs are pending
the current sequential integration-validation batch. No base-total algebra is
integrated.

The base-total prototype also passes **66,000 actual emitted reduction-block
comparisons**, including **29,352 index errors**. These compare exact sums and
maxima, partial accumulator values on failure, and final loop locals across
large/negative integers, duplicate/negative indices, mismatched peak-table lengths
and changing inserted items. Evidence: `economy80-base-integer-totals-blocks`.

Integer-total research completed at **80.4554–80.4562% collision,
79.0156–79.0329% corners, 79.2152–79.2187% lanes**, with matching reports.
Generic `insertion-base-integer-totals` now consumes emitter-owned exact-integer
field/extremum contracts, immutable snapshot roots and intact reduction/cache
shapes. It requires the verified nonempty width branch, unchanged zero/None
initializers and output write counts, and bounds/length guards. Original cache
lookup/publication and invalid-index loops remain. It preserves final reduction
locals and supports both integer minima and maxima.

The two focused tests pass (138.356 seconds), along with public240, fast240,
rich96, ten semantic fixtures/18 callback contexts and all **66,000 emitted-block
comparisons**. Planner:
`2749db223dba29943623a76e313afd6cab0129d5153bbe907fa705b315b986cb`.
Full generic compiler/guest validation remains pending.

`eighty_base_totals.py --wait-term` separately tests reusing the group-invariant
risk product when the integer maximum selected active time itself. In that case
the original integer expression `(tribute + period - active)` equals `tribute`
exactly. The floating multiplication remains unchanged on first use; other cases
retain the original expression. It passes fast240/rich96 with unchanged counts.
Planner: `ee0021961336fd4118fc6128d73e30de32ba24cfe8625f0b838aa32e1a17063d`.
Research savings are **80.6598–80.6604% collision, 79.2649–79.2832% corners,
79.3752–79.3789% lanes**. Generic cancellation/invariance proofs remain pending.

`eighty_lookup_reuse.py` tests removing the second unchanged private-bucket lookup
on top of the integer/no-wait research build. It retains the early previous-record
alias only while the bucket owns it, transfers to the original previous binding
at its original point, and releases the temporary in `finally` before publication
or on errors/continues. Fast240/rich96 pass; planner:
`627f8589ca57a409dd10a0291f5639c96e82cde67bc3d4fd8e462502e5623653`.
Collision measurement is running. Generic nonmutation/lifetime proofs are still
required. **The all-map 80% target remains unmet.**

Lookup reuse measured **80.8726–80.8729% collision, 79.4520–79.4695% corners,
79.5626–79.5654% lanes**, with matching reports.

`eighty_dead_slots.py` now tests removing **286 dead primitive alias/constant
assignments** after route forwarding, on top of the integer/no-wait/lookup
research build. Values are restricted to the direct route's exact-integer scalar
names, primitive constants and tuples thereof. It removes no calls or indexed
reads. Fast240/rich96 pass with unchanged counts; planner:
`0ffb1810cc93a0ef60c73d4ab471892a3193a8ef00677f8187eb041afae03612`.
Collision guest measurement is running. Generic private-local provenance,
definite-binding and liveness proofs remain required before integration.

Dead-slot research completed at **81.0692–81.0704% collision,
79.6612–79.6802% corners, 79.7766–79.7797% lanes**, with matching reports.
The integer-grid compensated-sum experiment passed fast240/rich96 and **78,436
bitwise comparisons**, but regressed collision to **80.9462–80.9472%**. It is
rejected and remains unintegrated.

`eighty_integer_edges.py` retains endpoint/adjacent integer edge values already
read by the lazy base-total calculation. On top of the totals/no-wait/lookup/dead
pipeline it passes fast240/rich96 and measures **81.3787–81.3806% collision,
79.9914–80.0092% corners, 80.1051–80.1085% lanes**. Reports match. Planner:
`974b997b9e8576fa17703b91da82a2d935be3fec7c929807c46e33665c64ff92`.
The corners-a result remains below 80%; repeated final evidence is outstanding.

Generic `insertion-cancelled-products` is integrated using numeric-emitter
integer-cancellation and resident-scalar contracts, invariant snapshot factor
provenance, stable selector bindings and original multiplication timing. Two
focused tests, public240/fast240/rich96 and callback witnesses pass. Planner:
`0ad4515612674aaf75e4f1adc26126c3d22a062588dcba6622707a45f521b5aa`.
Full compiler/guest validation remains pending for accumulated integrations.

`losing-record-lookup-reuse` is now drafted directly inside the existing solved
fresh-bucket/selection proof. The temporary previous-record alias remains owned
by the unchanged private bucket and is released in `finally` before publication
or on early exit. Integration validation is pending.

Lookup reuse and generic `insertion-retained-integer-edges` pass fast240/rich96
and callback witnesses together (planner
`10e5c1e47cd805c4ee0627502f99a4e561d2c7ccd33368247b474c5a08e1cce4`).
The retained-edge pass checks the whole original arithmetic block, immutable
roots, direct-base/position contracts, the unchanged certificate/bounds guard,
and lazy-total resets before the width dispatch. Its first focused run exposed
an overly narrow reset check (resets live before the whole width chain rather
than within each arm); that check was corrected before the full validation run.

Generic `numeric-dead-primitive-slots` now removes all **286** research stores.
It requires emitter-private locals, exact-int binding metadata on every write,
no uses outside numeric dispatch arms, and definite binding independently in
every prepared/fallback arm. Removed expressions are only direct-route integer
scalars/constants or matching flat tuple unpack assignments. Indexed reads and
possible unpacking errors cannot be removed. All-arm binding checks prevent
cross-iteration/fallback dependencies; primitive-only stores cannot release
arbitrary finalizers. Production planner:
`6af0946549a49f37aafc12156fca9fbb2b59c84e491a6b91c7611d6dd78d2b64`.

The actual retained integer-edge blocks pass **189,918 exact comparisons** of
base totals, inserted-tour totals, first edges and final pair-loop locals across
large integers, duplicate/negative indices, changing items and skipped positions.
Evidence: `economy80-retained-integer-edges-blocks`.

Full compiler/public/fast/rich/callback/all-map fuel/three guest-suite/all-map
normal-budget validation is running sequentially under `economy80-integer-slots-*`.
Research drivers disable the newly integrated passes before their historical
post-compile transformations so transformations are not applied twice.

`eighty_reduction_inits.py` is the next separate experiment: it moves four
overwritten zero/None initializers into the original integer-reduction fallback.
The guarded base-total and multiset-cache-hit paths already assign all outputs.
It passes fast240/rich96 and **66,000 emitted-block comparisons**, including
**29,352 index errors** with equal partial outputs/final locals. Planner:
`33a7a6808e4b4204941ad3e3c244a37a3ccb3cee440bf562c3174f682f449aae`.
Guest measurement awaits the production validation batch; generic integration
still needs cache-provenance and definite-assignment proofs.

The combined production batch completed: **302 serial test instances passed in
1,881.784 seconds**, and the user-requested parallel rerun passed **297 unique
tests in 754.9 seconds** (about **2.49x faster**, five duplicate imported cases
removed). Public240/fast240/rich96/callback checks and all three guest suites
pass. Production savings are **81.32% collision, 79.98–80.00% corners,
80.10% lanes** with matching reports. Normal-budget engine replays match on all
maps: collision **144 versus 64 original expansions**, corners/lanes **1 versus
1**. The all-map target remains unmet on corners. Initializer-sinking guest
measurement is now running under `economy80-reduction-inits`.

## Initializer sinking crosses the all-map target

The research measurement completed with matching reports:

| Map | Team A savings | Team B savings |
| --- | ---: | ---: |
| collision | 81.34399840% | 81.34382807% |
| corners | 80.02098863% | 80.03909111% |
| lanes | 80.13849172% | 80.14118704% |

`insertion-sink-integer-initializers` is now integrated into
`base_integer_totals.py`. The separate `reduction_initializers.py` proof checks
contiguous zero/None initializers, an emitter-tagged integer multiset key, a private
integer-cache origin, the intact hit unpacking, and the original bounded cache
publication. Every successful fast path overwrites the outputs; the original
fallback loop retains its initializers and partial-error behavior. Missing or
perturbed proofs leave the initialization in place. The pass can be disabled
independently.

The integrated output has **77 sinking sites** and is byte-identical to the
measured research planner, SHA256
`33a7a6808e4b4204941ad3e3c244a37a3ccb3cee440bf562c3174f682f449aae`.
The focused proof-perturbation test passes. Final validation is running under
`replays/economy80-final-*`: three-worker compiler tests, public/fast/rich/callback
checks, emitted integer-block comparisons, two-repeat all-map fuel measurements,
three guest suites, explicit raised/normal work counts, three-round normal-budget
replays, and copied-bot tests.

`audit_eighty_percent.py` will verify all twelve map/team/repeat rows against raw
replays, explicit equal work, original-source provenance, unchanged signatures,
byte-identical source regeneration, and identical Wasm import/code sections.
**Final repeated validation and provenance audit remain pending.**

## Final validation and provenance audit — complete

`audit_eighty_percent.py` completed successfully after all fourteen final
validation stages and the copied-bot suite. Every one of the twelve
map/team/repeat measurements exceeds 80%; both repeats have exactly the same
fuel counts. Measurement order reverses on the second repeat. Savings include
setup and fallbacks within `DraftPlanner.build`.

| Map | Baseline fuel, A / B | Optimized fuel, A / B | Savings range | Equal expansions per team |
| --- | ---: | ---: | ---: | ---: |
| collision | 1,358,254,434 / 1,358,270,180 | 253,395,969 / 253,401,220 | 81.343828–81.343998% | 6,020 |
| corners | 4,213,032,489 / 4,212,574,475 | 841,722,240 / 840,868,153 | 80.020989–80.039091% | 20,000 |
| lanes | 4,202,084,642 / 4,202,809,623 | 834,597,389 / 834,628,102 | 80.138492–80.141187% | 20,000 |

Validation evidence:

- **298 unique compiler tests** across 43 modules pass with three workers in
  **788.1 seconds**. The earlier same-suite comparison measured **754.9 seconds
  parallel versus 1,881.784 seconds serial**, approximately **2.49x faster**.
- **71 copied-bot tests**, 240 public scenarios, 240 explicit fast contexts,
  96 rich scenarios, ten semantic fixtures and 18 callback contexts pass.
  Fast-path work remains 1,152 direct evaluations, 3,586 inline entries,
  815 compensated-cache hits and 1,249 scalar-group hits.
- **66,000 integer-total comparisons**, including 29,352 index errors, and
  **189,918 integer-edge comparisons** preserve exact outputs and final locals.
- All ten cases in each of the `prefix`, `losing`, and `eighty` guest suites pass
  on both fixture maps under guest CPython 3.13.7.
- Three-round uninstrumented normal-budget engine replays and stdout match on
  all three maps. The separate normal-budget work probe records collision
  **144 versus 64 original expansions**; corners/lanes remain **1 versus 1**.
- The audit reconstructs observations from raw fuel/work/guest replays and
  verifies the reports, rather than accepting saved success flags alone.
- **22 original files** match commit
  `97f761f04ed3d3e85a6f2217df345629baab58c8` byte-for-byte. Original fingerprint:
  `950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c`.
- Public signatures match. Freshly regenerated uninstrumented, fuel-instrumented
  and work-counted source trees match their measured copies byte-for-byte.
  Wasm import and code sections are identical between baseline and optimized
  bundles; runtime fuel accounting is unchanged.

The audit snapshot contains compiler/benchmark sources, generated and baseline
source trees, instrumentation variants, compiler-test logs and validation logs.
The JSON archive includes report fingerprints, source fingerprints, exact fuel
rows, normal-budget results and Wasm section hashes. Final planner SHA256 remains
`33a7a6808e4b4204941ad3e3c244a37a3ccb3cee440bf562c3174f682f449aae`.

To generate a fresh optimized bot:

```sh
uv run python -m tools.bot_optimizer bots/economy-bot \
  --output bots/economy-generated --verify --maps collision,corners,lanes
```

To independently repeat the fuel measurement, select a new output directory:

```sh
uv run python -m tools.bot_optimizer.compare bots/economy-bot \
  --target draft_planner:DraftPlanner.build \
  --output replays/economy80-repeat --maps collision,corners,lanes --repeats 2 \
  --require-equal-prefix 'SQUAD_LOOPS_DATA '
```

The exact final validation commands are retained in
`replays/economy80-final-validation/step-00.json` through `step-13.json`.
To audit the existing final evidence again, use new archive destinations:

```sh
uv run python benchmarks/bot-optimizer/audit_eighty_percent.py \
  --output replays/economy80-reaudit.json \
  --snapshot replays/economy80-reaudit-snapshot
```
