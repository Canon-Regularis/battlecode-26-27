# Recovery phase diagnostic, profile version 1

Parent: `d378591a722eed9ebb6b1c407e748c9ecad9274a`,
`bots/pi_actor-scene-epoch-01/`. Candidate:
`bots/pi_phase-profile-recovery-01/`. Changes are uncommitted and confined to
this candidate. No games, uploads, SDK, infrastructure, other-bot or policy
changes were made on Pi. There is no competitive or fuel-optimization claim.

## Hypothesis and implementation

The suspension regression needs execution attribution before an economic core
or recovery optimization is selected. Completed inclusive costs and explicit
crossings can identify expensive stages under instrumentation; source scaling
and wrapper counts alone cannot establish fuel cost or suspension causes.

Read the current leader-party overview, state machine, combat, navigation and
Pi bridge documents, inherited implementation report, controller/adapter,
observation revision implementation and current C++ SDK. SDK fuel is a checked
signed host value exposed as uint64; first-turn allowances differ. Identity is
the actual champion handle, obtained through cached public self only at drain.

Added production files:

- `src/phase_profile.h`: exact requested default activation declarations,
  compile-time scope masks, fixed actor-local storage, sampler, nonthrowing
  scope interface, scalar context summaries and deferred text records.
- `src/phase_profile.cpp`: enabled-only SDK round/fuel/actor/output adapter;
  OFF translation unit has no defined symbols.

Hooks are confined to three existing production files:

- `src/recovery_sdk.cpp`: bits 0 recovery (including backend construction),
  1 prepare (including initialization/cache work), 2 capture, 3 self_geometry,
  4 members, 6 defense and 7 issue (including preflight and actual wrappers).
- `src/recovery.cpp`: bit 5 whole select_plan, returned Plan counters;
  Outcome counters at the existing controller construction/result boundary and
  the existing caught Halt boundary. Recovery admission is inherited explicitly
  from its enclosing recover scope, never from unrelated active turn scopes.
- `src/bot.cpp`: bit 8 whole play_turn, with drain immediately before its
  scope at the explicit function-entry safe point. All early returns remain.

Enabled function bodies are enclosed by try blocks with Halt/SDK/other catches
that close/label and rethrow unchanged. Pure planner exceptions use the
nonthrowing destructor's unwind detection. Capture's geometry and optional
member scope objects live outside that try block so the catch can label both
without shortening original self/state/reference lifetimes. Geometry closes
explicitly after clearing origin occupancy, immediately before enemy list
acquisition. Members starts immediately before visible camp acquisition and
extends through final camp construction/freshness checks. No original
statement or declaration was moved. Child scopes close before capture on
exception. Normal early returns close through destructors. No output occurs
inside recovery or exception handlers.

All new gameplay additions are removable `PPFX*` invocations and one header
include per changed file. OFF removes every added scope/object/helper/counter,
try/catch and output operation, including all sampling and extra getters.
`PPFX_STATUS_1/2` expands back to the original single Status expression OFF;
ON it records a returned status without evaluating it twice. Preprocessor bit
macros eliminate disabled scopes and their associated context hooks. There is
no runtime phase-mask dispatch. ON mask zero can still drain empty summaries;
OFF has no drain at all. Navigation, action permissions, evaluation order,
thresholds, reserves, quotas, static-cache publication, SDK observation revision
and controller gameplay tokens are preserved.

## Measurement and storage semantics

Scope IDs/bits 0..8 are recovery, prepare, capture, self_geometry, members,
plan, defense, issue, play_turn. Each admitted scope records entry separately
from completion/closure. Completion counts include labeled returned, Halt,
SDK and other exception exits; the exit bins disambiguate these. Normal
returned statuses and Halt status details have separate distributions. Halt
caught internally by execute becomes a returned recovery Outcome, with a
separate controller Halt-status counter; it is not falsely reported as an
exception escaping recover.

