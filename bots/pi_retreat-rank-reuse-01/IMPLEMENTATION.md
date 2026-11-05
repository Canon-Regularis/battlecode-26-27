# rrr01: retreat rank reuse and final movement epoch guard

Implemented against `2f0f534e8311ee597e516b11c2afca1bbf608060`, using its exact `bots/leader_party_tuned/` source as reference. Changes are uncommitted and confined to this candidate directory. This is an implementation for PC review, not a submission or promotion recommendation.

## Hypothesis and actual change

An improving candidate was ranked twice at a fixed state. Reusing its owned scalar tuple removes that duplicate evaluation while preserving the selected neighbor in a current epoch. A final current-round check prevents committing a fallback move after ranking crosses rounds. No fuel or playing-strength improvement is assumed.

The only modified inherited file is `src/navigation.cpp`, and only `retreat` changes:

- Each iterator element gets `const auto candidate_score=rank(p)` once. Strict comparison and assignment reuse that value.
- Inside `if(best!=s.pos)`, immediately before `move_checked(best)`, exactly one `if(!budget.current())return false;` is added.

The rank lambda, origin evaluation, tuple order, iteration expression/order, radius, blocked board, spawn access, initial safe attempt, early returns, pathfinding, Memory behavior, helper checks, invalidations and public API remain unchanged. No cache, threshold, capture, retry, logging, or other experiment is added. There are no departures from the requested production contract.

Added files:

- `tests/retreat.cpp`: scripted native public-retreat fixture.
- `tests/run_retreat.py`: extracts production/parent bodies, enforces the exact two-edit production delta, compiles and executes the fixture.
- `tests/run_local_checks.py`: reproducible Pi checks, including inherited tests and native SDK syntax checks; artifacts go to temporary directories.
- `IMPLEMENTATION.md`: this report.

Strategy/SDK references read: repository and bot READMEs; `docs/strategy/leader_party/{README.md,combat.md,state_machine.md,strategies/pathfinding.md}`; `docs/cambc/api/SDK_4.0.0.md`; actual C++ SDK declarations/bodies for live getters, camp enumeration, movement, spawn regions and reachable masks. Source/config remains authoritative where older navigation/state-machine prose describes untuned values.

## Native checks and exact outcomes

Run from repository root on the Pi (aarch64, Ubuntu GCC 13.3.0, Python 3.12):

```sh
python3 bots/pi_retreat-rank-reuse-01/tests/run_local_checks.py
```

All checks passed:

| Check | Result |
| --- | --- |
| Production contract | Entire navigation source equals exact base source with only the two required substitutions; every other production file byte-identical to base |
| Public retreat fixed-state comparison | 1,014 parent/candidate pairs pass (9 explicit arrangements, 1,000 seeded varied arrangements, 5 safe-status variants) |
| Two improvements, iterator includes origin | Parent 6 rank/incoming/camp enumeration calls; candidate 4; both move to `(2,2)` |
| Two improvements, iterator omits origin | Parent 5 calls; candidate 3; both move to `(2,2)` |
| All fixed-state comparisons combined | Parent 5,556 incoming calls and 5,556 camp enumerations; candidate 4,047 incoming calls and 4,047 camp enumerations |
| Scripted boundary executions | 30 executions across both versions pass |
| Inherited `decisions.cpp` + `state_machine.cpp` | `PASS protocol and state scenarios` |
| Inherited `strategy_contracts.cpp` + actual extracted geometry | 55,294,203 assertions pass; 5,041 map dimensions, 21,298,225 tiles, 116,964 centers, 1,176,588 requests |
| Inherited `verify_translation.py` | 240 cases match exact historical Python planner rankings, routes, scores and timing |
| SDK syntax | All 11 returned production `.cpp` files pass against unchanged `sdk/cpp` with native accommodations below |

The explicit two-improvement arrangement is self `(3,3)`, awake positive camps `(4,3)` range 1 strength 20 and `(3,4)` range 1 strength 60, candidates `(2,3)` then `(2,2)`, and spawn `(0,0)`. Actual extracted incoming code is checked to produce 80, 60, 0. Other adjacent tiles are scripted as walls/occupied; tested candidates are adjacent, unoccupied and within the radius. The origin-including variant evaluates origin again. Separate arrangements cover strict ties, no improvement, no enemies, mixed enemy/camp risk, fractional strengths, nearest-enemy and spawn-distance tie breakers, and no neighbors. The seeded cases vary camp liveness/awake state, ranges, fractional strengths, and enemy risks. They preserve each input's entity/addition order and compare both versions with identical inputs; generated candidate permutations are never sorted to favor a result.

Boundary assertions cover:

