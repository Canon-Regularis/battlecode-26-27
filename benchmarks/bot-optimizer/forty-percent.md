# Forty-percent economy planner fuel target

The new target is at least **40% lower guest `DraftPlanner.build` fuel** against
unchanged economy-bot on collision, corners and lanes, with repeated equal work.
**Achieved and audited:** the generic compiler saves **43.46% collision,
45.05% corners, and45.55–45.56% lanes** in repeated equal-work measurements.
See [the complete result archive](forty-percent-results.json).
The audited starting savings are30.44–30.45%,32.61%, and
33.11–33.12% respectively; see [the30% archive](thirty-percent-results.json).

At the start, compiler/tests matched that archive byte-for-byte. The preceding work
is now in commit `e8577e7`; this investigation began with only the original
`bots/economy-bot` untracked. Preserve it and all earlier archives. No changes to
fuel accounting or original bot sources are permitted; use fresh output paths
and run heavyweight guest experiments sequentially.

## Refreshed evidence

`economy40-section-profile` refreshes the current generated planner, including
the adjacent-iterator rewrite. It completes6020 collision and20000 corners
evaluations. Collision's inclusive section probes report192.5m fuel in integer
totals,154.1m in edges,133.3m in inter-camp exposure and136.9m in service exposure.
These include probe overhead; nested risk timing is especially inflated. They
rank targets and are not acceptance measurements.

`economy40-wasm-analysis` archives31 inventories/excerpts from the actual current
Wasm. Re-read frame setup/default binding and the native sum loop in
`/tmp/opencode/economy30-final-wasm-disassembly.txt`. The float path around
`1c7aa0–1c7b49` performs compensated accumulation with f64 addition/subtraction,
absolute-magnitude comparison, and a correction accumulator. A plain Python
addition loop cannot replace it while preserving floating-point results.

## Candidate experiments

`forty_experiments.py` compares guarded candidates against current compiler output.
These manual fixtures are exploratory, not proof of compiler acceptance.

| Focus | Evidence | Result |
| --- | --- | --- |
| `reduction-frames` | `economy40-reduction-frame-candidates`,14 fixtures on both maps | Reject: inlining with local builtin aliases is about0.979x; global lookups are0.89–0.98x on nonempty short routes. |
| `product-sums` | `economy40-product-sum-candidates`,14 fixtures on both maps | Reject: guarded product collection plus native sum is0.56–0.87x on nonempty short routes. |
| `fused-native` | `economy40-fused-native-candidates`,10 fixtures on both maps | Reject: adjacent fusion helps1–4 items but loses at8–16; the required guarded gap variant is0.87–0.93x at4–16. |

The product candidate retains native compensated sum and only computes under
exact-container/index/record/numeric guards; the guard cost exceeds saved generator
resumptions. The revised fusion candidate keeps exact-integer gap guards before
moving a maximum across intermediate calculations. Earlier fusion measurements
used repeated Python bounds comparisons and global builtin lookups; the revised
candidate must prove a gain with all semantic guards included.

## Insertion-buffer hoisting

The earlier25-fixture refinement experiment measured outer-loop buffer reuse
at1.03–1.18x versus the already optimized insertion generator. The new
`tuple-insertion-hoist` pass applies that shape only to matched insertion loops
nested inside another loop. Each never-rebound exact-tuple parameter owns one
buffer, cleaned in a function-wide `finally`; custom sequences keep the original
fallback. Unnested loops retain their existing local cleanup. Buffer contents
between completed insertion loops are exclusively owned tuple elements.

167 compiler tests pass, including outer-iterator advancement/errors, generator
close/throw/exhaustion, saved exceptions and unrelated-local finalizers.240 exact
planner scenarios in `economy40-insertion-hoist-differential` retain the prior
observation hash. The7-case `--suite forty` guest suite and71 copied bot tests pass.
The repeated all-map comparison in `economy40-insertion-hoist-raised` saves
**30.58% collision,32.79% corners,33.28–33.29% lanes**, with both repetitions equal.
This is a small accepted improvement, still well below40%.

## Numeric-field cache prototype (not integrated)

The next exploratory probe caches exact-integer field validation on frozen records
and measures ordinary/fused consumers, including cold construction fixtures. This
is not yet a sound compiler transformation. Constructor reinitialization, factory
coverage, reflective/serialized state and shared-key/finalizer behaviour require
review before integration.

