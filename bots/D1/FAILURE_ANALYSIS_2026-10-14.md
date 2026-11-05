# D1 Failure Analysis — 2026-10-14

## Executive summary

D1 is a cleanly running challenger, but it is not yet the resource-cycle optimizer described in its design plan. Its current decision loop is a compact nearest-camp policy with immediate banking and a few combat rules. It does not estimate which camp cycle will produce the most safely submitted gems, assign distinct jobs to champions, or choose deposit routes by legal path cost and risk.

The full fixed map/side matrix against G3 ended **5–13**. D1 swept Packs and Rows and won Elkring as Team B; it lost both sides on the other six maps. Two diagnostic losses show a severe economy/throughput collapse: on Collision D1 collected 22 and submitted 0 while G3 collected 1,056 and submitted 1,012; on Interlock D1 collected and submitted 144 while G3 collected 1,106 and submitted 1,026. D1 had fewer deaths in those two examples, so simply making it more aggressive is not supported by the evidence.

The right next step is to measure where its cycles stop converting into deposits, then test a small path-aware assignment and bank-choice improvement. Keep G3 canonical.

## Benchmark evidence

The matrix used the local 2,500,000 Python fuel cap, covered all nine maps with D1 on both sides, completed all 18 matches, and reported no bot faults. It is a fixed comparison, not a randomized confidence estimate; the runner has no exposed seed option.

| Map | D1 wins | Evidence |
|---|---:|---|
| Collision | 0/2 | Diagnostic Team A loss: 22 collected, 0 submitted, 5 deaths; G3: 1,056 collected, 1,012 submitted, 8 deaths. |
| Corners | 0/2 | Lost both sides; no per-match statistics were exported for the matrix. |
| Elkring | 1/2 | Won as Team B only. |
| Expanse | 0/2 | Lost both sides; no per-match statistics were exported for the matrix. |
| Interlock | 0/2 | Diagnostic Team B loss: 144 collected/submitted, 4 deaths; G3: 1,106 collected, 1,026 submitted, 9 deaths. |
| Lanes | 0/2 | Lost both sides; no per-match statistics were exported for the matrix. |
| Monolith | 0/2 | Lost both sides; no per-match statistics were exported for the matrix. |
| Packs | 2/2 | Combat-aware run: 1,092 collected, 1,000 submitted, 7 deaths, 6 kills; G3: 1,120 collected, 944 submitted, 9 deaths, 3 kills. |
| Rows | 2/2 | Won both sides in the matrix. |

The Packs results show D1 can convert a favorable local fight/economy pattern into a win. An earlier Packs run using the simpler policy scored 632 to G3's 1,012 and had 11 deaths to G3's 7. These are separate runs, so treat the contrast as directional evidence for combat value, not a controlled estimate of the effect size.

Detailed sources: [RESULTS.md](RESULTS.md), [collision-vs-G3-A.json](results/collision-vs-G3-A.json), [interlock-vs-G3-B.json](results/interlock-vs-G3-B.json), [packs-vs-G3-combat-A.json](results/packs-vs-G3-combat-A.json), and the 18 replay files under `replays/D1-G3-matrix/`.

## What D1 is not doing well

### 1. It does not rank full resource cycles

The plan specifies a cycle score that accounts for approach, clear time, capture time, altar travel, channel time, payout share, and risk. The implemented `_refresh_groups` returns a single bitboard containing spawn tiles for every group not known to be respawning. `_step_toward` then takes the nearest reachable tile from that union. There is no reward-per-turn comparison, no estimate of clear effort, and no estimate of safe return cost.

That makes the selected destination a geometric/pathfinding choice rather than an economic one. A nearby low-value, contested, already-occupied, or expensive-to-clear group can win over a safer and more productive cycle. This is a confirmed implementation gap; the available match totals do not identify which group choices caused each loss.

### 2. Champions do not split work or deliberately regroup

Each champion independently runs the same global camp-goal selection. The only deterministic coordination is turn priority rotation. D1 has no assignment memory, no local ally-occupancy penalty, and no rule to split farmers across equivalent camps or regroup carriers for a dangerous crossing or deposit.

