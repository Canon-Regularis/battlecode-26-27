# larpbot Stage 1 recovery

## Result

The active bot now wins **14 of 18** completed matches against `starter-python` in a side-balanced run: both sides on all nine maps. Two repeated runs of the same final build reproduced the same scores. The runner does not expose a seed option, and the repeated outputs are identical, so these runs establish reproducibility for this scenario set rather than independent statistical samples. All 18 matches completed and the statistics reported **zero bot faults**.

| Map | A score | B score | Gems collected A/B | Deaths A/B | Gold earned A/B | Gold spent A/B |
|---|---:|---:|---:|---:|---:|---:|
| collision | 1012–726 W | 1012–132 W | 1166 / 1012 | 20 / 6 | 5635 / 5085 | 4890 / 3240 |
| corners | 1008–566 W | 374–1002 L | 1044 / 446 | 15 / 25 | 1620 / 1800 | 870 / 1170 |
| elkring | 1026–414 W | 1008–522 W | 1134 / 1044 | 33 / 37 | 5905 / 5755 | 4800 / 4860 |
| expanse | 1046–740 W | 1026–692 W | 1046 / 1026 | 3 / 8 | 1530 / 1810 | 900 / 1140 |
| interlock | 784–1000 L | 734–1014 L | 900 / 922 | 23 / 27 | 2050 / 2250 | 1680 / 1980 |
| lanes | 1014–660 W | 982–1004 L | 1074 / 1078 | 20 / 17 | 910 / 1050 | 870 / 870 |
| monolith | 1018–946 W | 1002–308 W | 1062 / 1178 | 23 / 29 | 5640 / 6380 | 4170 / 5400 |
| packs | 1040–592 W | 1040–504 W | 1040 / 1040 | 10 / 8 | 3520 / 3370 | 3210 / 2280 |
| rows | 1001–836 W | 1023–462 W | 1056 / 1056 | 13 / 18 | 4320 / 4320 | 3720 / 3120 |

The original one-sided matrix from `STAGE1_RESULTS.md` was collision 418–1018, Corners 290–1002, Elkring 612–1008, Expanse 778–1024, Interlock 330–1010, Lanes 1018–718 W, Monolith 1018–996 W, Packs 452–1004, and Rows 66–1012: **2/9**.

The final run's raw statistics are in `results/final6_<map>_<side>.json` and the exact repeat in `results/final7_<map>_<side>.json`; runner output is in the matching `final6_logs/` and `final7_logs/` directories. The replay bundles are under `replays/larpbot/`.

## Original failures and evidence

### Draft picks fell back to random selection

**Observed:** The original baseline won 2/9 with rosters that did not follow `draft.py`'s preference. A probe showed zero draft-memory bytes. Zero memory alone did not prove picks had failed, so picks and memory were checked separately.

**Root cause:** `main.py` imported `Bot` before checking the draft phase. `Bot` pulled in the larger combat and objective modules before the draft handler could run. The draft API worked in a lightweight control; moving the gameplay import into the post-draft branch caused the intended picks to appear in completed-match statistics and restored the `LB2` draft-memory payload. The engine randomly fills selections when a draft turn fails to submit a pick, which explains the earlier inconsistent rosters. The exact fuel cost of the old import path was not recorded.

**Fix and verification:** `src/main.py` now dispatches `draft.play()` before importing a gameplay policy. Match statistics confirm the ordered picks for three, four and five selections: `[0, 2, 9]`, `[0, 2, 9, 3]`, and `[0, 2, 9, 3, 10]` (Ryth, Vendetta, Varg, then Cassi & Issac and Tavi as slots permit). A separate minimal draft control confirmed the SDK pick and draft-memory calls. The active farming policy does not need to read the body-slot metadata.

### Attack resets were skipped

**Observed:** The previous combat helper attempted an attack reset only after attacking and only if `can_attack()` was still true. A basic attack normally consumes that allowance, so the reset branch was unreachable in the intended attack-then-reset sequence.