The initial `economy40-{record-tags,fused-tags}-candidates` measurements accidentally
exercised fallback for warm records: existing private factories bypass `__init__`,
so their records lacked the cache value. Those results do not measure the intended
fast path. The prototype now stamps factory-created records as well, and host
checks explicitly confirm all warm cache values and non-fallback helper results.
Fresh `economy40-{record-tags,fused-tags}-factory-candidates` jobs completed on both
maps. Ordinary warm kernels gain about1.02–1.09x, but construction-heavy kernels
lose at0.74–0.88x. Fused-gap kernels are approximately break-even or worse at
planner lengths. Retain these as exploratory evidence only.

A reentrant field-finalizer witness already disproves uninvalidated caches: a
constructor overwrites a numeric field with a callback-bearing value, then an old
unrelated field finalizes and invokes the reduction. Original evaluation returns
`(7,99)`, while the stale cached path returns `(7,2)` after a nested reinitialization.
Invalidating before each field store restores `(7,99)` in that witness. Any accepted
implementation must cover this case, not merely refresh a cache at constructor exit.

## Live record dictionaries (rejected)

`economy40-record-dict-candidates` completed14 fixtures on both maps. Profile
dictionary reads are0.55–0.74x; guarded row dictionary reads are0.70–0.89x on
nonempty fast-path lengths. They lose fuel and are not integrated. Hoisted
dictionary references would also require handling field deletion and dictionary
replacement across callbacks.

## Region specialization investigation

`draft_budget_exhausted` calls the external `cambc.fuel_remaining` function and,
when stopping, `print`. A generic analysis cannot assume arbitrary external
calls preserve a validated input graph. Any region-based specialization must
end its validity interval at such calls and validate again afterwards, or prove
a narrower effect contract. Unknown callbacks must keep the original path.

`economy40-batch-region-candidates` completed9 fixtures on both maps, with24
records validated each call and all route/leg guards included. Eight-call batches
are1.005x at length4 and1.092x at length8 (1.166x at length16, beyond the configured
maximum route length10). Single-call batches lose at0.36–0.60x; four-call batches
lose at lengths4/8. The actual fuel-check interval is8. This does not yet justify
implementing a whole-program region pass, especially with additional graph guards.

## Wasm postprocessing probe (not accepted)

Binaryen108 `wasm-opt -O3 -g`, without fast-math or engine modifications, produced
`economy40-wasm-opt-o3/optimized.wasm`. Build hashes/flags, section summaries and
fresh actual-Wasm inventories are archived. The original module remains
`bb0a10562b91dc9fc174d16b887387eb5e3d3044ab1f0ef4e0350d0787ceec3a`.

The initial standalone rewritten module was rejected before Python execution
with the diagnostic `bot was built in
debug mode (imports env::fuel_pause)`. Both modules contain that import; this is
an initially unresolved engine/runtime classification issue, not a measured fuel improvement.
The failed run and diagnostic replay are preserved. An official `build --release
--output` produces bytes identical to the original module. No hooks were removed
or renamed, and no fuel-accounting changes were made. `wasm_compare.py` now archives
CLI logs and failed-run status so engine traps cannot be mistaken for savings.

The classification issue is resolved by placing the identical rewritten bytes
under a Python bot's `.cambc/build/bot.wasm` context. The unchanged release engine
then accepts the module. `economy40-wasm-opt-o3-context-collision` verifies module
hashes before/after execution and equal reports, but O3 **increases fuel by0.99%**
against the current generated module. Reject this O3 configuration. No hooks,
engine code or fuel-accounting settings were changed.

## Progressive product accumulation probe (rejected)

The next manual fixture reduces the earlier product-sum guard overhead by checking
each computed result rather than validating every record and operand. Exact float
prefixes can be collected before native compensated `sum`; the first non-float
switches to a one-shot lazy continuation, avoiding repeated multiplication effects.
It still guards exact tuple/integer routes.14 numeric host fixtures match exactly,
plus mixed-result callback/finalizer and PEP479 witnesses. Full semantic acceptance
is pending. Guest measurements completed both maps in
`economy40-progressive-product-candidates`: nonempty fast-path kernels are
0.65–0.91x. Even reduced guards plus lazy continuation lose fuel; do not integrate.

