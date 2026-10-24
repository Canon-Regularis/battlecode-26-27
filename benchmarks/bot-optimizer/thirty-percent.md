# Thirty-percent economy planner fuel target

The explicit new target is **at least30% less guest planner fuel** than the
unchanged original economy-bot, on collision, corners and held-out lanes, using
the established `draft_planner:DraftPlanner.build` boundary and repeated equal work.
The latest repeated measurements exceed the target on every map:

| Map | Less `DraftPlanner.build` guest fuel |
| --- | ---: |
| collision | 30.44–30.45% |
| corners | 32.61% |
| lanes | 33.11–33.12% |

Both repetitions agree exactly in `replays/economy30-restart-adj-iterator-raised`.
166 compiler tests,71 copied bot tests,240 exact planner scenarios, and47 guest
fixtures (36 focused plus11 reduction cases) pass. **The final audit is complete**:
equal work, normal-budget behaviour, original-source provenance, measured-source
correspondence and reproducible snapshots are verified in
[`thirty-percent-results.json`](thirty-percent-results.json).
The audited starting measurements are documented in [`twenty-percent.md`](twenty-percent.md):
20.30–20.31%,22.50%,22.99–23.01%.

The previous implementation was already committed when this phase began; the
working tree initially contained only the untracked original economy bot. All
new evidence uses fresh output directories. No original bot files are edited.

## Latest Wasm and remaining costs

Disassembled the actual43,004,984-byte starting bundle again with WABT. Full local
output is `/tmp/opencode/economy30-start-wasm-disassembly.txt`;21 selected function
inventories/excerpts and the module hash are in `replays/economy30-wasm-analysis`.
The inspected `min_max` body has561 static instructions and20 direct call sites;
`PyObject_RichCompareBool` has163 static instructions. Its comparison/truth-conversion
and reference cleanup paths motivate direct source loops, but these **static counts
are not dynamic fuel estimates**. The interpreter, native sum and generator paths
remain relevant. Float arithmetic and the original `sum` accumulation semantics
must be preserved.

`economy30-profile` records new inclusive guest profiles on collision/corners.
Both variants execute6020/20000 evaluations respectively. In the optimized profile,
evaluation consumes approximately83% of instrumented planner fuel, including risk
calculation at approximately25%. Instrumentation overhead is included; these
figures rank targets rather than establish savings.

## First36 competing guest fixtures

`thirty_experiments.py` and `economy30-first-candidates` compare:

| Candidate | Baseline/candidate fuel | Decision |
| --- | ---: | --- |
| Two-argument min/max Python helper |0.906–0.980x|Reject extra helper call |
| Inline cached record construction,2–20 fields |1.097–1.133x|Implement narrowly |
| Direct indexed min/max loops,1–32 rows |1.053–1.566x|Implement with semantic guards/cleanup |

Both maps complete;36 ordinary host result comparisons match. Separate host
comparison, boolean, expression-exception and finalizer witnesses test cleanup.
Floating-point extrema retain comparison order, NaN behaviour and stable ties.

## Allocation-preserving return inlining

`record-inline-return` removes the cached factory call at a proven terminal return.
It still allocates the **same exact record and dictionary at the original point**.
This does not use the rejected deferred-record prototype. It permits simple frozen
records with2–20 fields, definitely bound local/constant arguments and at most one
other expression. Multiple effectful arguments are rejected because an earlier
temporary could otherwise survive in an exception traceback when a later argument
raises. Unsupported scopes, constructors, hooks, defaults and bindings fall back.

Shared-key order before/after rejected records and field finalizers are covered.
Generated dictionary cleanup initially prevented the existing fusion pass from
matching; the composed implementation handles straight-line local deletion in
its definite-binding analysis while rejecting ambiguous nested deletion.

The repeated whole-planner result (`economy30-inline-return-raised`) is
**20.87% collision and23.12–23.13% corners**, still well below30%. Its copied71 bot
tests and240 exact differential scenarios pass. The initial diagnostic differential
without fusion is preserved separately; the composed differential is the measured
candidate.

## Direct indexed extrema

`extremum-loop` recognizes one min/max generator with an attribute/index expression,
an exact-list/tuple fast path, and original-generator fallback for custom iterables.
Captured locals must already be bound; nested mutable closures, generic scopes,
exception handlers/context managers, filters, keys and defaults are excluded.
Existing identity and arithmetic-only reduction passes retain their patterns.