A sample is one bounded round/fuel/round attempt, without retries. A changed
round, negative fuel or throwing getter invalidates the sample. Global
`sample_invalid` also preserves failures with no usable entry round. Entries
whose first sampled round is 1..100 are admitted, including incoherent samples
whose round is known; unusable unknown-round samples cannot be admitted. A
coherent equal-round pair with nonincreasing fuel supplies an **inclusive**
delta. Incoherence, clock regression or fuel increase within a round supplies
an invalid closure, never a fabricated delta. Each summary has count, sum,
min/max and eight bins: [0,1000), [1000,4000), [4000,16000), [16000,40000),
[40000,100000), [100000,250000), [250000,1000000), [1000000,infinity).
Nested inclusive values must not be summed as exclusive costs.

A valid forward crossing increments crossed count and retains actual start/end
round/fuel and scope ID in a shared 16-example array. No assumed per-round fuel
allowance or cross-round fuel total is computed. Additional crossings increment
`dropped_cross`. Metric count/sum overflow is counted explicitly; sum saturates.
Status admission outside the fixed 12-status range also increments overflow.
The arrays are fixed: nine scope summaries, 27 scalar context metrics plus
recovery-entry-fuel metric, four 12-status distributions and 16 crossed
examples. No collection allocation, sorting, formatting, actor lookup, output
or per-call event queue is introduced. No profiler SDK handles are retained.

Context uses existing values at construction/results: cold/warm member and
terrain cache paths at prepare entry; capture scene cells, enemy count, static
and visible members and mapping counts; relevant known/alive/awake totals
accumulated during the existing member loop; queries at capture closure;
returned Plan raw/risk/effect/actions and actual controller Outcome status,
moves, dashes, recalls, captures, cancellations and defenses. Query counts are
**guarded wrapper attempts**, including an increment rejected by quota, not raw
host imports or fuel. Relevant member totals are recorded only when the loop
reaches its existing final boundary. Other context likewise can be absent when
its construction boundary is not reached. Outcome captures are the existing
controller's capture attempts, not successful reward captures. Returned Outcome
status is omitted on an escaping exception; already recorded action/capture
counters are retained, and scope exits preserve the exception evidence.
Recovery entry fuel reuses the recovery scope entry sample. Upstream world,
observation, shopping and other turn work appears only in whole play_turn cost,
not silently in recovery/capture.

Admission permanently closes after observing round >100. Existing admitted
scopes can close later, retaining their real crossing; they are never forcibly
completed at round 100. The inline Store belongs to the actor's WASM instance,
not a life or turn. Death/respawn code never resets identity, totals or safety
state. It contains no dynamically expanding storage.

## Deferred records

At function-entry safe point only, drain samples current round/fuel and checks
round >100, coherent sample, fuel >=40000 and zero active admitted scopes,
before actor lookup or formatting. It repeats the guard for each of at most
two records per invocation. Formatting uses bounded stack buffers only here.
Every line starts `PPFX actor=<actual handle> source=ase01-d378591a profile=1
mask=<hex> window=1..100 phase=...`. Records are cumulative phase summaries,
context metrics, status bins, retained crossings, and one `phase=complete`
trailer with dropped examples, overflow, sampler invalidity and output failures.
Status bin order is the unchanged recovery::Status enum; status rows are normal
prepare, normal capture, controller-caught Halt and returned recovery Outcome.
Output cursor advances before emission: failing output is counted/lost rather
than retried with duplicate evidence. Completion is attempted exactly once;
an output failure can therefore lose its trailer. No later collection summary
is printed after completion. A missing drain/trailer is missing evidence.

## Preservation checks and tests

Changed test drivers: `tests/source_contracts.py`, `tests/run_focused.py`,
`tests/run_adapter.py`. Added `tests/profile_preservation.py`,
`tests/phase_profile.cpp`, `tests/run_profile.py`. Updated this report and README.
The five inherited gameplay/revision fixtures (`recovery_scenarios.cpp`,
`decisions.cpp`, `strategy_contracts.cpp`, `adapter_scene.cpp`, `adapter_epochs.h`)
remain byte-identical to exact ase01 parent. No gameplay assertions were removed.

