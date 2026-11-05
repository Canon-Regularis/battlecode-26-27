# dlp01: retain observed kills in committed camp progress

Candidate: `bots/pi_dominant-live-progress-01/`. Base: `35bbf733044c1facac007ac47be23684d60739aa`, bot `pi_dominant-prune-01`. Changes are uncommitted for the bridge.

## Hypothesis and scope

Task-supplied parent release probes show a partial-member kill removing live info while the spawn tile remains visible. Parent refresh restores that member's 120 design HP, which can prevent a real kill from advancing task progress. This task's local evidence is motivation, not newly measured release evidence here. Hypothesis: counting a locally verified dead member as zero prevents that artificial increase and lets ordinary commitment persist. Native progress improvement alone does not establish release improvement.

Inherited dg01 dominant metadata/preference, dt01 dominant bootstrap admission and dp01 combat pruning remain intact. Only production `src/objectives.cpp`, inside committed-task remaining-HP refresh, changes. Pathfinding, combat, roster, banking, gold recall, camp protection, scoring, timers, lifecycle and refresh scheduling are unchanged.

## Actual implementation

The existing visible/live expression remains `c.is_alive()?c.health():0`, with no new round query on that branch. On the unavailable-live-info branch, start with the original design HP. Only if the cached spawn tile is in snapshot visibility and the current round equals the snapshot round, call `c.is_dead()`. Check the round again after that call; contribute zero only for a positive dead result with a still-current round. Otherwise retain design HP.

Catch only `cambc::error` with `api_not_in_vision` or `api_not_found` from the new probe. These are uncertain observations and retain design HP; neither missing live info nor a missing identity establishes death. Other SDK errors propagate. No hidden health query, persistent death memory, attack-progress stamp, new path field or instrumentation was added. Noncommitted living objectives still use design health.

Reviewed current strategy overview, state machine, navigation, historical meta strategy, game rules and SDK compatibility notes, plus actual C++ camp/group declarations and typed API dead/hidden tests. `spawn_position()` is cached; `is_dead()` uses camp state separately from live info. Rules say camps do not chase. The local visibility condition permits the query but does not guarantee every identity lookup succeeds.

## Focused checks actually run

Host: aarch64 Pi; GCC 13.3.0. From repository root:

```sh
python3 bots/pi_dominant-live-progress-01/tests/run_native.py
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_dominant-live-progress-01/src/*.cpp
```

Both passed. Native builds use `-O2 -Wall -Wextra -Werror`. The first fixture run failed an incorrect test query-count assertion (the member was read alive at both 29 and 30); corrected to two reads, then the full runner passed. Production logic did not change in response.

The runner extracts the entire actual candidate `World::refresh` body without rewriting it. A reference extracts the entire parent refresh from the exact base Git object, renaming only its method to run alongside the candidate. The new fixture includes actual production `model.h`, so Memory, Config and `task_expired` are production code. There is no copied remaining-HP or expiry calculation standing in for those methods.

Natural 49-member scripted sequence: six earlier dead members have visible spawn tiles; member seven is 120 at 29, 10 at 30 and dead/live-info unavailable at 34. All those spawn tiles remain visible through 38.

| Refresh | Parent remaining | Candidate remaining | Parent progress | Candidate progress |
| --- | ---: | ---: | ---: | ---: |
| 29 | 5880 | 5160 | 20 (fixture initialization) | 29 |
| 30 | 5770 | 5050 | 30 | 30 |
| after kill 34 | 5880 | 5040 | 30 | 34 |
| 38 | 5880 | 5040 | 30 | 34 |

Actual `task_expired` expires the parent at 38 and retains the candidate. This demonstrates the supplied observation contract, not a claim that private release memory was inspected or that this exact release sequence will recur.

Additional fixture assertions cover:

- Nonlethal 10-to-5 reduction advances progress; unchanged health does not. Visible living reads health normally, visible dead does not read health, and the visible branch adds zero round queries.
- Hidden living and dead members with spawn outside snapshot visibility both contribute design HP, with no state/health/round query for those members. Another visible member keeps the group eligible for refresh.
- Visible spawn with unavailable live info but state alive falls back to base HP. Successful new probes check round before and after.
- New state errors not-in-vision/not-found retain base HP and cannot advance progress. An unrelated value-out-of-range error propagates.
- Round changes before the probe, during the probe, and during the post-query round read all retain base HP. An already-stale precheck skips the state query.
- Fully dead reward group sets zero through the existing lifecycle branch; capture timer reduction advances progress and an unchanged timer does not. Respawning records the existing deadline; fresh living respawn health returns to 120 without a new progress stamp.
- Noncommitted eight-round staggering/design health, hidden group skip, same-round/version suppression, independent stall=8 and task limit=90 boundaries remain effective.

Inherited runner checks also passed: 84 dominant metadata/actual selector assertions, protocol/state scenarios, and 19 actual fight/reference scenarios. All candidate production translation units passed actual-checkout-SDK syntax checks with inherited compatibility flags. This is syntax validation, not a release link. The inherited PowerShell runner duplicates decision checks; it and the Windows-specific planner differential script were not run.

## Host substitutions and limitations

The refresh fixture uses SDK-shaped substitutes, not linked engine imports: scripted camp live-info availability, dead/alive state, base/current HP, errors and rollover; group lifecycle/capture responses; a one-row 64-bit visibility/intersection board; observation version; and round reads. Objective/World/Snapshot shells supply the fields used by the unchanged extracted body. Camp counters assert that hidden/dead health is never requested. Actual SDK `is_visible` error translation, wrapper behavior, group visibility internals, real map geometry and suspension are not executed by this fixture; those declarations were reviewed and production compiles against them. Tests model state lookup failures explicitly. Parent reference extraction requires the base commit object locally.

No engine game, exact CLI5/engine3 WASM release, VM-fault check, fuel measurement or release-divergence analysis ran here. `cambc` and `uv` are unavailable on this Pi PATH. Extra state queries and two round reads for each eligible unavailable member can consume fuel and alter release timing, including earlier divergence than the supplied 34/38 sequence. Other task changes and execution cost remain possible causes of failures. No performance or strength conclusion follows from the native results.

## Exact identity and handoff

`SOURCE_SHA256SUMS` records every production source/header SHA-256 relative to this candidate. Its own SHA-256 is `b7a1fddffd6eff25f360642796c1e2922eb0d46902b2fbd6313de56c1a7232a6`. `src/objectives.cpp` SHA-256 is `6e77717b5967bb03249ff4e261af4b9b7f2668078ff64f60c26fa004e06f9ae1`.

Relative to the cloned parent, changed inherited files are only `src/objectives.cpp`, `tests/run_native.py` and this report. Added files are `tests/committed_progress.cpp` and `SOURCE_SHA256SUMS`. No other bot, SDK, repository tool or settings file changed. Generated native headers/binaries live in temporary directories and are removed by the runner; no release artifact exists to identify here. The PC must preserve the exact bridge source commit, release artifact hash, CLI/engine versions, build command, map/seed, frozen opponent identities and replay identities with its results.

## Frozen PC evaluation (pending)

After source review, build exact CLI5/engine3 release with normal fuel. First run four Vault games, both sides versus frozen champion and C02, using the same map/seed as dp01. Do not run the standard 80 tester first. Require all of:

- Zero VM faults. Investigate new repeated SDK errors, especially this state-query path.
- Champion-A central capture before 200 and subsequent own bank before 250.
- Champion-B first capture at or before 215 and bank at or before 238, the parent values. This is non-regression; 215 does not satisfy the earlier capture-before-200 gate.
- At least 3/4 wins and champion-A central HP removed through 100 strictly greater than 1080.

Inspect actual release first divergence, commitment/useful work after a partial-member kill, central damage and capture, with local visibility evidence where needed. Do not assume the exact 34/38 sequence recurs after query timing changes. These are developmental gates, not leader competitiveness. If any gate fails, retain the finding and do not expand solely on local wins or native progress improvement; do not weaken gates after outcomes.

If all pass, freeze a separate next panel before further matches. Other dominant maps and ordinary regression conditions remain unevaluated. No broad evaluation/upload or ranked change follows from these four games. Original 16 confirmation maps are consumed and must never be relabeled fresh. Commits and pushes belong to the bridge.
