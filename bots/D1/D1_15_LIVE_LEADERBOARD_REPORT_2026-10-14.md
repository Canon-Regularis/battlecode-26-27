# D1.15 Live Leaderboard Evaluation — 2026-10-14

## Result

D1.15 v4 played five unranked match groups against current leading teams. Each group used both teams' active submissions and five random maps. D1.15 lost all five groups and all **25/25 maps**.

| Opponent | Ladder position at setup | Representative roster family | Match | D1 gems | Opponent gems |
|---|---:|---|---:|---:|---:|
| hello | 1 | Cassi & Issac / Stellar / Ren | 0–5 | 598 | 5,130 |
| Mite | 2 | Cassi & Issac / Varg / Stellar | 0–5 | 1,818 | 5,140 |
| Univardisty of Shingtonwash | 3 | Cassi & Issac / Stellar / Varg/Ryth/Tavi | 0–5 | 738 | 5,124 |
| procless | 5 | Vendetta / Stellar / Ryth family | 0–5 | 1,574 | 5,102 |
| Nyxius | 7 | Varg / Vendetta / Cassi & Issac family | 0–5 | 2,088 | 5,076 |
| **Total** |  |  | **0–25** | **6,816** | **25,572** |

D1 averaged **273 submitted gems per map**, while the opponents averaged **1,023**. D1 produced only **26.7%** of the opponents' submitted total. All games completed normally, so this is a strategy failure rather than a compile or runtime failure.

## Map profile

| Map | Games | D1 average | Opponent average | Record |
|---|---:|---:|---:|---:|
| Collision | 3 | 88 | 1,026 | 0–3 |
| Corners | 3 | 125 | 1,024 | 0–3 |
| Elkring | 4 | 234 | 1,018 | 0–4 |
| Expanse | 3 | 659 | 1,028 | 0–3 |
| Interlock | 5 | 188 | 1,024 | 0–5 |
| Monolith | 4 | 302 | 1,027 | 0–4 |
| Packs | 2 | 276 | 1,014 | 0–2 |
| Lanes | 1 | 564 | 1,014 | 0–1 |

Expanse remains D1's strongest map, but even there it lost all three games. Collision is the clearest emergency: D1 averaged only 88 gems and lost by an average of 938.

## Replay findings

### Combat collapse: hello on Collision

Final visualiser analytics near round 438:

| Metric | D1.15 | hello |
|---|---:|---:|
| Gold earned | 1,450 | 3,615 |
| Gems banked | 88 | 986 |
| Champion kills | 0 | 12 |
| Camps captured | 21 | 35 |

D1 initially led 22–0 in submitted gems, but had already conceded a kill by round 42. By round 67 the opponent had three kills and had taken the score lead. The timeline then records repeated deaths of Vendetta, Cassi & Issac and Varg through round 410. D1 repeatedly returned to the same losing central interaction and never established a safe farming cycle.

The active Collision roster was Cassi & Issac / Vendetta / Varg. hello used Cassi & Issac / Stellar / Ren. D1's gameplay uses only opportunistic basic attacks against enemy champions; its damage, reset and shield ability logic is applied to camps. It therefore enters a coordinated disable and ranged-pressure matchup without a comparable PvP response.

### Economic loss without enemy kills: Mite on Expanse

This was D1's best game of the suite at 722–1,042. Visualiser analytics near round 387 showed:

| Metric | D1.15 | Mite |
|---|---:|---:|
| Gold earned | 990 | 1,330 |
| Gems banked | 722 | 972 |
| Champion kills | 0 | 0 |
| Camps captured | 21 | 29 |

Mite won through camp throughput and conversion rather than PvP kills. D1 also recorded three deaths without an enemy kill credit, consistent with camp or environmental attrition. This establishes an independent economy problem: combat avoidance alone will not close the gap.

### Combined failure: Univardisty on Monolith

Near round 406 D1 trailed 264–950 in banked gems, 2,095–4,396 in gold, 22–30 in camps and 0–9 in champion kills. D1 was simultaneously slower at resource acquisition and unable to survive contact.

## Code-level causes

