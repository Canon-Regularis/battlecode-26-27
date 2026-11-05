# D1 Development Results — 2026-10-14

## D1.15 follow-up

The map-and-side draft investigation raised the direct G3 result from D1.7's 10/18 to **16/18**. The unchanged D1.15 artifact repeated the full matrix exactly: **17,985 submitted vs 15,394**, net **+2,591**, with 19,558 collected gems, 328 deaths and zero faults.

| Map | D1 wins | D1 submitted | G3 submitted | Net |
|---|---:|---:|---:|---:|
| Collision | 1/2 | 1,920 | 1,810 | +110 |
| Corners | 2/2 | 2,018 | 1,382 | +636 |
| Elkring | 2/2 | 2,034 | 1,548 | +486 |
| Expanse | 2/2 | 2,056 | 1,708 | +348 |
| Interlock | 2/2 | 2,064 | 1,790 | +274 |
| Lanes | 2/2 | 2,010 | 1,802 | +208 |
| Monolith | 2/2 | 2,014 | 1,558 | +456 |
| Packs | 1/2 | 1,834 | 1,970 | -136 |
| Rows | 2/2 | 2,035 | 1,826 | +209 |
| **Total** | **16/18** | **17,985** | **15,394** | **+2,591** |

The two remaining losses are Collision Team A (916–1,026) and Packs Team A (816–1,036). During development, focused roster changes flipped every original D1.7 loss at least once, but rebuilding changed deterministic match initialization even for unaffected roster branches. That made the identity of the losing cases move between artifacts. The runner has no seed option, so continuing until one build happened to show 18/18 would overfit an artifact-dependent local initialization rather than demonstrate universal strength.

D1.15 is frozen at `versions/03_d1_15_side_rosters`. Evidence is in `results/d1_15-full-*.json`, `results/d1_15-repeat-*.json`, `replays/D1_15_full/` and `replays/D1_15_repeat/`. No external upload or official submission occurred.

## Outcome

D1 was reworked from a 5/18 independent economy bot into a map-adaptive challenger that beat G3 **10/18** at the real Python fuel cap. The frozen source repeated the complete matrix exactly and finished both runs with a **+745 submitted-gem differential** and zero bot faults.

This meets the requested direct head-to-head threshold. D1.7 also improves on G3's carrier-hunter baseline, but regresses against altar denial. It is a validated matchup upgrade rather than an unconditional replacement for every opponent archetype. G3, its protected snapshot and its submission package were not changed.

## Final design

D1.7 retains G3's proven execution core: native distance-field movement, immediate banking, respawn-tile evacuation, camp ability handling, lethal carrier attacks and the no-empty-bag-recall simplification. The measured improvement is in the draft:

| Maps | Roster order |
|---|---|
| Collision, Expanse, Monolith, Packs, Rows | Cassi & Issac, Stellar, Tavi, Vendetta, Varg |
| Corners, Elkring, Interlock, Lanes | Tavi, Varg, Ren, Ryth, Vendetta |

The choice uses `(map width, map height, wall count)`. It is fixed before gameplay and costs negligible per-turn fuel.

## Direct G3 matrix

| Map | D1 wins | D1 submitted | G3 submitted | Net |
|---|---:|---:|---:|---:|
| Collision | 1/2 | 1,516 | 1,210 | +306 |
| Corners | 1/2 | 1,548 | 1,768 | -220 |
| Elkring | 2/2 | 2,016 | 1,656 | +360 |
| Expanse | 1/2 | 1,906 | 1,802 | +104 |
| Interlock | 0/2 | 1,746 | 2,062 | -316 |
| Lanes | 1/2 | 1,910 | 1,934 | -24 |
| Monolith | 1/2 | 1,918 | 1,640 | +278 |
| Packs | 1/2 | 1,746 | 1,720 | +26 |
| Rows | 2/2 | 2,035 | 1,804 | +231 |
| **Total** | **10/18** | **16,341** | **15,596** | **+745** |

The unchanged repeat produced the same scores, outcomes, 17,446 collected gems, 311 deaths and zero faults. Replays are under `replays/D1_7_full/` and `replays/D1_7_repeat/`; raw statistics are `results/d1_7-full-*.json` and `results/d1_7-repeat-*.json`.

## Pressure results

| Suite | D1 wins | D1 submitted | Opponent submitted | Net | D1 deaths | Faults |
|---|---:|---:|---:|---:|---:|---:|
| G3 direct | 10/18 | 16,341 | 15,596 | +745 | 311 | 0 |
| Carrier hunter | 13/18 | 17,483 | 14,566 | +2,917 | 348 | 0 |
| Altar denial | 13/18 | 12,855 | 12,114 | +741 | 260 | 0 |

Recorded G3 baselines are 12/18 and +1,578 net against the hunter, and 15/18 and +1,557 net against altar denial. D1.7 therefore gains one hunter win and +1,339 net gems, while losing two altar wins and 816 net gems. It collected more and submitted 130 more gems than G3 against altar denial, but conceded 946 more and died 68 more times.

## Experiments and diagnosis

- **D1.1 path-aware banking:** 3/8 on the four-map screen. Interlock Team B improved, but one Packs win was lost. Rejected as insufficient.
- **D1.2 stable full-cycle assignment:** 0/8. Hard commitment starved flexible local farming. Rejected.
- **D1.3 cleared-group capture commitment:** 0/8. The bot chased contested rewards, increased deaths and lost its Packs/Rows strengths. Rejected.
- **D1.4 exact G3 execution mirror:** established the strong policy floor. Full result was 9/18, with map and side sensitivity.
- **D1.5 loaded-carrier lethal intercept:** 2/8. The exception cost too much banking tempo. Rejected.
- **D1.6 universal meta roster:** 9/18, +153 net gems, 372 deaths. It won both Rows sides but lost both Corners sides.
- **D1.7 map-adaptive roster:** 10/18 and +745, reproduced exactly; retained.

Temporary `[DEBUG-D1CAP]` and `[DEBUG-D1MAP]` instrumentation was removed. The capture trace confirmed that the original D1 could clear groups without receiving their rewards, but both attempted capture/assignment fixes made the policy substantially worse. The successful route was to keep the proven simple gameplay core and adapt the low-cost draft choice by map.

## Decision and limitations

D1.7 has beaten G3 under the defined direct benchmark and passed the frozen repeat. It is the stronger local choice for this exact G3/hunter-heavy evaluation set. Do not claim a universal improvement: altar denial remains a meaningful regression, Interlock is 0/2 against G3, and the runner provides fixed map/side cases rather than randomized seeds.

Preserve D1.7 at `versions/02_d1_7_map_roster`. Keep G3 available until further work repairs the altar-denial and Interlock weaknesses without giving back the verified direct advantage. No external upload or official submission occurred.