This is especially relevant to the reported leader pattern of spreading out to gather and grouping for deposits or dangerous areas. D1 currently has neither phase. Duplicate visits and capture reward dilution are plausible consequences, but the matrix does not export objective-selection or capture-share telemetry, so these remain hypotheses rather than established causes.

### 3. Altar choice is geometric and weakly informed

When carrying gems, D1 banks immediately and selects the altar with the shortest Chebyshev distance. It skips a lock only when that altar is visible. It does not compare legal path distance, expected channel time, visible threat, bag value, or the risk of crossing opponent territory. A geometrically close altar can therefore be a poor route, and hidden lock state is inherently uncertain.

Immediate banking does protect a bag once the champion has gems, and that safety rule should not be removed on the basis of these results. The weakness is route selection and the absence of a measured exception for a nearby, low-risk high-value camp—not the basic priority to secure carried gems.

### 4. Safety is reactive, with no movement-level threat policy

D1 attacks visible enemies only if they are already in basic attack range, prioritizing a lethal carrier. It has no retreat, evade, escort, rally, or “do not continue deeper” rule. Varg's shield is conditional on low health near a visible camp, which protects a camp fight but is not a general opponent-threat response.

The two diagnostic losses do not show that excess deaths are the primary problem: D1 died less than G3 in both. They show that survival without productive capture and deposit is insufficient. On Collision, D1's Tavi collected only 22 gems and submitted none; on Interlock, all 144 collected gems were submitted, but total collection remained far below G3. This points first toward cycle throughput, assignment, or map access, with combat safety as a secondary investigation.

### 5. The policy is map-agnostic despite highly map-dependent outcomes

D1 uses the same global nearest-goal and geometric-bank rules on every map. Its 4/4 wins on Packs and Rows, 1/2 on Elkring, and 0/12 on the remaining six maps are a clear warning that the current policy transfers poorly across layouts or matchups. This does not prove map-specific scripts are required; it does show that the current generic heuristic is not robust enough.

## What the evidence does not establish

- The 5/18 score does not by itself prove whether navigation, target selection, capture dilution, altar routing, draft, or combat caused a particular map loss.
- The full matrix has outcome/replay artifacts but not per-match exported gem/death statistics for every map. Collision and Interlock diagnostic stats are individual examples, not a complete map-level breakdown.
- There is no recorded per-champion selected target, travel distance, time spent attacking/capturing, bank path, channel interruption, or carried gems at death. These gaps prevent reliable attribution of lost throughput.
- The small number of fixed map/side cases should not be presented as an estimate of expected win rate against all opponents.

## Recommended next work

1. **Instrument one representative replay per failed map before changing strategy.** Record per champion: current bag, chosen camp group, path distance, target changes, attacks, capture progress/payout, altar target, time banking, deaths with carried gems, and visible enemy proximity. Export match-level collected/submitted gems and faults for the full map/side suite.
2. **Add a small bounded assignment rule.** Keep the native distance field, but select one camp group per champion using path cost and a simple reward/occupancy adjustment. Spread champions when a nearby alternative is productive; allow regrouping when a fight, shared payout, or dangerous transit makes it valuable. Keep nearest reachable as the fallback.
3. **Make bank routing path-aware.** Compare only viable altar approaches using legal route distance and visible lock/threat information. Keep immediate securing as the default and use telemetry to decide whether a narrowly defined low-risk continuation is worth testing.
4. **Test one change at a time at the correct fuel cap.** Re-run both sides of the weak maps and then the complete 18-match matrix. Track own and opponent submitted gems, collected gems, deaths, carried gems lost, faults, and fuel. Do not promote on a Packs-only win.

## Disposition

D1 is a useful standalone baseline and map specialist, not a general upgrade over G3. Its key shortcoming is that its delivered algorithm does not implement the plan's cycle economics or coordination. Preserve the current version and G3; use instrumentation to determine whether assignment or altar routing is the first bottleneck before adding more strategy branches.