The next unmeasured lead is a larger guarded risk-expression region that collects
primitive route inputs once, reuses them across edge and service calculations,
and retains native compensated summation. It must include guard/construction
costs and preserve overflow/exception ordering before any planner integration.

## Structural helper contracts (under validation)

Following the request for structural improvements, `helper_facts.py` introduces
an emitter-owned contract registry and a cross-helper fact-reuse pass. A successful
adjacent-extension helper certifies an exact tuple of exact integer indices and
its length bound. A later reduction helper can use a specialized private clone
without repeating those checks. Calls and callbacks cannot change these immutable
facts; any rebinding/deletion invalidates them. Mutable containers, record types,
numeric field values and bounds checks are retained. Failed producer guards keep
the original consumer/fallback. Public signatures are unchanged.

173 compiler tests pass, including callback mutation of records, custom tuple/index
fallbacks, invalid indexes, rebinding/deletion and disabled-pass combinations.
`economy40-shared-facts-differential` passes240 exact planner scenarios with the
unchanged observation hash and one contract reuse.12 guest fixtures and71 bot
tests pass. Repeated all-map measurements in `economy40-shared-facts-raised`
save **31.77% collision,33.88% corners,34.38–34.39% lanes**, with equal reports.
This is the current validated fuel improvement, still below40%.

The host compiler profile (`economy40-compiler-structure-profile`) attributes2.95s
of6.41s profiled compilation to100 calls to `used_names`, each performing several
whole-tree walks and lexical binding scans. `used_names` now collects identifiers
and hidden import/exception/pattern bindings in one traversal of the live AST.
`economy40-single-pass-names-candidates` alternates three old/new compilations and
verifies every emitted Python file byte-for-byte. Median host compilation is
**1.44x faster** (2.037s to1.412s); concurrent guest activity makes this preliminary
timing noisy. This improves compiler throughput, not guest fuel. The benchmark
retains the historical collector for repeatable isolated measurements.

An isolated rerun (`economy40-single-pass-names-isolated`) confirms **1.428x**
median host speedup:1.194s to0.836s, with all generated Python files identical.

`forty_experiments.py --focus helper-regions` completed6 fixtures on both maps.
Branch-specialized continuations gain1.005–1.019x over boolean proof dispatch.
The integrated `immutable-helper-regions` pass versions one bounded continuation
in the original lexical scope, without extra dispatch checks. Contracts now also
cover extrema helpers, preserving arbitrary comparison effects and stable ties.
175 compiler tests and240 exact planner scenarios pass; the planner uses two
contracts and one region.14 guest fixtures and71 copied bot tests pass. Repeated
all-map measurements in `economy40-helper-regions-raised` save
**32.53% collision,34.66% corners,35.16–35.18% lanes**, with equal reports.

`helper-fusion` retests cross-gap sums/maximum fusion with the new shared tuple
proof. Six fixtures on both maps still lose at ordinary lengths:0.90–0.95x for
4–16 inputs, versus the now-improved compiler. Reject; mutable field and gap
guards remain necessary despite the reusable tuple fact.

## Static container shapes (validated)

The structural framework now also registers container-type guards separately
from immutable-content guards. `static-helper-shapes` proves exact list/tuple
types from local literals, list comprehensions and aliases, invalidates facts on
binding changes, and specializes helpers without redundant container checks.
Mutation can change a builtin list's contents but cannot change its exact type.
Element/field checks remain in place. Static clones preserve any remaining
runtime contracts for composition with immutable helper/region specialization.

178 compiler tests and240 exact planner scenarios pass, including list-content
mutation through callbacks, annotation/rebinding rejection and custom numeric
fallback. The planner removes two more container checks. All 16 guest fixtures
and 71 bot tests pass. Repeated all-map measurements in
`economy40-static-shapes-raised` save **32.95–32.96% collision, 35.11% corners,
35.62–35.63% lanes**, with equal reports.

`section_profile.py --functions-only` completed the next hotspot refresh in
`economy40-structural-function-profile`.
It instruments actual generated helpers and planner methods after compilation,
so branch-versioned methods no longer depend on the older flat section markers.
These inclusive timings include instrumentation overhead and are not acceptance
savings; the emitted helper inventory and target list are archived with each run.
Collision inclusive costs: extension 92.3m, short-circuit 53.1m, totals 157.5m,
maximum 79.4m, risk 292.4m fuel. Corners: 267.8m, 159.9m, 444.3m, 230.0m,
853.0m respectively. Evaluation counts are 6020 and 20000.