The previous scalar-only production byte-preservation gate was explicitly
replaced for this experiment; **that unchanged byte gate is not claimed to
pass**. The inherited repair is still checked against its preceding parent.
Two independent OFF checks now compare with exact ase01:
mechanically stripped/normalized source tokens for every inherited production
file, and actual compiler-preprocessed OFF tokens for all three modified
translation units. Untouched inherited files retain their exact bytes. The
empty OFF profiler object is checked with nm. These checks are not substitutes
for the PC's required WASM hash identity.

Actual Pi commands/results are recorded below. Tests use temporary binaries
and generated adapters. SDK syntax retains the parent's GCC -fpermissive
workaround; shared SDK files are unchanged.

```sh
python3 bots/pi_phase-profile-recovery-01/tests/run_focused.py
python3 bots/pi_phase-profile-recovery-01/tests/run_adapter.py --profile
python3 bots/pi_phase-profile-recovery-01/tests/run_adapter.py --parent-control
```

Focused checks pass: unchanged 292 controller assertions, protocol/state
scenarios, every production source against current SDK OFF and ON mask 0x1ff,
all integration/coordinate/revision contracts, normal real-SDK adapter fixture,
normalized/preprocessed OFF preservation, empty OFF object, scripted profiler
interface at masks 0x1ff/0/0x155, and ON real production adapter hooks. ON fixture
asserts entry/closure balance across scopes 0..7, actual SDK/Halt exit labels,
Halt status details, normal statuses and query/cache/plan/recovery context.
The optional inherited negative control still reproduces the pre-ase01 stale
fresh-capture failure after one committed step, as expected.

Scripted-clock tests execute the actual profiler implementation for same-round
cost, min/max/histogram boundaries, nested inclusive overlap, early return,
unwinding, explicit exit labels, multi-round crossings, entry and exit sample
incoherence, round regression, invalid/increasing fuel, getter exceptions that
preserve an underlying exception, fixed-example overflow, numeric sum overflow,
no tag/output through round 100, an active admitted scope crossing beyond 100,
active drain suppression, fuel guard, two-record bound, stable actor tags,
exactly-once completion, output/tag failures, permanent admission closure,
mask elimination and OFF invalid-name elimination. ON adapter additionally
executes actual wrapper -> invalidation -> fresh capture -> continuation and
all inherited rollover and SDK-error paths, with instrumentation enabled. A
separate actual-controller/LiveBackend proxy case throws on capture after a
committed move and asserts that the move counter survives while no normal
returned recovery status is invented.

## Limits and PC follow-through

No fuel or competitive measurements were taken on Pi. Native mocked round/fuel,
visibility, field and action behavior cannot establish engine fuel consumption,
scheduling, suspension, actual engine legality or WASM resource usage. Observer
effect includes entry/exit round/fuel/round imports, counter work, exception
wrapping, initialization/storage, nested scopes and context accumulation. Costs
include some nested instrumentation, while an entry's own sampling and final
bookkeeping are not completely included in its delta. ON can change control
flow, outcomes and crossings. Its values cannot establish unbiased parent cost
percentages, uninstrumented private control flow, universal mechanism inactivity
or strength. Matches ending before safe drain remain incomplete evidence.

PC must review source and build OFF first. Require exact parent WASM SHA-256:
`b87eb8b98c9f2b70827515a16f7bbca22cbab874c72bb931a1b290d74d4846d6`.
This artifact gate has NOT been performed on Pi. Only after it passes, build ON
with PPFX_ENABLED=1, PPFX_PHASE_MASK=0x1ffu. Verify both compiler flags AND changed
source activation bytes, so CLI's source-input cache cannot reuse OFF. The old
PC profile_campaign.py defaults to original a24ef0... and must be parameterized
for this exact ase01 hash before use; it was not edited here.

Run exactly two Swirl/C02 games, both sides, current CLI 5 / engine 3,
loglimit 2,000,000, shared gentle_run/reserved physical core. Reuse cached ase01
Swirl results as uninstrumented controls; no OFF games after identity passes.
Retain ON divergence and missing/overflow evidence. No adaptive scout expansion,
strength panel, standard80, uploads, challenges or ranked change. The frozen
rounds 1..160 prefixes with 12-round context lacked Recall/dash-before-walk;
that remains incomplete coverage, not proof of inactivity. ON results may
localize completed/crossed stages only, subject to the observer effects above.