The helper preserves first-winner ties and the exact comparison sequence. Generator
expression `StopIteration` becomes `RuntimeError` with its cause; comparison/bool
exceptions propagate normally. It releases the current value, best value and
iteration references in the appropriate error paths. Comparison errors also clear
helper parameters so tracebacks do not pin caller-owned inputs unnecessarily.

An additional audit of the earlier `short-circuit-loop` found that a saved boolean
exception could retain its input container after the caller rebinds the local.
The helper now clears that parameter on the boolean-error path; a concrete
finalizer-order regression covers it. Prior archives are preserved.

Current host evidence: **144 optimiser tests** and **240 exact differential
scenarios**, including exact float hex observations and unchanged input fingerprint
`950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c`.
Generated guest fixtures (`--suite thirty`) completed on both maps. Repeated
whole-planner comparisons in `economy30-extremum-raised` save **22.19–22.20%
collision,24.47–24.48% corners and24.97% lanes**. All repeated samples agree.
These jobs began before the latest traceback-cleanup edits; fresh guest witnesses
are still required for those paths. The source-aligned host differential is
`economy30-extremum-cleanup-differential`.

The next26 manual candidates (`thirty_experiments.py --focus next`) completed in
`economy30-next-candidates`. Scalar extrema inline at1.076–1.186x baseline/candidate
fuel; nested clamp cleanup at1.043–1.171x; guarded native pairwise at1.144–1.299x.
Indexed adjacency loses fuel at16/32 elements and is not integrated.

`scalar-extremum` handles bound-local/constant pairs and narrow terminal-return
chains whose first argument is a bound local/constant. It preserves comparison
direction and clears every materialized temporary with `finally`, including on
boolean errors. `tuple-adjacent` handles unpacking `for` loops with a never-rebound
parameter owner, guarding exact tuples and retaining original zip behaviour for
lists/subclasses/custom sequences. Escaping pair objects and rebinding are excluded.

Current combined host evidence:151 optimiser tests,71 copied bot tests and240
exact planner scenarios in `economy30-scalar-adjacent-differential`, with the same
observation hash. The first expanded guest attempt finished all22 cases, but its
report validator read only the first `CASES` assignment (the fixture used `+=`).
The inventory is now one literal assignment; the fresh full run passes both maps in
`economy30-scalar-adjacent-generated-fixed`. Repeated all-map comparisons in
`economy30-scalar-adjacent-raised` save **23.60% collision,25.98–25.99% corners and
26.47–26.48% lanes**. Both repetitions agree. The original failed report directory
is preserved.

The35-candidate kernel suite (`--focus kernel`) completed on both maps in
`economy30-kernel-candidates`. Native multi-attribute extraction loses substantially
(0.585–0.753x), as do dictionary update/keyword/zip fills (0.532–0.749x). Reject them.
Direct incremental extension loops win, especially native pairwise. Eager extension
is only an exploratory cost bound: callbacks observe wrong partial-target contents.
It is **not semantically acceptable**.

The20 `--focus dispatch` fixtures in `economy30-dispatch-candidates` compare guarded
Python-callback maps against generator expressions, including PEP479 handling.
They lose at ordinary lengths (approximately0.78–0.91x); reject them too.

A stricter extension audit found that arbitrary tuple indices can finalize in a
different order when a saved expression-error traceback is destroyed. The first
simple witnesses did not expose this. `economy30-checked-extension-candidates`
measures an exact-int tuple guard:1.47x at one index,1.23x at four,1.065x at eight,
but losses at16/32. The compiler therefore limits `adjacent-extend` to exact lists
and exact tuples of at most eight exact integers. It appends incrementally,
preserves PEP479, and clears the temporary value and helper target reference.
Unsupported cases return before effects; the original generator expression stays
in the original caller, preserving fallback traceback ownership and finalizers.

Current extension candidate:156 optimiser tests,71 copied bot tests and240 exact
planner scenarios pass (`economy30-extension-differential`), with unchanged
observation hash. The27-case guest suite passes both maps. Repeated all-map
comparisons in `economy30-extension-raised` save **23.94–23.95% collision,
26.94–26.95% corners and27.42–27.43% lanes**. This remains below30%.

The next ten `--focus fusion` probes combine three guarded integer sums with an
indexed integer extremum. A variant includes intervening numeric assignments and
`sum` over an additionally validated exact integer sequence. This investigates
whether redundant record reads and iteration can be removed when every intervening
operation is proved callback-free. It remains a manual candidate, not a compiler pass.
Host probes also match float-field fallback, missing attributes, huge-int division
overflow, and a custom sum operand mutating a later extremum field. A second ten-case
`--focus extension-fusion` experiment combines exact-integer matrix extension with
its immediately following negativity check. Both completed and are rejected:
cross-gap reduction fusion is0.70–0.97x; extension/check fusion is0.33–0.89x. Guard
cost outweighs eliminated iteration. Adjacent reduction fusion only helps tiny
fixtures and does not justify integration for the planner.

