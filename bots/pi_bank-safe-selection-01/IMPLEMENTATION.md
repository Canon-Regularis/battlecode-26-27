# bss01: select banks under the executor's current camp mask

Implemented on the Pi, 2026-11-05. Base checkout HEAD:
`3558053c1602355a83f8387c3d6fe756afa40005`; supplied candidate inherits
`pi_bank-work-admission-01` (bwa01). All changes remain uncommitted and confined
to `bots/pi_bank-safe-selection-01/`. No engine games, uploads or ranked changes
were performed.

## Hypothesis

A completed altar search should use the same locally known awake damaging-camp
exclusions as safe `move_to`. A bank route that exists only through those attack
areas should complete unavailable, allowing bwa01's existing subsequent work
window. This does not establish escape, eventual camp capture, survival or banking.

The supplied release evidence motivates the change: bwa01 improved numeric wins
and banking but failed loss/death gates, with Guardian still banking zero. At the
sampled Guardian/C02/A round246 state the old selector mask had altar distance18,
while the executor mask had neither a route nor a legal safe first step. These
are supplied findings, not games or measurements reproduced on this Pi. Earlier
trajectory divergence and extra SDK queries may change the relevant release round.

Read the inherited implementation report, current leader-party strategy, state
machine, banking and navigation documents, SDK 4.0.0 notes and actual SDK camp,
vision, bitboard and field declarations. Strategy documents contain some older
thresholds; the inherited candidate source/config remains authoritative.

## Actual changes

Only `src/objectives.cpp::choose_altar` changes production behavior:

- Keep the initial `!b.admit() || b.fields>=1` return before any camp scan.
- Capture exactly one `vision::camps()` list. Starting with `s.blocked|s.risk`,
  test `is_alive()`, then `is_awake()`, then `strength()>0`, and union
  `around(c.position(),c.attack_range())`, exactly as safe `move_to` does.
- Check admission before each camp to stop the bounded loop before processing
  another camp once the turn is known stale or field admission is underfunded.
- Clear the origin after adding hazards. Recheck `b.admit()` after mask
  construction, before incrementing `fields` or computing the existing field.
  Incomplete construction returns deferred without field accounting or failure.

Scoring, typed results, retry filtering, previous-target hysteresis, final
round/reserve checks and caller application are unchanged. There are no map-wide
camp queries, hidden-state queries, persistent threat caches, extra fields or risk
relaxation. Sleeping/zero-strength camps add no hazard area; snapshot occupancy
continues to block them. The scan and checks add host queries, including on paths
whose selected outcome is unchanged. No inactive-artifact identity, fuel savings
or identical trajectories are claimed.

Navigation/executor, observations/facts, bank_due, admission/task deadlines,
maintenance, camp selection/execution, shopping, roster, configuration and release
logging are byte-identical to bwa01. No gold recall, egress, dash, dead-camp
progress or new timeout policy was added.

Test changes: extend `tests/mock/cambc.h` with scripted visible camps, query hooks
and HP/lifecycle queries; share the inherited host in `tests/bank_admission.cpp`;
add `tests/bank_safe_selection.cpp`; extend `tests/run_native.py` to compile/run
both fixtures. The new fixture links the actual `World::refresh` body; its combat
stub changes mock camp HP and observation version, leaving production refresh to
update objective HP and task progress.

## Checks performed

From repository root:

```sh
python3 bots/pi_bank-safe-selection-01/tests/run_native.py

g++ -std=c++20 -fpermissive -include cmath -fsyntax-only -I sdk/cpp \
  bots/pi_bank-safe-selection-01/src/*.cpp
```

Native suite: PASS, inherited 170 production selection/application/dispatch
assertions, 175 new safe-mask/production-refresh assertions,
and inherited protocol/state scenarios. Native environment: aarch64 GCC 13.3.0,
Python 3.12.3. Compiler outputs use temporary directories under `/tmp`.

New coverage uses returned production `choose_altar` results and production
application, rather than copied selection predicates:

- A physically/enemy-safe corridor is cut by an awake positive-strength camp's
  attack area. No camp, asleep, dead or zero strength preserves route selection.
  Physical occupancy is retained even for zero-strength camps.
- The exact attack-range boundary blocks; a route one tile beyond it remains.
  Clearing an enclosed origin does not connect it to masked neighbors. A reachable
  alternative wins over an unreachable previous altar; reachable cooldown and
  complete unavailability stay distinct. Unaffected tie order/hysteresis remains.
