# actor-turn-core-01 implementation

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, cloned `leader_party_tuned`.
This is a recovery-controller construction experiment. There is no competitive
improvement claim. No tournaments, uploads, ranked changes, commits or pushes
were performed. All edits are inside this candidate directory.

## Hypothesis and actual change

A single owner of recovery actions can express physical dash escapes, two-action
motion sequences, and immediate committed health recall without depending on a
risk-masked walking route. Replanning after each action should make these
sequences explicit while keeping stale observations and unknown landing effects
out of subsequent decisions. These are policy/construction hypotheses, not
predictions of prevented damage or wins.

Read: the current leader-party state-machine and configuration-tuning documents,
the strategy overview, GameRules action/destination/channel timing contracts,
and the checkout's public `sdk/cpp/cambc.h` interfaces for states, restrictions,
buffs, dash metadata, bitboard export, fields, camps and cached groups.

Changed inherited files:

- `src/bot.h`: owns persistent recovery runtime and includes its public adapter.
- `src/bot.cpp`: routes exactly every `State::escape`, or `State::recall` with
  fresh `Memory.recovering`, into the controller. Removes the old escape execution.
  Escape abandonment/carrier release remain; cancellation belongs to the controller.
  Integrates channeling/healing state and genuine motion/defer counters; released
  recovery returns to explore intent for the next dispatch, unfinished recovery
  keeps escape intent. It then
  returns without optional ward or another dispatch. Bank/capture/progress and
  pending-bag counters are not rewritten as recovery success.
- `src/objectives.cpp`, `src/route_plan.cpp`: add explicit `<cmath>` includes
  required by their inherited `std::ceil` uses on this Pi. No policy changes.
- `README.md`: candidate-specific check command and report link.

New files:

- `src/recovery.h`, `src/recovery.cpp`: owned scalar scene, public backend and
  outcome interface, pure bounded plan selection, channel/path comparison and
  common executor.
- `src/recovery_sdk.h`, `src/recovery_sdk.cpp`: production public-SDK adapter,
  immutable terrain/full home-field cache, membership/range and per-turn action
  history flags, capture and guarded primitive actions.
- `tests/recovery_scenarios.cpp`: scripted backend exercising that same executor
  and planner, without SDK imports or a second decision implementation.
- `tests/run_focused.py`, `tests/source_contracts.py`: runnable Pi checks and
  structural/source-preservation assertions.
- `IMPLEMENTATION.md`: this report.

All other inherited source is byte-identical to the base bot. The source check
verifies this, allowing only the two `<cmath>` include additions above. Original
camp/bank movement, route planning, economics, draft, equipment thresholds,
state selection order and shared communication are retained.

## Interface, ownership and order

`recovery::execute(Intent, Memory&, Backend&) -> Outcome` is the common public
entry. `select_plan(const Scene&, allow_step, allow_dash)` is the pure test seam.
`Scene` owns positions, health, permissions, visibility/occupancy buffers and
scalar threat/camp records. It shares immutable owned static terrain, spawn and
complete home distances. It stores neither live SDK handles nor `observe()`
references. Outcomes carry executed history, successful movement/dash counts,
attempt/cancel/recall/defense/capture/candidate counts, unknown-effect and
prefix-risk rejection counts, plus the homeward-route flag.

Outcomes distinguish channeling (no arrival claim), reached spawn while the
health latch remains set (no healing claim), recovered (health latch released),
partial actions, blocked attempt, no improving motion, defensive/cancelled wait,
incomplete work, initialization deferred and stale epoch. Stale/incomplete
outcomes retain counts/history of actions already completed. A blocked motion
ends the dispatch without another attempt or footer.

The original dead, tribute/teleport, spawn-defense, danger and existing-recall
ordering remains in `decide`. Routing uses the fresh health latch, never
`Facts.recovery` (which also includes gold). Gold-only recall keeps the original
branch outside this adapter. Every escape still uses the controller, including
gold-only evasion; its health footer requires a newly observed health latch.
There is no earlier spawn-healing override. Carried gems do not disable health
recovery; pending bank state survives it.

