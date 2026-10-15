# D1.15 Opponent Evaluation — 2026-10-14

## Executive result

D1.15 completed 126 new matches against seven distinct local opponents at the real Python cap of 2,500,000 fuel per turn (`--fuel 100000`). It won **103/126 (81.7%)**, submitted **119,725** gems against **89,543**, produced a **+30,182** differential, and recorded **zero bot faults**.

The field contains three purpose-built strategy proxies, starter Python, and three retained competitive challengers. These are not downloaded leaderboard binaries, so this report measures breadth against the strongest local evidence rather than claiming a leaderboard win rate. Including the separately repeated G3 matrix, D1.15 is **119/144 (82.6%)** across eight opponents with a +32,773 aggregate submitted-gem differential.

## Method

- Nine official local maps.
- D1 played once as Team A and once as Team B on every map.
- Full matches at `--fuel 100000`.
- Final statistics exported for all 126 matches.
- The active source and compiled artifact were unchanged throughout the evaluation.

## Suite results

| Opponent | Strategy represented | Wins | D1 submitted | Opponent submitted | Net | D1 collected | D1 deaths | Opponent deaths | Faults |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Carrier hunter | Attacks visible loaded carriers | 14/18 | 17,743 | 14,326 | +3,417 | 20,082 | 342 | 266 | 0 |
| Altar denial | Interrupts visible submissions | 15/18 | 14,171 | 10,710 | +3,461 | 16,140 | 261 | 235 | 0 |
| Economic farmer | High-body-count Cassi/Issac economy | 15/18 | 17,543 | 14,130 | +3,413 | 18,902 | 304 | 343 | 0 |
| Starter Python | Regression floor | 17/18 | 17,515 | 9,266 | +8,249 | 18,600 | 294 | 267 | 0 |
| **Total** |  | **61/72** | **66,972** | **48,432** | **+18,540** | **73,724** | **1,201** | **1,111** | **0** |

### Competitive challenger results

| Opponent | Distinguishing strategy | Wins | D1 submitted | Opponent submitted | Net | D1 collected | D1 deaths | Opponent deaths | Faults |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E05A | Cassi/Issac, Stellar and Tavi pressure roster | 14/18 | 17,361 | 13,163 | +4,198 | 19,074 | 319 | 377 | 0 |
| E36 | Cassi/Issac Jungle Strength pressure build | 12/18 | 17,409 | 14,576 | +2,833 | 19,110 | 336 | 368 | 0 |
| E39 | Loaded-carrier lethal interception | 16/18 | 17,983 | 13,372 | +4,611 | 19,436 | 307 | 258 | 0 |
| **Total** |  | **42/54** | **52,753** | **41,111** | **+11,642** | **57,620** | **962** | **1,003** | **0** |

The E36 suite is the hardest result at 12/18. D1 still wins the aggregate economy by 2,833 gems, so E36 exposes map-specific matchups rather than a general scoring collapse. D1's 16/18 and +4,611 against E39 is especially strong because E39 was retained as the best broad non-G3 local challenger.

Against recorded G3 pressure baselines, D1.15 gains two hunter wins and +1,839 net gems (G3: 12/18, +1,578), while matching G3's 15/18 altar win count and gaining +1,904 net gems (G3: +1,557). These are fixed local matrices rather than seeded paired trials, so the comparison is directional.

## Cross-opponent map profile

Each row combines seven opponents, both sides, for 14 matches.

| Map | Wins | D1 submitted | Opponent submitted | Net |
|---|---:|---:|---:|---:|
| Collision | 13/14 | 12,362 | 5,344 | +7,018 |
| Corners | 9/14 | 11,822 | 9,402 | +2,420 |
| Elkring | 12/14 | 13,374 | 9,018 | +4,356 |
| Expanse | 14/14 | 14,392 | 10,168 | +4,224 |
| Interlock | 9/14 | 13,088 | 11,574 | +1,514 |
| Lanes | 14/14 | 14,098 | 10,796 | +3,302 |
| Monolith | 12/14 | 13,712 | 9,582 | +4,130 |
| Packs | 9/14 | 12,962 | 11,856 | +1,106 |
| Rows | 11/14 | 13,915 | 11,803 | +2,112 |