The full `risk-regions` guard/collection probe loses heavily: six fixtures on
both maps give 0.55–0.58x baseline/candidate at lengths 1–16 and 0.982x on the
length-32 fallback (`economy40-risk-region-candidates`). Reject this candidate.

`guard-branches` now passes host checks: both intended cached integer type chains
are rewritten; six ordinary fixtures plus custom, missing, bool, float and int
subclass field cases match. Guest measurements in
`economy40-guard-branch-candidates` gain 1.015x at lengths 4–16, 1.009x at one,
and 0.999x empty on both maps. Integrated as `helper-guard-branches`, restricted
to generated exact builtin type calls on already-loaded locals. 179 compiler
tests and 240 exact planner scenarios pass with the same observation hash.
The 71 bot tests and 16 guest fixtures pass. Repeated all-map measurements in
`economy40-guard-branches-raised` save **33.15% collision, 35.29% corners, and
35.79–35.81% lanes**, with equal reports across both repetitions.

`helper-bindings` measures closure-cell binding and one packed tuple default
against the current per-builtin defaults. All 12 fixtures match on both maps,
but closures lose at lengths 8–16 (0.995–0.999x) and packed defaults lose across
all lengths (0.971–0.995x). Reject both as general replacements; retain current
cached defaults (`economy40-helper-binding-candidates`).

`mapped-products` is a prepared lazy native-map probe. It retains native sum,
evaluates one product per callback, wraps body StopIteration like a generator,
and uses an exact-tuple guard plus original fallback. Seven exact-value fixtures
and five mutation/index/exception/finalizer witnesses match on the host. Guest
measurement in `economy40-mapped-product-candidates` loses at nontrivial lengths:
0.91x at four, 0.84x at ten, and 0.79x at 32. Reject; it is not integrated.

`scoring-regions` combines totals, maximum and weighted-risk validation/field
collection in a single helper. Six fixtures match exact floats, and empty,
negative and invalid route cases match on the host. Measurements on both maps
in `economy40-scoring-region-candidates` still lose at 0.73–0.77x for lengths
1–16 (0.993x length-32 fallback). Reject the per-evaluation collection design.

Next investigation: conditional effect summaries for callbacks. The actual
budget callback's False path consists of a fuel read and an integer comparison;
its printing path returns True and terminates candidate expansion. This could
allow larger guarded regions if the pinned SDK call is proven read-only and the
callback identity/control flow are guarded. Unknown callbacks still require
invalidation. `sdk_effects.py` archives the actual guest SDK implementation in a
fresh diagnostic bot; do not infer this effect from the older workspace SDK.

The diagnostic completed in `economy40-sdk-fuel-effects`: guest CPython 3.13.7
reports the SDK wrapper calls `_bc.fuel_remaining()`, checks a negative result,
then returns the integer. The actual Wasm disassembly at `27dbc7` has
`w_fuel_remaining` call host import `sdk_fuel_remaining` followed by
`PyLong_FromLongLong`. This supports a successful-call read-only SDK contract,
but does not by itself certify an arbitrary user callback.

`snapshot-regions` validates all 32 numeric records, 32 weights and the full
32x32 distance matrix once per batch, then uses projected numeric arrays.
It loses through 64 evaluations: 0.906x at length four and 0.997x at eight.
`snapshot-fused` retains one fused totals/maximum traversal of packed numeric
rows. It gains **1.026x / 1.119x** at 64 evaluations of length four/eight,
including full setup, but loses for batches of one/eight. These are synthetic
callback-free batches, not planner acceptance evidence. Six exact-value fixtures
and empty/invalid/negative/list-route cases pass on the host. Invalid routes
must fall back: indexing a projected list would otherwise change the original
tuple's IndexError message.

`snapshot-long` completed 128/512-evaluation batches with one measurement
iteration per sample, no additional warmups, and 2bn guest fuel for both sides.
The archived runner retains five alternating samples and cold measurements.
Any integration still requires generic effect/region analysis, callback identity
and continuation proofs, primitive snapshots with no retained mutable aliases,
and original fallbacks at every failed guard. No snapshot transformation is yet
integrated into the compiler. At 128 evaluations, length four/eight gains are
1.109x/1.183x; at 512 they are **1.181x/1.235x**, agreeing across both maps.