Controller order:

1. Admit/finish static initialization, capture an owned scene and update the
   inherited <=35% / >=55% health hysteresis.
2. For active recall, compare preservation with a visible, clear, zero-current-
   and-response-exposure path of at most five ordinary steps. Require steps
   <=remaining timer (discounting this turn if known controller movement was
   already spent). Otherwise preserve a clear channel even with distant visible
   enemies. Threatened channels may cancel once through live permission checks.
3. A selected faster-home cancellation refreshes permissions and executes only
   its freshly checked first step. It suppresses new recall for the turn, even
   if that step fails or actual movement after cancellation is unavailable.
4. Otherwise select stay/step/dash/dash-step/step-dash; execute only the first
   action, refresh, update the health latch and replan with remaining allowances.
5. Invoke one guarded compatible defensive primitive, at most once; refresh if
   it acted and update the latch again.
6. Report spawn/recovery truth, or start committed health recall when below
   55%, the latch is set, alive outside spawn, no visible foe or covering awake
   damaging camp/current exposure, and exact permissions/epoch/reserve pass.
   Refresh after starting; channeling does not imply future arrival or healing.

Per-turn native recall-started/cancelled flags and runtime flags block repeat
starts/cancels, including a failed native start. Tribute/teleport are never
cancelled here. Stun, completed-turn, actor/life/round and channel state are
checked explicitly; an empty restriction set is not treated as recall permission.

The defensive adapter retains shield priority at the inherited <70% HP/current
exposure condition, then the inherited ally-heal <75% condition and heal/lethal-
exposure ranking, then one lowest-health reachable enemy basic attack. It is
intentionally a single primitive, not the old multi-action `fight` call: recovery
no longer casts offensive spells/attack resets or follows a shield with another
combat action in this dispatch. It never moves, wakes camps by attacking them,
or starts/cancels channels. Fresh preflight guards issuance; the controller
refreshes before its footer. All ordinary camp-service combat remains unchanged.

## Geometry, effects and bounds

Only integral range 1 or 2, nonexclusive dashes are supported. Nonfinite,
fractional, larger-range, exclusive or otherwise unsupported metadata explicitly
leaves ordinary-step/stay/defense/health-recall fallback. Two simultaneously ready
supported dashes return incomplete rather than silently expanding the cap or
choosing one without comparison. Effect radius support is integral 0..2.

Dash physical paths use one or two eight-neighbor steps through visible,
in-bounds, vacant tiles. Walls, holes, altars, enemy spawn, champions, camps and
teleports block the physical subset. The actual self origin is cleared. There
is no tactical mask in reachability, and no normal-move prerequisite for a
nonexclusive dash. Native allowance/cooldown/restrictions are rechecked before
issuance. Cross-hole or occupied overflight and all exclusive dashes remain
unsupported; no exclusivity inference is made from `!can_move`.

Current basic exposure sums visible enemy and known awake camp Strength in
geometric attack range. Enemy range+1 exposure is separate. Neither is predicted
HP loss: no shield discount, cooldown prediction, beneficial stun or kill is
invented. Each action prefix must have current exposure <=the fresh origin's.
Intermediate nonzero exposure is allowed.

Damage/stun landings require the entire in-bounds effect square visible. All
enemy contacts are initially unsupported because retaliation/passive effects
are not simulated. Each hit camp group requires fresh live/dead evidence for
every member. Positive-damage hits add known living asleep damaging siblings
at full Strength, even when the hit member was already awake or passive.
Groups are deduplicated before siblings are added. Unknown groups/members and
stun-only camp contacts are excluded. A remembered camp tile being visible is
necessary but not sufficient for death evidence; fresh public `state()` must
confirm dead. Missing/hidden state stays unknown.

