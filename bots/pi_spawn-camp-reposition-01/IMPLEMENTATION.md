# scp01: leave camp coverage without leaving healing spawn

## Hypothesis and provenance

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, original `leader_party_tuned` champion. The bridge clone was byte-identical to that bot before editing. No bge01/bce01 changes were imported. All work is confined to this candidate directory and remains uncommitted.

The supplied original Elkring/gold_diamond/B evidence (`cd01-broad-baseline/00011.zip`, Heart6 pre-turn250/input4586/substep44) describes camp-only spawn defense with no usable enemy/camp attack target. One adjacent walking step outside visible camp basic-attack coverage, while remaining in own spawn, may release the actor into ordinary recovery and subsequent economic work. Spawn still takes camp damage; this change does not assume immunity. The supplied baseline census and rejected bge01 evidence motivate the mechanism but do not establish this candidate's performance. Replay claims were not independently reproduced on the Pi.

Read the leader-party combat, state-machine, pathfinding and combined-tuning documents, current game movement/spawn/channel rules, SDK API notes, and the checked-in C++ wrappers/imports for snapshots, movement, camps and bitboards.

## Actual change

Only three production files differ from the original champion:

- `src/bot.cpp`: in `State::defend`, capture `observe().foes.empty()` before the unchanged `fight(world,-1)` call. Only an empty entry list permits calling the new helper afterward. Killing the last enemy does not enable repositioning.
- `src/combat.h`: declare `bool spawn_camp_reposition(TurnBudget&)`.
- `src/combat.cpp`: implement the helper with local temporary data and no Memory argument or persistent cache.

The helper checks the current round and fuel strictly above reserve, invalidates observations and refreshes after combat. It requires a same-round living own-spawn snapshot, no visible foes, positive incoming and camp coverage, then checks life, channel, movement allowance and movement restriction. It captures the SDK's visible camps once into an ordered list of living, awake, positive-strength camp positions/ranges/strengths. Both origin and destinations use the same captured list and the original `incoming_at` Chebyshev/range/float summation semantics. Origin exposure must remain positive.

Candidates come directly from `s.blocked.reachable_tiles(s.pos,1)`, intersected with the exact SDK ally spawn mask, excluding self. At most eight adjacent destinations are considered. Only exactly zero incoming qualifies; deterministic `(y,x)` chooses the destination. There is no distance field, path search, dash, attack, camp assignment, outside-spawn goal, or relaxed enemy policy. Before the single `move_checked` attempt, round/fuel and life/channel/mobility/restrictions are checked again. Only actual movement returns true. A rejected hidden-blocker move gets no retry; original invalidation/error handling is retained.

Round/fuel checks surround camp retrieval, each camp record, candidate-mask construction, enumeration and candidate inspection. The round is checked again after the fuel query. These are stale-work boundaries, not atomic transactions: SDK calls can suspend internally, including calls inside unchanged `move_checked` after the helper's last guard.

No roster, item, task lifetime, camp-selection, banking, recovery, state-selection, navigation, enemy-combat, queue/channel, optional-ward, reporting or coordination policy changed. The helper does not mutate task/altar/distance/counters or spend field quota. Existing post-dispatch bookkeeping remains in place. The next ordinary turn selects its state normally.

## Pi checks

Reproduce from repository root:

```sh
python3 bots/pi_spawn-camp-reposition-01/tests/run_native.py
```

Final run on Pi: Python 3.12.3, GCC 13.3.0; all checks passed:

```text
PASS: production spawn camp helper and Bot defend integration
PASS protocol and state scenarios
PASS: all production translation units parse against unchanged real SDK (GCC -fpermissive, forced cmath for inherited includes)
```

`tests/spawn_camp_reposition.cpp` links actual production `combat.cpp`, `observations.cpp`, `bot.cpp` and `state_machine.cpp` against the unchanged real `cambc.h`/`imports.h`. Predicates and dispatch are not copied or extracted. Controlled host responses substitute the engine; unrelated shop, objective/world refresh and navigation dependencies are substituted. Unimplemented host imports are generated as fail-fast stubs in a temporary directory. The existing `tests/decisions.cpp` state/protocol suite is retained unchanged and executed separately. All build artifacts live in a temporary directory.

Covered cases:

- Wounded Heart-style origin `(27,27)`, covering camp `(26,23)` range4/strength60, occupied `(28,27)`/`(29,27)`: one walking move to `(27,28)`. Reversed host enumeration verifies explicit coordinate ranking. The helper makes one camp-list scan beyond the three scans already performed by unchanged observation code.
- Actual `Bot::play_turn()` defend dispatch, original in-range enemy attack, far visible foe veto (including the helper's fresh check), and entry enemy killed by original fight still vetoing movement.
- Actual defensive shield before movement although `fight` returns false; a shield response that spends movement prevents repositioning.
- Existing assigned task, task timestamps, blocked count, distance and exploration sentinel preservation; no economic/navigation dependency called during defend. Helper field quota remains unchanged.
- No camp exposure, zero origin exposure, outside own spawn, dead/sleeping/zero-strength camps, inactive additional camps, and origin exposure disappearing between observation and the local capture.
- All in-spawn neighbors occupied, only outside-spawn safe neighbors, lower but positive exposure, and multiple covering camps.
- Dead, all channel types, immobile, restricted, fuel exactly at reserve; fuel depletion and round rollover injected at each observed occurrence of observation/camp retrieval/camp-state collection/reachability/enumeration/life/mobility/restriction/fuel query boundaries. Guarded boundaries abort before movement. Final queries *inside* unchanged `move_checked` are explicitly excluded from the atomicity assertion.
- Hidden-blocker false return and expected bad-destination exception: one attempt, unchanged position, false helper result and observation invalidation.
- Actual healing, bank-channel and ordinary work dispatches do not trigger the helper's refresh/scan.

Initial native compilation without compatibility options rejected inherited SDK `team team()` declarations under GCC. All-source syntax checking also exposed inherited missing direct `<cmath>` includes in `objectives.cpp`/`route_plan.cpp`. The runner uses `-fpermissive -Wno-changes-meaning` and forces `<cmath>` for the all-source syntax pass only; production/SDK sources are unchanged. Initial harness runs also caught unimplemented startup/design/shared-memory imports and aborted as intended; those host substitutes were then supplied. These were native harness/compiler issues, not measured candidate VM faults. Final checks pass.

Source comparison confirms every original file other than the three listed production files is byte-identical to `leader_party_tuned`; only this report and the two focused test files were added. Repository tracked files outside the candidate have no diff.

## Limits and frozen PC handoff

The fake host uses a 32x32 linear bitboard and simple eight-neighbor reachability, with SDK spawn bounds for the stated example. It does not reproduce official chunk storage, engine collision/diagonal legality, scheduling, arbitrary instruction-level fuel suspension, healing, damage, bags, economy, death events, or future/hidden spells. It validates real wrapper signatures and production control flow, not official host legality, trajectory exposure or useful recovery. Unrelated dependency substitutes do not validate survivor/camp/bank trajectories; their production source and the original state tests remain unchanged. No WASM/CLI build, replay, tournament, upload or ranked change was performed. PC establishes official legality, fuel, zero VM faults and wins.

Keep the requested evaluation frozen: normal fuel, CLI5/currentengine3 build `96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`; source review before standard80. Require zero candidate VM faults, direct >=8/16 and common >=33/64. Lower scores reject expansion; keep all outcomes/errors and inspect unintended early divergence even if the branch appears inactive.

After screen, run exactly eight bounded development diagnostics even if screen fails: Elkring versus C02/record_guard, D1, gold_diamond on both sides (six), and Homonoliths versus C02 on both sides (two), reusing exact original cd01-broad-baseline receipts. Elkring gates:

| Opponent | Baseline A/B bank | Minimum A/B bank |
| --- | --- | --- |
| C02 | 1012 / 572 | 911 / 515 |
| D1 | 433 / 1001 | 390 / 901 |
| gold_diamond | 1012 / 979 | 911 / 882 |

Require Elkring sum >=5259 (baseline5009) and wins >=5/6, as well as every per-condition floor. Homonoliths baseline bank0/0 and wins0/1: lose no baseline win and incur zero faults. Scoreless tiebreaks do not establish economic progress.

For preselected original Elkring/gold/B, locate actual first divergence and new-branch exposure. Require a verified host-legal in-spawn zero-exposure move, preserved HP/bag accounting, and camp damage, collection or deposit by that same actor within30 rounds after recovery. No exposure is inconclusive; moving into indefinite healing/idling fails the useful-mechanism claim. Measure defense duration, resumed work, banked gems/lost bags, deaths and fuel; inspect repeated re-entry and displaced camp attacks onto teammates. Reduced damage to one actor alone is insufficient.

Numeric improvement without that mechanism is insufficient. These diagnostics are consumed development data; the original16 confirmation maps are already consumed. Do not relax gates, run broader matches or publish from this job. A separate broad design and fresh confirmation conditions may be frozen only after all gates pass. All PC gates remain pending.