1. **The active bot is the simple benchmark policy.** `src/main.py` imports `Bot` from `simple_policy.py`. The larger `D1` implementation in `src/d1.py` is inactive.
2. **Every non-empty bag triggers an immediate altar trip.** `simple_policy.py` calls `bank()` and returns whenever `gem_count() > 0`. This creates many low-value travel and channel cycles and explains why opponents can capture substantially more camps.
3. **Camp choice is nearest-goal routing.** All camps not known to be respawning are merged into one bitboard. Champions choose the closest reachable tile without reward-per-turn scoring, ownership claims, ally congestion cost or return-to-altar cost.
4. **No regrouping or carrier protection exists.** Champions neither escort loaded allies nor rally before dangerous crossings or deposits. Each champion independently farms or banks.
5. **Threat handling begins only inside attack range.** There is no projected enemy attack zone, retreat rule, health-adjusted danger score or depth limit. A zero-bag champion attacks any visible in-range enemy even when the exchange is losing.
6. **PvP ability use is missing.** Ability and shield logic in `combat.py` is driven by camps. Enemy handling in `simple_policy.py` is limited to one basic attack.
7. **Drafting is opponent-blind.** `draft.py` selects a static order from map geometry and side. It does not counter the enemy picks that are already visible during the draft.
8. **There is no decision telemetry.** The live replays contain no D1 stdout, so target changes, carried gems at death, path choices and channel interruptions cannot be measured directly.

## Recommended D1.16 sequence

### 1. Replace immediate banking with a bounded carry policy

Keep immediate banking when health is low, enemies threaten the route, the bag is old, or the champion is already near an altar. Otherwise finish a nearby high-value cycle until a tested bag threshold is reached. The threshold must be screened by map size and champion speed; one universal large bag would recreate the earlier deep-overextension problem.

### 2. Add lightweight camp claims and full-cycle scoring

Score each candidate group using expected gems and gold divided by travel, clear, capture and altar-return time. Penalise claimed camps, enemy-side depth and visible threat. Claims should expire quickly and nearest-reachable should remain the fallback. The inactive `d1.py` contains a starting claim mechanism, but its earlier hard commitment regressed, so it should be simplified rather than activated unchanged.

### 3. Add two explicit movement modes

- **Spread:** unladen champions take distinct profitable camp cycles.
- **Return:** loaded or threatened champions choose a rally/altar route; nearby allies converge when the carrier's risk exceeds a threshold.

This implements the split-to-gather and regroup-to-deposit pattern seen in the leading teams without requiring a large global planner.

### 4. Add a conservative threat gate

Before movement, estimate enemy reachable attack and disable zones. Refuse routes that enter a locally losing fight unless the expected carrier interception or objective value justifies it. Retreat toward an allied rally or altar when health, nearby numbers and carried gems make the current position negative value.

### 5. Separate camp abilities from PvP abilities

Use shields, disables, movement abilities and focus fire in enemy contact. Prioritise survival of loaded carriers and coordinated exits over low-probability basic attacks. Collision should be the first combat screen because it exposed a 0–12 kill deficit.

### 6. Make the draft responsive

Retain the low-cost map/side prior, then adjust later picks from visible opponent selections. The first counterdraft experiment should target the Cassi & Issac / Stellar / Ren family that defeated D1 5–0 and produced the 12–0 Collision kill result.

### 7. Validate in stages

1. Mite Expanse: improve camp count and gold while keeping deaths low.
2. hello Collision: stop the repeated wipe and raise banked gems above the current 88.
3. Interlock across all five opponents: verify that the generic policy transfers.
4. Repeat the same 25-map live suite, then run the local regression matrix against G3 and the proxy opponents.

Promotion should require live improvement and preservation of local results. The previous local 103/126 result did not predict current leaderboard strength.

## Match links

- Univardisty: `ddfa9bc6-7cf9-4acd-b3c9-6e9febfeacf3`
- Mite: `d524222e-6cdc-4d9d-9a92-e0b10300cd0d`
- hello: `635e7055-7e4a-46f0-a48c-a9e19a2147e8`
- procless: `19708178-e5d5-4892-a98f-dc704c0cb24b`
- Nyxius: `47e9434f-0c59-474e-9ebf-04dc877a9458`

These were unranked tests and did not affect ladder Elo.