Expanse and Lanes are perfect at 14/14. Corners, Interlock and Packs are tied for the lowest win rate at 9/14; Packs has the smallest net margin. D1 went 56/63 as Team A and 47/63 as Team B, confirming that Team B remains the weaker side even after adding the challenger suites.

## Loss analysis

D1 lost 23 of the 126 matches. Sixteen losses occurred as Team B and seven as Team A, so the remaining weakness is substantially side-skewed. Corners B, Packs B and Rows A recur across both proxies and retained challengers. E36 additionally exposes Collision A, Elkring B and Interlock A sensitivity.

### Collection failures

The clearest failures happen before banking:

- Starter Corners B: D1 collected 376 versus 1,094 and lost 282–1,028.
- Economic farmer Packs B: 588 versus 1,040 collected and a 588–1,018 score.
- Altar denial Monolith B: 820 versus 1,090 collected and a 710–952 score.
- Economic farmer Monolith A: 922 versus 1,084 collected and an 834–1,018 score.
- Carrier hunter Interlock B: 950 versus 1,102 collected and a 682–1,008 score.

These cases point to camp access, clearing allocation or lost farming uptime rather than altar routing alone.

### Collection-to-submission failures

Four losses show competitive collection followed by weaker conversion:

- Carrier hunter Interlock A: D1 collected 1,304 versus 1,056, but submitted 998 versus 1,034.
- Carrier hunter Elkring B: D1 collected 1,188 versus 1,116, but submitted 990 versus 1,008.
- Carrier hunter Packs B: D1 collected 1,048 versus 1,040, but submitted 832 versus 1,040.
- Economic farmer Rows A: both collected 1,056, but D1 submitted 924 versus 1,012.

These are the best targets for replay-level work. They indicate gems lost or stranded between capture and tribute. The carrier hunter cases also show more D1 deaths, consistent with loaded carriers being caught, although final statistics cannot prove the exact death timing.

### Pressure and linked-pair cost

D1 outscores every opponent suite despite dying more than the opponent in four of seven suites. The extra deaths do not currently erase its economic advantage, but they lower conversion under hunter and altar pressure. Cassi and Issac's linked deaths amplify this risk on several side-specialized rosters.

## Assessment

D1.15 is no longer only a G3 counter. It has a positive margin against every tested opponent and at least 12/18 wins in every matrix. The strongest evidence is its combination of:

- 16/18 against G3, repeated exactly.
- 14/18 against carrier hunting.
- 15/18 against altar denial.
- 15/18 against a high-body-count economic farmer.
- 17/18 against starter Python.
- 14/18 against E05A.
- 12/18 against E36.
- 16/18 against E39.
- Zero faults across the 126 new matches.

The main remaining risk is Team B performance on Corners, Interlock and Packs, plus Rows A. The next development step should target only losses that preserve collection but fail to submit, especially hunter Interlock A/B and Packs B. A small carrier coordination or banking improvement should be screened there before any full promotion. Broad draft changes would risk giving back the perfect Expanse/Lanes records and should not be made from a single loss.

The evidence supports D1.15 as the strongest current submission candidate in this workspace. It materially exceeds G3 head-to-head, improves the recorded hunter result, matches G3's altar win count with a larger margin, and remains positive against every retained challenger. The limitation is external validity: none of these files are actual current leaderboard teams.

## Evidence

- Raw statistics: `bots/D1/results/d1_15-carrier-*.json`, `d1_15-altar-*.json`, `d1_15-farmer-*.json`, `d1_15-starter-*.json`, `d1_15-e05a-*.json`, `d1_15-e36-*.json`, and `d1_15-e39-*.json`.
- Replays: `replays/D1_15_carrier/`, `replays/D1_15_altar/`, `replays/D1_15_farmer/`, `replays/D1_15_starter/`, `replays/D1_15_e05a/`, `replays/D1_15_e36/`, and `replays/D1_15_e39/`.
- No source changes, rebuilds, uploads or official submissions were made during these suites.