## Refreshed section profile and private-helper refinements

The renewed investigation reads the current `economy30-extension-raised` Wasm,
with full disassembly at `/tmp/opencode/economy30-restart-wasm-disassembly.txt`.
`economy30-restart-wasm-analysis` archives27 runtime inventories/excerpts. Read
the actual global-lookup dictionary searches, frame initialization/default binding,
list-extension iterator/allocation paths, and list-index native bounds handling.
Static counts include114 instructions in `_PyDict_LoadGlobal`,2423 in frame setup,
and361 in generic list extension. They are not dynamic fuel estimates.

`section_profile.py` produces source-aligned, grouped guest profiles with route-length
breakdowns. `economy30-restart-section-profile` completed6020/20000 evaluations.
Collision reaches route lengths9–10 (1744 evaluations), while corners stops at8.
Integer totals, edges, inter-camp exposure and service-risk sums remain substantial.
Nested section probes heavily inflate the enclosing risk timing; all measurements
explicitly include instrumentation overhead and are used only to rank candidates.

The48 `--focus caches` fixtures completed both maps. Private-helper default bindings
for type/int/list/tuple/len improve guarded sums by about2.2–4.4% at measured short
lengths and extension up to2.5%. Type-only defaults give smaller improvements for
short-circuit/extremum helpers. General local aliases often lose. The compiler's
`helper-builtin-cache` applies only to generated helpers; public signatures stay
unchanged and have a regression covering argument errors/defaults.

The20 `--focus loops` fixtures found two further wins: hoisting the invariant lower
integer bound and using ordinary bound comparisons saves about5–8% at4–8 indices;
a local initialized boolean instead of a global extremum sentinel saves about5–6%.
`helper-loop-shape` implements those refinements. Other check/store rearrangements
did not consistently improve them. All original guards and error cleanup remain.

Host evidence for the combined helper candidate:156 existing tests plus one new
signature regression pass;240 exact planner scenarios retain the same observation
hash in `economy30-restart-helper-differential`. Its27 guest fixtures pass both maps.
Repeated planner measurements save **24.99% collision,28.45% corners and
28.93–28.95% lanes** in `economy30-restart-helper-raised`.

The28 `--focus indexing` probes completed both maps. Replacing redundant Python
bounds comparisons with native exact-sequence indexing and IndexError fallback
wins about12–15% at1–8 indices. With the new guard,16-index reductions also win;
32 indices lose. Cached extension helpers similarly remain profitable through16.
The Wasm list-index path already performs its own bounds check; the implementation
retains exact-int/exact-container guards and original fallback errors.

`native-index-guard` and `wide-helper-limit` pass157 host tests,71 copied bot tests,
240 exact scenarios and11 guest reduction fixtures including negative, huge and
late out-of-range indices. `economy30-restart-native-index-raised` saves
**27.92–27.93% collision,30.15% corners and30.65–30.66% lanes**, repeated twice.
The all-map target still requires further collision improvement.

## Tuple insertion buffers

The24 `--focus insertions` fixtures compare starred tuple construction and three
private-buffer alternatives. Starred construction loses. A list buffer using
insert/yield-tuple/delete wins1.30–1.69x at4–16 elements, exceeding the pop and
adjacent-move alternatives. Empty inputs incur some guard/setup overhead.

`tuple-insertion-buffer` recognizes a single-yield loop enumerating insertion
positions into a never-rebound tuple parameter. The inserted value must be an
owned local. It guards exact tuples, retains the original custom-sequence path,
and produces fresh exact tuple outputs. The private buffer is deleted in `finally`
before leaving the original scope; it cannot pin payloads after generator close
or a thrown exception retained in a traceback.

The candidate passes162 host tests plus an additional unrelated-local-finalizer
regression, and240 exact planner scenarios in `economy30-restart-insertion-differential`.
Tests cover value identity, nested insertion loops, send/close/throw, PEP479,
saved tracebacks, subclasses, malformed patterns and source signatures. The
34-case expanded guest suite passes both maps, and71 copied bot tests pass. The
completed `economy30-restart-insertion-raised` repeats agree exactly and save
**28.62–28.63% collision,30.80% corners,31.29–31.31% lanes**. At this stage collision
was still below the all-map target; the adjacent-iterator refinement below closed it.