**Fix:** `src/combat.py` now attacks first, attempts an available reset, checks the SDK action allowance, then attacks again if allowed. Varg target scoring also prefers hits with more adjacent visible camp targets. The helper remains in the active policy. The match statistics do not expose per-ability casts, so the reset's exact contribution to the win-rate change is not isolated.

### The persistent objective policy lost to its own complexity

With drafting corrected and the fixed Ryth/Vendetta/Varg-first lineup, the persistent `ObjectivePolicy` version won **9/18** in a fresh side-balanced matrix. Its measured profile showed repeated whole-map camp-state scans, repeated objective ranking, and custom cached route construction. The worst original observed turn consumed **2,495,164 / 2,500,000** fuel. Later changes reduced a Lanes sample to **2,208,340**, with a subsequent guarded sample at **2,349,769**; those measurements still left little headroom.

The simpler challenger in `src/simple_policy.py` follows the starter's proven loop: attack visible camps, route to the nearest available camp group with the SDK distance field, hold on a cleared group while its reward is available, and bank carried gems. It won **15/18** before the respawn-memory and pre-bank safety checks were added. The current policy retains this simple loop and adds targeted respawn safety.

This is strong evidence that the previous objective/navigation architecture was a major performance bottleneck. It does not isolate which individual part—target persistence, route caching, assignment sharing, or their combined fuel cost—caused the losses. The old policy remains in `src/bot.py` and `src/objectives.py` for future controlled comparisons.

### Purchase experiment: health shards

A full-map health-shard variant won **13/18**, compared with **14/18** for the final strength build. Health raised submitted gems in some Interlock and Corners trials, but regressed on Lanes and Monolith and did not solve Interlock. `PURCHASE_SHARD` is therefore back to Strength. The experiment's match data is retained as `results/health_<map>_<side>.json`.

## Current policy and correctness behavior

- Drafting is handled before gameplay modules load. The selection and roster metadata remain deterministic.
- `simple_policy.py` attacks enemies only when already in basic-attack range, banks any carried gems, recalls below 35% health away from spawn, farms visible camps, and spends available gold on Strength shards at spawn (or anywhere for Tavi).
- Camp spawn masks are cached per champion. A camp visible as respawning is excluded from route goals, and its timer is remembered after vision is lost. When a gem carrier is standing on a known respawn tile, the bot makes a legal adjacent exit toward an unlocked altar before beginning tribute. If all exits are blocked, it defers banking and retries next turn.
- The SDK's built-in `DistanceField` navigation is used for ordinary camp and altar routes. Melee champions can attack after movement when the action allowance permits.
- `combat.py` handles the available basic damage, Varg shield and attack-reset behavior. One successful ability cast per turn remains governed by the SDK action state.
- `me.set_priority()` randomizes intra-team champion order, matching the starter's behavior. The priority change was not isolated on fixed random seeds.

### Capture and respawn assessment

Capture remains implicit in the engine loop: the champion stays on the camp tile while the group reports `RewardAvailable`; the tile is removed from goals once the group reports `Respawning`. The gem totals in the final matrix confirm repeated successful collection and banking on every map, including Rows. The final results show no bot faults.

The previous build recorded 217 moves off known respawn tiles. That count described evacuations, not failed captures or harmful departures. The active policy no longer emits per-transition capture/stuck events, and `cambc --statistics` does not report capture attempts, idle turns, navigation failures, or fuel. Therefore a precise current count of abandoned captures, stuck turns, or respawn evacuations is **not available** from these match artifacts. The pre-bank tile check specifically closes the observed channel-on-respawn-tile hazard; inaccessible or overlapping hidden states still need replay-level instrumentation.

## Fuel measurement

