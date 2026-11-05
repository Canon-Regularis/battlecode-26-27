# dt01: shared passive-objective admission at the opening

Candidate: `bots/pi_dominant-team-01/`, cloned from `pi_dominant-gems-01` at parent source `ef22c7f92ecab5fe76e3333ab7df3f8ec567ff9a`. Changes remain uncommitted for the bridge. No champion merge, platform selection change or upload was performed.

## Parent history and hypothesis

Parent dg01 originated from `leader_party_tuned` at `2f0f534e8311ee597e516b11c2afca1bbf608060`. It added a cached canonical index for the unique positive-gem, zero-gold, all-gem-cluster group whose gems strictly exceed all other groups combined, and preferred it only during bootstrap after the existing eligibility scan. Its Pi report recorded 40 focused metadata/selector checks plus protocol/state scenarios and native SDK syntax checks. It retained the solo max_clear=90 rejection. No item experiment was inherited.

The supplied subsequent PC evidence describes dg01 as tested but unpromoted, active on 3/112 surveyed development maps: the two other affected maps improved to 7/8 versus 3/8, but Vault stayed 1/4 versus 1/4, with first useful candidate capture at 1239. Vault's 49 passive clusters total 5880 HP and 343 gems; other camps together yield 16 gems. The solo estimate excludes that group for all four starting picks. Fish's clear33/capture39 and Mite's capture38 show an opening opportunity with different opponents. Fish's five actors' aggregate 6120 monster damage equals the center plus an earlier 240-HP gold group; final clear credit is not evidence of solo work. These are task-supplied observations, not independently replayed Pi results, and do not establish exact routes, commands or allocation for our roster.

Hypothesis: identical local policies can select the same publicly known passive objective early and share actual work if the solo clear estimate stops vetoing that one objective. This is a bounded coordination experiment, not a team-DPS estimate. Fewer bodies, different abilities, travel, contention, weak combat, fuel, capture sharing or enemy arrival can defeat it. Local farming improvement would not establish leader competitiveness.

## Actual delta from parent

The sole production change is in `src/objectives.cpp`, inside the actual `choose_camp` scan:

```cpp
if(clear>Config::max_clear&&!(bootstrap&&i==w.dominant_gem_camp))continue;
```

Only the cached dominant group during bootstrap bypasses this rejection. Its inherited metadata contract and preference are unchanged. Every other group and every non-bootstrap decision retain the original cutoff. Retry cooldown, blocked/risk reachability, respawn versus arrival, budget/current-round checks, eligibility bookkeeping, preferred-loop precedence and scoring are unchanged. The existing new-task caller still controls selection; no task preemption or communication was added.

`max_clear=90`, `task_limit=90`, loop phase, group definition, draft, items, combat, enemies, channels, retreat, banking and pathfinding remain unchanged. There is no future ally damage, AoE forecast, round threshold, map special case or release logging. Exemption does not promise completion within the independent task lifetime.

`tests/dominant_gems.cpp` extends inherited fixtures against the extracted production selector and actual metadata helper/canonical sort. `tests/run_native.py` changes only its temporary-directory prefix from dg01 to dt01. This report replaces the inherited report with explicit parent history and this experiment's delta.

## Checks performed on the Pi

Host: aarch64, GCC 13.3.0. Read the current leader-party strategy overview, selection/routing, navigation, state-machine, configuration and combat references, along with relevant C++ API/SDK metadata and distance-field contracts and the actual caller.

From repository root:

```sh
python3 bots/pi_dominant-team-01/tests/run_native.py
```

Passed: **84 dominant metadata / production selection assertions**, plus inherited protocol and state scenarios. Harness builds use C++20, `-O2 -Wall -Wextra -Werror`, with all generated headers/executables in a temporary directory.

Coverage includes:

- Overlong dominant admission during bootstrap in distance and value modes, including a 49-member/5880-HP fixture; rejection after bootstrap even when the loop planner requests it.
- Ordinary overlong groups rejected with the exception active; ordinary clear=90 accepted. Equal-reward, gold-bearing, each non-gem member type (including attacking types), and mixed groups use the real recomputed metadata index and production selector: clear>90 rejected in bootstrap and later, clear=90 available to the later planner.
- Overlong dominant groups still rejected during cooldown, with unreachable exported approaches, or with respawn beyond arrival; cooldown expiry and respawn exactly at arrival admitted.
- Later planner precedence/fallback, bootstrap preference, fresh/stale HP, reward-available admission, missing dominant group, no-eligible sentinel, admission failure, already-used field budget and stale-round deferral. Budget fixtures include an overlong dominant objective.
- Retained strict dominance versus equality, positive rewards, all-other-group sums including unreachable groups, mixed/member exclusions, 64-bit totals/full uint32 rewards, empty maps and canonical index after the actual production anchor sort.

```sh
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_dominant-team-01/src/*.cpp
```

Passed for every candidate translation unit against the checkout SDK. These are the inherited native compatibility flags: suppress the SDK's GCC `team team()` naming diagnostic and supply `<cmath>` externally for inherited missing includes. No SDK or unrelated source was edited. This is a syntax check, not a release link/build.

A byte comparison of all **37 inherited files** against `ef22c7f92ecab5fe76e3333ab7df3f8ec567ff9a:bots/pi_dominant-gems-01/` found changes only in `src/objectives.cpp`, the two focused test files and this report. The production diff is precisely the one condition above. Git status shows only the untracked candidate directory; no tracked modifications elsewhere. No tournaments ran; `uv` and `cambc` are unavailable on this Pi PATH.

## Gaps and frozen PC progression

The harness runs the actual selector body and metadata/sort seams with fixture SDK metadata and exported distances. It does not exercise engine distance computation, occupancy, actual risk construction, the entire World initialization, combat sharing, fuel, capture or banking. No exact-source current-engine release/WASM build, VM-fault result, match outcome or early cooperative conversion is claimed.

PC validation must first build exact-source release/current engine and require zero candidate faults. Keep source, WASM and replays. Run Vault both sides versus frozen champion and C02, matching original baseline AND dg01 receipts by map/seed/opponent/side. Inspect first dominant clear/capture/bank and per-actor participation. Require at least one candidate-owned dominant capture before round200 and at least one subsequent bank before round250. This remains much slower than leaders38–39. If no early conversion occurs, diagnose actual source task/action/fuel events and reject this exception as insufficient; do not loosen gates to rescue it.

Only after mechanism success, repeat the predeclared other two positive maps against champion/C02, both sides, then all three positive maps versus frozen D1/gold_diamond, both sides. Compare with parent and original; total wins must not fall below either in each common-opponent stage. Disclose per-map score/capture regressions. These developmental criteria are not confidence bounds.

Then run the 80-game negative-control screen: direct >=8/16, common >=31/64, zero candidate faults. Compare changed event trajectories/fuel because earlier inactive-rule code also changed outcomes. Keep 16 confirmation maps reserved. Passing these gates does not authorize upload or establish broad leader competitiveness. Future performance or capture changes require separate tests. Implementation belongs to Pi; validation/research belongs to PC; commits belong to the bridge.
