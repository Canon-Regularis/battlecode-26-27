# dp01: prune dominated camp targets before reachability

Candidate: `bots/pi_dominant-prune-01/`. Parent: `862c588a37b9b29f34e7a8100cb061a66f8022f1`, `pi_dominant-team-01` (dt01). Changes are uncommitted for the bridge; no push, upload, tournament, or champion selection change was made.

## Inheritance and bounded hypothesis

Inherited dg01 identifies the unique positive-gem, zero-gold, all-gem-cluster group whose gems strictly exceed all other groups combined, caches its canonical index, and prefers it during bootstrap after eligibility checks. Inherited dt01 admits that dominant bootstrap group despite the solo `max_clear=90` estimate. Both remain intact, including navigation, eligibility, fuel/current-round gates and independent task expiry.

Task-supplied PC evidence says dt01 admitted the opening objective but failed the early-conversion gate: Vault first captures 257/360, first bank 282, with zero faults in all four diagnostics. Champion-A central HP loss through 100 was 945 (Marcella 160, Vesper 785, Heart/Ren 0). Fish's different roster removing 5880 HP by 33 is motivation, not a controlled comparison. Official replay evidence places Marcella at (11,15), hitting camp54 (12,14) for 40 at 36, leaving 80 HP; at openings 37–44 the attack remains legal but inputs alternate rollover/end-turn without work. This identifies legal work during a release stall, not a suspended C++ callsite. These observations were supplied with the task and were not independently replayed here.

Hypothesis: after a reachable camp becomes incumbent, equal/higher HP members cannot replace it under the existing strict ranking. Testing that ranking before reachability can avoid repeated attack masks, ability construction/readiness and ability masks while preserving selection for a fixed live state. With 42 members at 120 HP followed by one at 80 HP, reachable incumbent first, selection reachability evaluations can fall 43 to 2. This is a conditional work-count prediction, not evidence that the release stall is fixed. Observation, refresh, movement goals and task expiry remain alternative explanations. The preceding attack was nonlethal; post-kill retargeting is outside this window. No spell/dash changes were made.

## Actual single production delta

Only the camp-selection loop in `src/combat.cpp::fight` changes:

```cpp
if(!target&&!travel&&task>=0)for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()) {
    const float candidate_hp=c.health();
    if(candidate_hp<hp&&reachable(c,false)){selected_camp=c;hp=candidate_hp;}
}
```

Visibility still precedes alive, and both precede HP. Each living visible candidate's HP is sampled once within that iteration. The strict `candidate_hp<hp` expression precedes unchanged reachability; successful selection retains the camp handle in the existing owning `std::optional<camp>` and assigns the sampled HP. Iteration order and strict ties remain unchanged, including floating-point unordered comparisons. There is no cross-turn cache, new telemetry, instrumentation or profiler change.

Enemy selection/priority, travel/task guards, `reachable`, ability scoring, basic/cast ordering, all round/fuel guards, navigation, movement goals, dominant admission and other production code are byte-identical to dt01. Capture-defense and passive-threat filtering are not included. No other loop was optimized.

Test-only changes: add `tests/combat_selection.cpp` and extend `tests/run_native.py` to extract the full production fight body and run it alongside the prior ordering. The generated reference restores the exact parent camp loop; a separate comparison against the frozen Git parent confirmed that the entire generated reference fight equals the parent body. Temporary headers and binaries stay in a temporary directory.

## Pi checks and results

Host: aarch64, GCC 13.3.0. Read the current strategy overview, combat, configuration, routing, navigation and state-machine documents; reviewed SDK compatibility documentation and actual C++ camp/group/ability declarations. The SDK returns a span of stored camp wrappers; selected execution continues through the existing owning optional.

Commands from repository root:

```sh
python3 bots/pi_dominant-prune-01/tests/run_native.py
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_dominant-prune-01/src/*.cpp
```

Both passed. Native checks include the inherited **84 dominant metadata / production selector assertions**, inherited protocol/state scenarios, and **19 full production fight/reference scenarios**. Builds use C++20, `-O2 -Wall -Wextra -Werror`; the new test locally suppresses only the inherited fight body's misleading-indentation warning while including both extracted bodies unchanged. Initial compilation exposed that warning; the scoped test suppression resolved it without editing production behavior. Syntax checking covers every candidate production translation unit against the real checkout SDK, using inherited compatibility flags (`-Wno-changes-meaning` for SDK naming and external `<cmath>` for inherited includes). This is not a release link/build.