- Successful safe movement returns immediately with no fallback ranking or round check. Scripted wait, deferred, no-route, invalid-goals and at-goal results proceed through the original fallback rules.
- Stale epoch immediately after the safe attempt, unavailable movement after that attempt, and empty spawn retain early exits.
- Round change in the origin's camp-position getter and in a later candidate's camp-position getter: candidate finishes finite ranking, returns false, makes zero movement attempts and performs zero fallback invalidations. The parent makes the stale fallback move in these fixtures; preserving that action is deliberately not required.
- Stale ranking with no improvement returns without adding a final epoch poll.
- Movement becoming unavailable or movement restriction becoming active during ranking reaches the actual `move_checked` checks and prevents `move_absolute`. The existing retreat invalidation still occurs once.
- Success, false/rejected movement and expected bad-destination errors retain two invalidations (helper plus retreat). Unexpected movement errors propagate with no subsequent invalidation. Visibility enumeration failure during origin/later ranking propagates with no movement or invalidation.
- Every fixture compares every actual Memory member to its value **after** the scripted initial safe attempt, including its legitimate blocked-counter or successful-move updates. There is no fallback mutation or rollback.

These are function/query counts, not SDK import counts, measured game fuel, fuel savings or strength results.

## Extraction provenance and substitutions

`run_retreat.py` reads parent source directly using `git show 2f0f534e8311ee597e516b11c2afca1bbf608060:bots/leader_party_tuned/src/navigation.cpp`. It extracts the complete parent and candidate `retreat` definitions using brace matching. Both functions execute as public functions in separate fixture namespaces. No ranking or dispatch expressions are copied into the fixture.

Extracted retreat definition SHA-256 values (printed by the runner):

- Parent: `08009af2e6b07cad54f79ca3b544cd1c24254b3b44f881ac591c3933e81aacb9`
- Candidate: `77599a01b6342830fc73f62debae1e98ca766407f366a4ce39f13928fe72b7ca`

The actual unchanged `incoming_at` and `move_checked` definitions are extracted from `src/observations.cpp`; `cheb` and `TurnBudget` are extracted from their production headers. `incoming_at` executes inside an implementation namespace with a counting forwarding wrapper at the original call boundary. Its body and floating-point accumulation remain unchanged. The fixture separately counts `vision::camps()` entries and asserts incoming/enumeration counts agree. Actual production `Memory` and `Config` types are included.

All environment substitutions are explicit in `retreat.cpp`: snapshot/observe, self/entity handles and getters, camp enumeration, round/fuel imports, spawn board, ordered reachable-mask/position boundaries, move results/errors, restriction values, invalidation counter, and safe `move_to`. The safe-path stub validates arguments and scripts its result and Memory effects. It does not execute real field computation, dashes or yielding. The bitboard boundary supplies ordered neighbors and checks origin/radius; it does not implement engine geometry. Getter hooks inject rollover or movement-state change, and visibility/movement error mocks preserve the relevant error-code interface. No observation refresh or intentional Snapshot mutation is introduced during ranking.

Inherited geometry tests extract `World::chunk` and `World::center` into a minimal scalar fixture, retaining their real bodies. The inherited planner comparison retrieves its historical Python reference from local Git objects at `97f761f04ed3d3e85a6f2217df345629baab58c8`. Its Windows compiler/output paths are adapted **in memory** to GCC and `/tmp`; its original file is unchanged. The PowerShell decisions script is run through its equivalent native GCC compile/execute commands, with output redirected to `/tmp`.

## Syntax limitations, remaining uncertainty and PC handoff

The raw native GCC syntax command initially fails on existing SDK `team team()` naming and inherited sources' transitive `std::ceil` include dependence. The passing check uses:

```sh
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only \
  -I sdk/cpp bots/pi_retreat-rank-reuse-01/src/*.cpp
```

These flags accommodate the native compiler only; no SDK or production files were edited to resolve them. The inherited planner compilation emits its existing misleading-indentation warning at `src/loop_planner.cpp:55`. The new retreat fixture compiles with `-Wall -Wextra -Werror`. No release/WASM build or game runs were performed on the Pi.

Mocks do not establish engine geometry/visibility fidelity, import accounting, WASM suspension behavior, full observation-cache freshness, release action identity or actual game performance. The guard only rejects stale ranking at its final explicit check; no stronger atomicity guarantee is claimed. Changed getter schedules may alter suspension timing and later optional work. Exceptions still propagate, and ranking is allowed to finish before detecting rollover.

No local implementation blocker remains. The named Swirl/C02 A+B release replays were not found in this checkout (only `maps/00swirl.map26a`); earliest action/fuel divergence and the first affected retreat episode therefore remain unaudited PC work. Do not assume the old A Heart 1630–1647 timestamps recur, or require repetition of its stale unsafe action.

PC must review exact source/tests, run its release build, replay comparison and frozen standard80 screen against the original champion on the existing engine3/CLI5 maps/opponents/both sides. Mandatory gates remain zero VM faults, direct >=9/16, common >=35/64, common banking >=44512, common gem loss <=2352, common deaths <=548. Record fuel suspensions, early noninitial pauses and actor-round-normalized rates, scores, collected/banked/lost resources and deaths; separately investigate repeated caught SDK errors. Any missed gate or unexplained regression blocks expansion. Broad/confirmation stages require separate freezing; consumed confirmation maps are not fresh. No duplicate baseline games, upload, online challenge or ranked change is authorized by this implementation.