## Whole-planner region feasibility (manual only)

`planner_regions.py` stages a fresh current-compiler copy and a manual private
search clone reached from the known budget-callback callsite. It snapshots exact
numeric records, configuration, matrix/spawn/altar tables, risk arrays and beam
routes once per search level. Failed schema/method/callback identity guards keep
the original path. Snapshots contain primitive copies, never retained mutable
user tables. The direct evaluator reuses numeric fields, fuses integer totals and
maximum, and retains native compensated sum for float products. Existing record
return construction is reused verbatim. Public methods retain their compiler
output. The whole-planner experiment remains target-specific benchmark code;
generic eligibility, emission and effect analysis are not implemented yet.

`economy40-planner-region-host` passes 71 copied bot tests and 240 dedicated
scenarios that explicitly exercise the fast context, with 1,152 exact direct
evaluation comparisons and equal complete loop results/stop counts. This avoids
mistaking the unknown-callback fallback for validation of the fast path.
Actual three-map feasibility measurements completed in
`economy40-planner-region-probe`. Against the archived original baseline, the
manual candidate saves **46.90% collision, 48.22% corners, 48.74% lanes** with
matching reports (`archived-comparison.json`). This is one manual run against
archived baseline measurements, not a generic compiler acceptance claim.

The reproducible `planner_region_differential.py` additionally checks unknown
mutating callbacks, custom truth conversion, numeric fallback, risk-method
overrides, mutation between levels, custom beam sequences, missing fields and
mutable-table finalizer timing. All pass in the host archive's `adversarial.json`.

## Generic region foundations (not wired into compilation yet)

`effects.py` now derives bounded path-sensitive False-continuation contracts.
Unknown calls, custom comparisons/truth, implicit None returns, rebound constants
and shadowed SDK modules reject the proof. The actual budget callback is recognized
with dependencies `settings.FUEL_RESERVE` and `cambc.fuel_remaining`.

`region_types.py` derives primitive graph schemas from resolved annotations and
simple constructors, and emits complete runtime validators/copying helpers.
Annotations select guards rather than proving types. Mutable inputs are copied
into private tuples. Before reading instances, raw class namespace guards reject
changed lookup methods or descriptors without invoking them. Missing/custom
fields take a distinct failure sentinel; optional None stays valid. Recursive,
unknown, descriptor-bearing and ambiguous layouts decline.

All **191 host tests** pass, including 12 focused effect/schema tests covering
unrelated class/field names, runtime mutations, malformed values and finalizer
timing. `economy40-generic-region-analysis` archives
the inferred whole-planner schema, callback contract and emitted snapshot source,
and confirms successful copying without mutable alias retention. Numeric clone
lowering, loop-region eligibility, effect barriers, callsite guards and pipeline
integration remain required before fresh repeated acceptance measurements.

The current schema builder requires **exact float** for a float annotation.
The first generic-analysis archive predates this refinement and labels those
fields `number`; its emitted source remains preserved as historical evidence.
This distinction is essential for future eager numeric comprehensions: mixed
int/float native sum can raise while converting a huge integer, whereas an exact
float-only sum does not. Moving later element evaluation ahead of that conversion
could change exception order. An integer supplied for a float field now keeps
the original path.

Next implementation design: lower pure numeric methods from their actual AST,
projecting guarded record fields to tuple positions and resolving only verified
pure helper methods. Collect method-identity and indexed-access obligations.
Argument shape/bounds guards must precede projected accesses; invalid cases call
the original method so container-specific errors stay unchanged. Preserve native
sum, converting generators only when primitive type/effect and exception-order
proofs permit it. Fuse only total, exact-integer traversals. No snapshot-derived
containers may escape as public return values. Derive consumer epochs and known
callback callsites structurally, invalidating across other unknown calls; the
manual benchmark's names and formulas must never become production matching rules.

Additional actual-Wasm structural settings are rejected:
`economy40-wasm-structural-variants` uses correct Python bot contexts, unchanged
release accounting and no fast-math. Binaryen108 O1 increases collision fuel
by1.86%, and Os by1.39%, against the region-specialized compiler; reports match.

Full host/guest, exact planner, repeated all-map, work-count, normal-budget and
source-provenance audits remain required for any eventual40% completion claim.