Fight scenarios compare returned action status and full attack/cast target traces to the reference, with independently expected targets. Coverage: 49 equal-HP reachable camps (first wins); 42x120 plus a late 80-HP member; unreachable low HP that must not update the incumbent; first candidates unreachable; all unreachable; hidden/dead members; strict lower ties; no attack/cast; cast-only reachability; unavailable cast readiness; basic then cast; higher-priority enemy; travel skips camps but still attacks enemies; no task; preserved channel; NaN, positive infinity and signed-zero ties. Query counters cover HP, attack masks, ability lists, readiness and ability masks. Hidden HP/alive queries assert immediately; count checks also exclude dead HP reads. Wrapper registration checks assert that action handles are live, that camp actions use retained copies rather than group-loop wrappers, and that all temporary wrappers are released after fight.

Representative counts below include action execution, including the unchanged post-action HP check. Thus basic attack-mask totals include one execution query beyond selection reachability.

| Fixture | HP prior -> dp01 | Attack masks prior -> dp01 | Ability lists / readiness / ability masks prior -> dp01 (each) |
| --- | --- | --- | --- |
| 49 equal reachable, basic | 51 -> 50 | 50 -> 2 | 0 -> 0 |
| 42x120 + late80, basic | 46 -> 44 | 44 -> 3 | 0 -> 0 |
| 42x120 + late80, cast only | 46 -> 44 | 0 -> 0 | 44 -> 3 |
| First two unreachable, third reachable | 3 -> 4 | 4 -> 4 | 0 -> 0 |
| All three unreachable, basic | 0 -> 3 | 3 -> 3 | 0 -> 0 |

Reading HP earlier adds work for unreachable members. With 43 cast-only candidates and readiness false, HP reads rise 0 to 43 while ability-list/readiness queries stay at 43 and masks stay at zero. Savings depend on the reachable incumbent and iteration order; no universal reduction is claimed. These are mock interface-query counts, not engine host-import counts or timing measurements.

Compared all 37 inherited files against the exact parent bot: changed inherited files are only `src/combat.cpp`, `tests/run_native.py`, and this report; the only added file is `tests/combat_selection.cpp`. The sole production diff is the loop above. Repository status contains only the untracked candidate directory; no files outside the candidate were modified.

## Gaps and frozen PC gates

The fight harness runs actual production selection and execution bodies with controlled SDK-shaped wrappers. Defense is a no-effect stub; readiness and SDK methods return fixture values. It does not test SDK imports, engine occupancy, visibility transitions, defense internals, suspension, fuel use, or changing live state during evaluation. Selected-target equivalence is tested for fixed state; fuel/suspension timing can change in release. The retained native runner passes; separate inherited PowerShell/Windows planner scripts were not run (they hardcode Windows tooling and repository-root output paths). No new instrumentation was added to production.

`uv` and `cambc` are unavailable on this Pi PATH. The checkout documents CLI/SDK 4.0.0; no exact CLI5/current engine3 release/WASM build, normal-fuel match, fault result, early capture/bank outcome or strength claim is available here. Mock query savings do not establish the release mechanism. The mechanism remains pending PC validation.

Freeze the following before new outcomes:

1. Review source and build exact uninstrumented release with CLI5/current engine3 and normal fuel. Keep exact source/build/replays. First run exactly Vault both sides against frozen champion and C02 (four games), matching dt01 source/map/seed/opponent conditions. Require zero candidate faults, at least one own central capture before 200 followed by an own bank before 250, and champion-A central HP loss through 100 exceeding the parent's 945. Inspect first central actions and rollovers by actor. These are minimal development gates, not leader competitiveness.
2. If any gate fails, do not expand on local wins or native query savings. Diagnose replay frames, then explicitly retain/reject the mechanism; do not assume fewer calls resolves a different cause.
3. Only after passing, repeat dt01 progression: the other two positive maps both sides versus champion/C02, then all three positive maps both sides versus D1/gold_diamond. Compare original/dg01/dt01 where available. Require no fewer wins than original or dg01 at each common-opponent stage; disclose score/capture regressions.
4. Before broad strength conclusions, the ordinary 80-game regression screen requires direct >=9/16 AND common >=35/64, zero faults. Reject below 8/16 or 31/64; intermediate results are inconclusive. Pruning applies beyond dominant maps, so this is not an inactive-rule control. Preserve the 16 confirmation maps. No server upload from diagnostics. Any cd01 interaction needs a separate candidate.

Commits and pushes belong to the bridge.