## Adjacent iterator refinements

`economy30-restart-refinement-candidates` measures25 fixtures on both maps.
Replacing pairwise tuple production/unpacking with a previous-item local and an
exact tuple iterator wins1.11–1.34x. Sliced iteration is a smaller win; explicit
index arithmetic loses on long inputs. Hoisting insertion buffers across the
outer item loop wins1.03–1.18x, but is not yet integrated. Separating the first
max item from its remaining loop is only a small long-input win and loses on
short inputs, so is also not integrated.

`tuple-adjacent-iterator` applies the measured iteration shape to stable owned
tuple parameters and the already integer-guarded adjacency extension helper.
Original custom-sequence fallbacks remain. Extra iterator/previous references
are removed in `finally` before original locals are cleared. A regression caught
CPython lexical local ordering: binding the right target first would swap finalizer
order on function exit. A nonexecuted declaration preserves the original left/right
local slots, including their unbound state for empty inputs.166 host tests pass.
The scalar-extremum pass must run before this pass introduces cleanup blocks;
the first differential probe exposed that interaction and pass order was corrected.
Fresh36-case guest fixtures pass both maps, as do71 copied bot tests and240 exact
planner scenarios. The repeated planner comparison saves30.44–30.45% collision,
32.61% corners and33.11–33.12% lanes. The final checks below confirm equal work and
complete the audit.

`economy30-restart-vector-reduction-candidates` rejects14 native bulk-reduction
alternatives. Composing itemgetter, attrgetter, zip, map(type), and identity guards
costs roughly2.4–4.2x the current direct helper on nonempty short inputs. Type IDs
were also measured to avoid invoking custom metaclass equality; they lose further.

## Final verification and archive

The accepted boundary is `draft_planner:DraftPlanner.build`, measured twice on
each map for both sides with the raised fuel argument `1000000000`. Every pair
has equal printed planner witnesses, equal engine trajectories, and identical
fuel samples between repetitions. These are planner-call savings.

Explicit `LoopPlanner.find_loops:expansion_count` observations in
`replays/economy30-final-raised-work` verify6020 collision expansions and20000
on each other map for both original and generated bots. Engine replays and stdout
also match. At the normal engine budget, the exit-only counter probe records:

| Map | Original expansions | Generated expansions |
| --- | ---: | ---: |
| collision | 64 | 112 |
| corners | 1 | 1 |
| lanes | 1 | 1 |

The collision difference is the fuel-aware search doing more work; it is recorded
in `replays/economy30-final-normal-work`. All three engine trajectories still match.
The separate **uninstrumented three-round** run in
`replays/economy30-final-normal-budget` has byte-identical engine replays and
stdout on every map.

`audit_thirty_percent.py` completed successfully and produced
`thirty-percent-results.json` plus `replays/economy30-final-snapshot/audit.json`.
It recomputed all savings, checked both repeats, and verified:

- All22 original bot files match commit `97f761f04ed3d3e85a6f2217df345629baab58c8`
  byte-for-byte; input fingerprint is
  `950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c`.
- The original bot remains untracked, and the staging area is empty.
- Current emitted sources match the measured planner, differential, work-counter,
  normal-budget and guest-fixture sources exactly.
- The240 exact differential observations retain hash
  `f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6`.
- Compiler, tests and benchmark Python tools are snapshotted and fingerprinted.
  Uninstrumented baseline/generated bots and both instrumentation variants are
  included in `replays/economy30-final-snapshot`.
- The final42,983,841-byte Wasm bundle was disassembled again;31 runtime inventories
  and excerpts are in `replays/economy30-final-wasm-analysis`. Its native code section
  exactly matches the inspected runtime (SHA256
  `4ede57b72071d411c57c75b83ad6a4b723c63d664be838a67db38a4fe63bf2a0`).

Reproduce the principal comparison in a fresh directory:

```sh
uv run python -m tools.bot_optimizer.compare bots/economy-bot \
  --target draft_planner:DraftPlanner.build \
  --output replays/economy30-reproduction \
  --maps collision,corners,lanes --repeats 2 \
  --require-equal-prefix 'SQUAD_LOOPS_DATA '
```

The JSON archive embeds the final reports, earlier progression measurements,
source fingerprints and rejected exploratory fixtures. No commit or merge was
performed during this investigation.

```sh
uv run python benchmarks/bot-optimizer/thirty_experiments.py --output <fresh-directory>
uv run python -m tools.bot_optimizer.benchmark --suite thirty --output <fresh-directory>
```