## Generic integration and repeated target result

`numeric-consumer-regions` is now in the normal compiler pipeline. All schemas,
field projections, formulas, numeric helpers, consumer operations and callsites
are derived from ASTs. The production pass contains no planner-specific matching
rules. Public methods and signatures remain intact.

* `numeric_regions.py` emits primitive-only numeric clones, fuses total integer
  reductions and a compatible later extremum, and hygienically inlines small pure
  helpers. Native float sum remains compensated; its empty integer-zero result is
  tracked rather than assumed to be a float. Stored lazy iterators, loop-carried
  fact changes, borrowed mutation and projected result escapes decline.
* `consumer_regions.py` solves source-derived container/alias facts across helper
  calls, branches and loop backedges. It accepts only native operations and owned
  container mutation. Unknown effects and shared mutable helper defaults decline.
* `regions.py` guards callbacks, SDK dependencies, exact owner/record schemas,
  method identities and source helper bindings. A dirty True callback disables
  numeric dispatch before its branch continues. Callsite argument restrictions
  prevent wrappers from retaining new arbitrary finalizable temporaries.
* Proven numeric assignments use native indexing. On `IndexError`, the private
  clone returns a distinct sentinel and the original evaluator runs outside the
  exception handler. No borrowed mutation or callbacks can occur in the clone;
  moved expressions can otherwise fail only by native indexing. Retrying restores
  original error order, list/tuple error wording and skipped short-circuit reads.
  Other call forms retain explicit bounds guards.

Measured iterations, all with runtime checks included:

| Archive | Collision | Corners | Lanes |
| --- | ---: | ---: | ---: |
| `economy40-generic-regions-first` | 37.09% | 39.14% | 39.64–39.65% |
| `economy40-generic-region-typed-guards` | 38.74–38.75% | — | — |
| `economy40-generic-region-inlined` | 38.92% | — | — |
| `economy40-generic-regions-repeated` | **43.46%** | **45.05%** | **45.55–45.56%** |

The final row uses fresh unchanged baselines and **two repetitions on all three
maps**, matching printed reports on both sides. It supersedes the manual
prototype as the generic target result.

Current host evidence: **214 compiler tests**, **71 copied bot tests**, and the
unchanged 240-scenario public-planner observation hash
`f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6`.
`generic_region_differential.py` additionally verifies 240 successful contexts,
1,152 direct fast evaluations, 3,586 consumer numeric calls, exact returned records
and stop counts, and no retained mutable input aliases. The latest conservative
analysis restrictions emit byte-identical economy-bot source to the measured build.

`economy40-final-wasm-analysis` contains 31 inventories/excerpts from a fresh
disassembly of the actual final bundle. Native tuple/list item routines perform
their own bounds checks and set Python errors; those checks make repeated Python
bounds scanning redundant in the certified retry region. Static instruction
counts are explanatory evidence, not the measured fuel reduction. The SDK fuel
wrapper remains at `27dbc7`, calling the host counter without accounting changes.

Final validation completed:

* Raised-fuel counts are exactly **6,020 collision / 20,000 corners / 20,000 lanes**
  for both versions and both sides. Instrumentation covers the original method
  and the emitted consumer clone; full engine replays and stdout match.
* Three-round uninstrumented normal-budget matches have identical engine replays
  and stdout on every map. Exit-only work probes show collision expands 128 times
  versus the original 64; corners and lanes both retain the one-expansion fallback.
  Normal-budget probes are behavioural checks, not equal-work fuel measurements.
* All **16 existing and 10 new region guest fixtures** pass on collision/corners
  under guest CPython3.13.7. The new tiny fixtures are semantic witnesses; their
  setup-heavy timings are not the planner performance claim.
* `audit_forty_percent.py` passed every gate: replay equality, explicit work,
  fresh source reproduction, unchanged public signatures and Wasm runtime code,
  and byte-for-byte original source provenance against
  `97f761f04ed3d3e85a6f2217df345629baab58c8`.

The complete evidence and prompt-to-artifact checklist are in
`forty-percent-results.json`. The reproducible compiler, benchmark tools, baseline,
generated sources and their instrumented variants are archived in
`replays/economy40-final-audit-snapshot`. The original bot remains untracked and
unchanged. No staging, commits, merges or pushes were performed for this work.