- Initial low fuel/field cap performs no camp scan. Rollover or fuel below30,000
  during list collection, early camp queries, the last camp, or an empty-list
  scan returns deferred, computes no field and preserves commitment/queue/stamp.
  The loop stops before the next camp. Exactly30,000 still admits the field.
- Field/scoring rollover and reserve exhaustion, and selected/unavailable
  application epoch/reserve guards still reject stale results. One field only.
  The inherited tests also cover the urgency query's application guards,
  post-field fuel25,000 and the reserve5,000 boundary.
- Through public `Bot::play_turn`, a current completed mask failure at246 leaves
  that turn bank-preempted with no camp attack. At247 the original still-due
  eight-gem task resumes, preserving bag age/prior bag/life and task start236.
  Simulated nonlethal attacks continue through256; actual production refresh
  advances progress from observed HP decreases without movement or manual progress
  writes. At257 the inherited window expires, banking preempts work and a fresh
  completed search records a new failure. No same-turn work admission is added.

The inherited fixture remains a branch test with stubbed refresh and some
synthetic progress-clock updates; it is not release mechanism evidence. The new
refresh fixture supplies the independent HP-progress test described above.
Inherited cases retain channels, danger, recall/healing, urgency, queue/locks,
ordinary banking and both caller sites.

Actual-SDK syntax check: PASS for every candidate translation unit. Existing SDK
`team team()` declarations require `-fpermissive` with this GCC; existing transitive
math-header dependencies require `-include cmath`. Only those inherited SDK naming
warnings were emitted. Neither SDK nor unrelated bot code was changed. No `uv`,
`clang++` or `cambc` executable is available on PATH; WASM/release build remains a
PC check. The Windows-only planner differential runner was not run; unchanged
planner code is outside this experiment.

## Limits and PC handoff

Geometry is a mock 20x20 Chebyshev bitboard with eight-neighbor BFS, scripted
physical/enemy occupancy and vision, not engine distance-field ABI validation.
The fixture compiles source bodies at runtime; only initialization and shop are
omitted in the new build, with test-only private-state access in a temporary
header. Navigation is a programmable stub. Combat subtracts mock HP without
engine retaliation, spell readiness, action limits, capture/reward transitions or
submission completion. Production refresh is exercised against a visible living
group with scripted HP/version changes, not engine observation timing, hidden
entities, capture timers, arbitrary WASM suspension or simultaneous actions.
Native action invocation does not prove safe engine capture. No measured fuel,
economic, loss/death, caught SDK-error, win or release mechanism result exists
for this candidate yet.

Frozen PC sequence remains the task's sequence, superseding the old bwa report:

1. Review exact source, build with engine3/CLI5 and normal fuel, then run the frozen
   standard80 original-champion panel. Require direct>=9/16, common>=35/64,
   banking>=44512, gemloss<=2352, deaths<=548, zero VM faults and preservation of
   Guardian/C02/A's win. Direct<8 or common<31 rejects; every other missed gate
   forbids expansion. Compare BOTH original33 and bwa01, including bwa01's
   10/16 direct, 44/64 common, banking51280, gemloss3109 and deaths573; disclose any
   reduction from44 common wins. Investigate new repeated caught SDK errors
   separately. Do not omit Guardian or relax gates.
2. Audit Guardian/C02/A Marcella through400 and the first actual due-bag transition
   exposed to the awake-camp mask mismatch. Reconstruct selector AND safe-executor
   masks from local preturn data, including enemy spawn tiles. Require original
   camp work within10 rounds of no-safe-bank evidence with the same bag surviving,
   and useful continued damage or capture through its bank-reconsideration
   boundary. Record death/loss and delivery. Round246 need not recur; no qualifying
   release witness means no expansion. Public actions plus reconstructed masks
   must not be represented as observed private task/stamp logs.
3. Only after ALL screen/economic/mechanism gates pass, run the already frozen
   Braided/C02 ordinary-bank A/B controls, identical hashes/seeds and existing
   baseline888/980: A>=800, B>=882, zero VM faults. No baseline reruns or claim that
   these reproduce the original online trap. Further broad/confirmation panels
   require a separate freeze. No upload or ranked change is authorized here.