| Build/sample | Peak observed fuel | Evidence |
|---|---:|---|
| Original Stage 1 | 2,495,164 / 2,500,000 | `STAGE1_RESULTS.md`, Monolith |
| Optimized persistent policy | 2,208,340 / 2,500,000 | Lanes profile after target/combat optimization |
| Persistent policy with later guard | 2,349,769 / 2,500,000 | Lanes profile; only about 6% headroom |
| Active simple policy | Not directly exported | `cambc --statistics` contains no fuel field; final 18 games had zero bot faults |

The active policy removes the repeated persistent-target and custom-route work, but its current peak has not been read from the replay log stream. Zero bot faults confirms that the 18 final matches completed without recorded crashes; it does **not** establish a fuel margin. A structured, retrievable fuel trace is still required before making a strong headroom claim.

## Benchmark history

| Version / experiment | Result vs starter | Interpretation |
|---|---:|---|
| Original Stage 1, one A-side game per map | 2/9 | Random fallback drafts and weak Rows/Corners/Packs throughput; see `STAGE1_RESULTS.md`. |
| Draft-fixed persistent objective policy, 9 maps × 2 sides | 9/18 | Roster fixed; complex navigation/state policy still lost half the games. |
| Starter-derived policy, before respawn memory | 15/18 | Native route-to-nearest-available-camp loop strongly improved aggregate results. |
| Strength policy with respawn memory and carrier evacuation | 14/18 | Final result reproduced in two full 18-game runs with identical map/side scores. |
| Health-shard challenger | 13/18 | Rejected after full-map regression. |

The runner's `cambc run` command exposes no seed option. Repeated exact scores indicate the same deterministic scenario per map/side; they are useful regression checks but must not be presented as independent samples.

## Remaining weaknesses

1. **Interlock is the primary gap:** 0/2 in each final matrix. The final strength run collected 900 and 922 gems for the two larpbot sides, but submitted only 784 and 734; champion deaths were 23 and 27. This is consistent with losing value between collection and tribute, but the statistics do not identify how much was lost on death versus other causes. Inspect carrying timelines and altar routes before changing the policy.
2. **Corners B remains weak:** 374 submitted against 1,002, with 25 deaths in the final run. Corners A wins in the same fixed build. This side asymmetry suggests spawn geometry, draft interaction, or route access; one result does not identify which.
3. **Lanes B is a narrow loss:** 982–1,004 with 17 deaths. The low-health respawn-tile evacuation was kept for correctness even though it costs a turn when it triggers; this single result does not prove that the safety move caused the loss.
4. **Fuel headroom and stuck/capture telemetry remain unverified** for the active policy. Add retrievable instrumentation before optimizing fuel or claiming zero stuck behavior.
5. **Draft composition is now fixed, not proven optimal.** The health build lost overall. C&I linked survivability, map-specific draft choices, and the Varg/Vendetta/Ryth contribution still need controlled composition tests.

## Failed experiments and safeguards

- The first starter-derived control accidentally seeded its distance field with an empty origin mask. It completed with zero activity. Fixing the seed to the current tile yielded a Rows win (1,001–880); that broken run is not included in performance totals.
- A static navigation mask that treated all camp spawn tiles as permanent blockers and a route expansion cap of 24 caused zero progress on Lanes. The static mask was corrected, and the cap was not used by the active policy.
- Scanning every camp state before every bank/retreat turn regressed a full matrix from 16/18 to 10/18. The scan was narrowed to the rare case where a carrier stands on a camp tile; ordinary turns retain the simpler loop.
- The health-shard build improved some losing scores but fell to 13/18 overall; Strength remains the default.

## Final assessment

Stage 1 is now a materially stronger and usable baseline: it clears the initial 75% target at 14/18 (77.8%) in a deterministic side-balanced suite, completes every match, selects the intended draft, and repeatedly clears, captures, and tributes camps. It is not ready for advanced Stage 2 PvP work yet. Interlock remains a reproducible two-sided loss, Corners B and Lanes B remain weak, and current-policy fuel/stuck/capture telemetry is incomplete. The next work should instrument carry-to-bank losses and fuel use, then make one small Interlock/Corners improvement and rerun the same matrix.