Membership comes from World's cached groups, never per-endpoint
`camp::camp_group()`. Camp range is cached by public camp kind. Each refresh
captures visible camp positions once, then live state/Strength only for camps
within range+5 of self or in a potentially hit group. This covers the entire
motion neighborhood and five-step channel comparison. Hidden members remain
unknown. Effect/group results are cached once per landing. Scalar current,
response and nearest-enemy features are precomputed on the local 7x7 square;
continuations use those records, with no host getter or `is_set()` in endpoint,
ranking, effect or BFS loops.

Ranking is terminal current exposure, terminal enemy range+1 exposure, full
static physical home distance (65535 remains unreachable), greater nearest
visible-enemy distance, worst action-prefix exposure, motion action count,
then stable first x/y/action and terminal x/y ties. Stay participates, so a
non-improving scene does not force motion.

Explicit caps (`recovery::Limits`):

| Work/data | Limit |
| --- | ---: |
| Map/export cells | 16,384 |
| Visible enemies / defensive allies | 32 each |
| Cached/visible camp records | 256 |
| Cached groups | 128 |
| Ability slots | 2 |
| Ready supported dash choices | 1; more returns incomplete |
| Public query batches between captures | 4,096 |
| Raw plans per selection | 417 including stay; no dedup required |
| Selections per ordinary dispatch | 2, at most 834 raw choices |
| Distinct local effect landing caches | 49 per selection |
| Effect footprint | at most 25 in-bounds tiles per landing |
| Safe-home BFS | depth <=5, 121 nodes, 968 neighbor checks |
| Owned captures per dispatch | 6 maximum |
| Motion | <=2 successes, <=1 ordinary attempt and <=1 dash attempt |
| Channel cancellation / new recall / defense | <=1 each |

Membership matching is bounded by 256x256 scalar handle comparisons per capture.
Feature/effect work is bounded by the record and local-square caps; it performs
no host queries. BFS marks each eligible tile before scoring it, avoiding
repeated threat scans for exposed tiles. Caps and exhausted reserve yield
incomplete, never a partially collected "safe" model. The query cap counts
checked public call batches, not raw engine imports: some SDK methods and
round/fuel checks issue additional host calls. It is not a measured fuel bound.

The home field consumes one admission in the existing shared `TurnBudget`,
using unchanged reserve=5,000, admission=30,000 and total max_fields=3. It uses
full `distance_field::compute` with static blockers and own spawn roots, exports
once, and is reused across turns/lives of this bot instance. It is not a dynamic
or origin-stopped field. No model-dependent action occurs before initialization
finishes. A complete static computation/export that spans an epoch is retained;
the old dispatch then returns stale and discards its dynamic scene. Partial
field data is never published.

Epoch checks surround checked capture/preflight batches, pure planning/BFS and
issuance. Successful native work is counted once before checking for rollover.
There is no unbounded restart in the dispatch. Current-round unexpected native
errors propagate to the existing outer error reporter. Only explicitly missing
camp information is converted to unknown. No new release trace or extra debug
queries are enabled; counters are returned without per-action printing.

## Checks actually run on Pi

Host: aarch64, GCC 13.3.0. From repository root:

```sh
python3 bots/pi_actor-turn-core-01/tests/run_focused.py
```

Result: **292 recovery assertions passed**, inherited protocol/state scenarios
passed, all production source syntax passed, and integration contracts passed.

This compiles/runs native recovery scenarios with C++20, O2, Wall/Wextra/Werror;
compiles/runs inherited `decisions.cpp` with `state_machine.cpp`; checks every
production `.cpp` against the current public SDK with
`g++ -std=c++20 -fpermissive -w -fsyntax-only -I sdk/cpp`; and runs structural
integration/source-preservation assertions. GCC requires `-fpermissive` for the
shared SDK's existing `team team()` declarations. The SDK was not edited.

Scenarios exercise the actual common controller/planner:

- Ren walking-spent pure dash and risk-exposed ordinary midpoint; blocked,
  invisible, occupied/teleport midpoint and known occupied landing exclusion;
  edge bounds and the absent (19,17)/(20,17) control tiles.
- Heart no-hit dash->step; Ren 60->20->0; step->dash; unsupported dash fallback;
  first success followed by unavailable/blocked/stale continuation; failed first
  hidden destination; refreshed occupancy blocking the planned continuation.
- Full/partial effect visibility; effectless/no-hit controls; passive or awake
  hit waking a remote sleeping sibling; unknown and freshly dead sibling;
  duplicate hit groups (including a case that fails if sibling Strength doubles);
  no invented lethal/stun benefit; unsupported enemy effect contact.
- A37/B40 shaped observed disappearance after a safe step and same-dispatch
  health recall; distant visible enemy blocking the footer; no-health evasion;
  new observed damage enabling its latch; defensive healing releasing it;
  spawn/recovered distinction and pending carrier/bank memory preservation.
- Tribute/teleport/dead/stunned/completed/already-started/cancelled recall guards;
  clear active channel retained; threatened channel cancelled once; timer2/two-
  step home exception; unavailable movement after cancellation; blocked selected
  home step; obstructed, exposed, invisible, too-long or known-spent home routes.
- Stale capture, prerequisite, cancellation, first/second motion, refresh and
  enumerated final-current/preflight checkpoints; completed actions counted
  exactly once and no stale second action. Completed prerequisite reuse is
  exercised through the scripted backend's interface, not a native field mock.
- Incomplete prerequisite/capture and oversize enemy/group/camp models; exact
  417-choice open scene; deterministic selection; stay; zero planner backend
  calls; exact state adapter routing and no old retreat/ward continuation.

Also run the common native scenarios under AddressSanitizer/UBSan:

```sh
g++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I bots/pi_actor-turn-core-01/src \
  bots/pi_actor-turn-core-01/tests/recovery_scenarios.cpp \
  bots/pi_actor-turn-core-01/src/recovery.cpp -o /tmp/actor-recovery-sanitized
ASAN_OPTIONS=detect_leaks=0 /tmp/actor-recovery-sanitized
```

Result: all 292 assertions passed with AddressSanitizer/UBSan and leak detection
disabled; no memory-access or undefined-behavior finding was reported.

LeakSanitizer's default run fails because this managed environment uses ptrace;
leak detection is disabled in the runnable sanitizer command. This does not
constitute a leak check.

## Gaps and PC validation

No `uv`/`cambc` or WASI compiler was available on this Pi. Production code received
current-SDK source syntax checks, not an engine-linked/WASM build or gameplay
execution. Scenario scenes are deliberately bounded geometric/control fixtures,
not replay-prefix reproduction or proof of native endpoint acceptance. Scripted
failures/rollovers exercise the same controller contract; actual SDK suspension,
native permission failures, field persistence across real rollover, action-event
ordering, resource cap hits and fuel cost remain unverified in-engine. Full
source/native-backend integration cannot establish the SDK metadata conversion
or native action legality by itself.

In particular, range+1 exposure remains a heuristic and does not certify safety;
Heart599-style beneficial stun cases may be rejected; wider wake effects are
penalized; hole-crossing Heart147 is outside the supported physical subset.
The simplified single-primitive recovery defense may change combat strength.
No attempt was made to fit thresholds, economic utility, carrier-specific
recovery policy or champion strength. Hidden threats and future path safety are
not observed. Query/candidate bounds and reserve checks do not make multiple
actions atomic or guarantee they fit in a turn.

PC should build with the current SDK, run the separately specified frozen
8-game Swirl/Lanes/Elkring/Guardians panel, both sides versus C02, and inspect
native errors, sequences, recovery/arrival/healing, delivery, fuel, rollover and
cap hits. The subsequent economic-core construction should depend on review
and those findings, not a standalone win threshold.
