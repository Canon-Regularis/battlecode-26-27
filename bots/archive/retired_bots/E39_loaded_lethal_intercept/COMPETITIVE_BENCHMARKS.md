# Competitive Benchmark Record

**Fuel calibration correction (2026-10-14):** Python receives 25× the C++/Rust fuel quantum. Earlier runs passed `--fuel 2500000`, which allowed 62,500,000 Python fuel per turn; treat the historical rows below as oversized-budget exploratory results. Use `--fuel 100000` for the requested 2,500,000 Python fuel. Correct-cap results are recorded in the section below. The runner exposes no seed flag, so a full map/side sweep is not an independent randomized sample. Statistics JSON reports faults but not fuel use; diagnostic stdout is retained in replay bundles.

## Current champion

| Bot | Opponent | Matrix | Wins | Gems submitted | Gems collected | Deaths | Faults |
|---|---|---:|---:|---:|---:|---:|---:|
| G2 (`bots/larpbot`) | `starter-python` | 9 maps × both sides | 16/18 | 17,707 | 18,608 | 254 | 0 |

Canonical source and protected snapshot: `bots/larpbot/src/` and `bots/larpbot/versions/10_larpbot2_20261013/`.

## Correct-cap results (`--fuel 100000`)

| Bot | Opponent | Matrix | Wins | Bot submitted / collected | Opponent submitted / collected | Deaths bot / opponent | Faults |
|---|---|---:|---:|---:|---:|---:|---:|
| G2 | starter-python | 9 maps × both sides | 16/18 | 17,707 / 18,608 | 12,596 / 13,786 | 254 / 306 | 0 |
| G2 | carrier hunter | 9 maps × both sides | 7/18 | 14,547 / 16,058 | 16,295 / 17,058 | 265 / 233 | 0 |
| G2 | altar denial | 9 maps × both sides | 7/18 | 11,843 / 13,052 | 13,471 / 14,936 | 190 / 207 | 0 |
| E05A | G2 | 9 maps × both sides | 9/18 | 16,237 / 17,564 | 16,344 / 17,534 | 391 / 257 | 0 |
| E05A | carrier hunter | 9 maps × both sides | 8/18 | 15,563 / 17,748 | 15,808 / 16,816 | 396 / 262 | 0 |
| E05A | altar denial | 9 maps × both sides | 8/18 | 11,347 / 13,728 | 12,611 / 14,292 | 319 / 204 | 0 |
| E05A | starter-python | 9 maps × both sides | 15/18 | 16,912 / 18,580 | 12,596 / 13,786 | 413 / 306 | 0 |

E05A changes draft priority only to Cassi & Issac / Stellar / Tavi; all gameplay code matches G2. Against both pressure proxies it gains one win over G2's matched baseline and improves the score differential, but it records 129–131 additional deaths. Its mirror against G2 is tied 9/18 and nearly tied on submitted gems, with 134 extra deaths. Keep it as a pressure-roster challenger while testing a minimal linked-pair survival change; do not promote yet.

Corrected G2 source and results are in `bots/benchmark_runs/2026-10-14_python_2p5m/`; E05A raw stats remain in its challenger folder. Replays for all corrected suites are under `replays/fuel_corrected_20261014/`. The E31 diagnostic copy measured a 1,416,091-fuel whole-turn high-water on one Corners side at this cap, including profiling overhead; this is not a full worst-case audit.

## Meta and coordination challengers against G2

| Experiment | Controlled change | Wins | Candidate submitted / collected | G2 submitted / collected | Deaths candidate / G2 | Faults |
|---|---|---:|---:|---:|---:|---:|
| E05A | Cassi & Issac / Stellar / Tavi draft; G2 policy | 8/18 | 16,475 / 17,886 | 16,602 / 17,748 | 394 / 265 | 0 |
| E05B | Cassi & Issac / Varg / Vendetta draft; G2 policy | 7/18 | 15,069 / 16,912 | 16,254 / 16,990 | 391 / 251 | 0 |
| E06 | E05A roster; 50% recall threshold for empty-bag linked pair | 5/18 | 15,310 / 16,902 | 16,887 / 18,040 | 379 / 264 | 0 |
| E07 | E05A roster; low-health rich-bag pair recall | 8/18 | 16,475 / 17,886 | 16,602 / 17,748 | 394 / 265 | 0 |
| E08 | Rally code was in inactive `bot.py` | Same output as E05A | — | — | — | 0 |
| E09 | Beacon code was in inactive `bot.py` | Same output as E05A | — | — | — | 0 |

E05A pair-specific cumulative stats: Cassi & Issac collected 5,428 gems and submitted 4,628; they recorded 196 combined death counts. Those totals motivate further instrumentation but do not prove the linked pair caused the team-wide score gap.

E08 and E09 are invalid rally tests: both modified `bot.py`, while `src/main.py` loads `simple_policy.Bot`. Their unchanged outcomes do not demonstrate a policy advantage or disadvantage.

## Active coordination and core-algorithm experiments

| Experiment | Matrix | Wins | Candidate submitted / collected | G2 submitted / collected | Deaths candidate / G2 | Faults |
|---|---|---:|---:|---:|---:|---:|
| E10: beacon threshold 100 | 4 maps × both sides | 4/8 | 7,770 / 8,144 | 7,770 / 8,144 | 106 / 106 | 0 |
| E11: full-team rally at 40 gems | 4 maps × both sides | 1/8 | 5,318 / 6,654 | 7,954 / 8,332 | 78 / 95 | 0 |
| E12: one rotating escort at 20 gems | 9 maps × both sides | 7/18 | 15,132 / 16,264 | 15,665 / 16,708 | 204 / 258 | 0 |
| E13: escort near altar approach | 4 maps × both sides | 6/8 | 7,788 / 7,912 | 7,174 / 7,864 | 95 / 112 | 0 |
| E14: cached gems-per-cycle group choice | 4 maps × both sides | 3/8 | 5,406 / 5,570 | 6,588 / 6,860 | 48 / 101 | 0 |
| E15: in-range carrier attack priority | 4 maps × both sides | 4/8 | 7,332 / 7,662 | 7,746 / 8,188 | 111 / 103 | 0 |

Pressure results: E13 won 2/4 versus altar denial on Corners/Interlock and 1/4 versus the corrected carrier hunter on the same maps. E12 won 1/4 against altar denial. These are small exploratory matchup samples, not promotion evidence.

E15 also went 0/4 against the corrected carrier hunter on Corners/Interlock (2,782 submitted / 3,282 collected, 69 deaths) versus the proxy's 4,072 / 4,284 and 55 deaths. Reordering in-range attacks toward nonlethal carriers did not repay its cost in this matchup.

E14 shows why death count alone is insufficient: it cut deaths by 53 in the pilot but submitted 1,182 fewer gems than G2. Its approximate loop ranking performed especially poorly on Lanes (180 and 96 candidate gems on the two sides). Keep the efficient baseline and require net secured-gem gains when adding objective logic.

## Low-cost tactical and banking follow-ups

| Experiment | Matrix | Wins | Candidate submitted / collected | G2 or proxy submitted | Deaths candidate / opponent | Faults |
|---|---|---:|---:|---:|---:|---:|
| G2 baseline | carrier hunter: 9 maps × both sides | 6/18 | 15,461 / 16,614 | 16,901 / 17,716 | 274 / 241 | 0 |
| G2 baseline | altar denial: 9 maps × both sides | 9/18 | 13,437 / 14,790 | 12,663 / 14,084 | 205 / 221 | 0 |
| E16: shared threat alert, one escort | G2: 4 maps × both sides | 5/8 | 7,138 / n/a | 7,380 | 88 / 105 | 0 |
| E17: conditional Varg intercept | G2: 9 maps × both sides | 10/18 | 16,929 / 17,872 | 16,407 | 254 / 261 | 0 |
| E17: conditional Varg intercept | carrier hunter: 9 maps × both sides | 5/18 | 15,025 / 16,442 | 17,751 | 288 / 235 | 0 |
| E17: conditional Varg intercept | altar denial: 9 maps × both sides | 10/18 | 13,363 / 14,696 | 12,331 / 13,824 | 212 / 220 | 0 |
| E17: Varg intercept | carrier hunter, 2 maps × both sides | 0/4 | 2,774 / n/a | 4,070 | 74 / 53 | 0 |
| E17: Varg intercept | altar denial, 2 maps × both sides | 2/4 | 1,832 / n/a | 1,748 | 46 / 45 | 0 |
| E18: Tavi buys one altar lock | G2: 4 maps × both sides | 3/8 | 7,362 / n/a | 7,972 | 106 / 108 | 0 |
| E19: team buys one altar lock each | G2: 4 maps × both sides | 3/8 | 5,522 / n/a | 5,962 | 88 / 77 | 0 |
| E20: clear blocking lock if no altar is open | G2: 2 maps × both sides | 2/4 | 3,864 / n/a | 3,864 | 63 / 63 | 0 |
| E21: fixed Varg altar guard | G2: 4 maps × both sides | 3/8 | 6,964 / n/a | 7,940 | 98 / 100 | 0 |
| E22: bank at 20 gems or nearby danger | G2: 4 maps × both sides | 4/8 | 7,770 / 8,144 | same as G2 | 106 / 106 | 0 |
| E22: 20-gem banking threshold | carrier hunter, 2 maps × both sides | 0/4 | 3,056 / 3,334 | 4,056 | 73 / 57 | 0 |
| E22: 20-gem banking threshold | altar denial, 2 maps × both sides | 1/4 | 1,906 / 2,428 | 2,080 | 39 / 46 | 0 |
| E23: nearby Varg defensive guard | G2: 4 maps × both sides | 5/8 | 7,872 / 8,166 | 7,380 / 7,704 | 103 / 106 | 0 |
| E23: nearby Varg defensive guard | carrier hunter: 2 maps × both sides | 0/4 | 2,982 / 3,268 | 4,108 / 4,226 | 72 / 54 | 0 |
| E23: nearby Varg defensive guard | altar denial: 2 maps × both sides | 2/4 | 1,550 / 2,058 | 1,624 / 2,146 | 36 / 40 | 0 |
| E24: Tavi/Varg/Vendetta-first draft | G2: 9 maps × both sides | 8/18 | 15,473 / 16,508 | 16,773 / 17,912 | 264 / 248 | 0 |
| E24: Tavi/Varg/Vendetta-first draft | carrier hunter: 2 maps × both sides | 0/4 | 2,036 / 2,478 | 4,072 / 4,272 | 72 / 46 | 0 |
| E24: Tavi/Varg/Vendetta-first draft | altar denial: 2 maps × both sides | 1/4 | 1,538 / 1,950 | 2,062 / 2,586 | 45 / 36 | 0 |
| E25: Tavi emergency stun | G2: 4 maps × both sides | 3/8 | 7,232 / 7,758 | 7,572 / 7,978 | 108 / 101 | 0 |
| E25: Tavi emergency stun | carrier hunter: same 4 maps × both sides | 3/8 | 6,606 / 7,266 | 7,910 / 8,252 | 116 / 98 | 0 |
| E25: Tavi emergency stun | altar denial: same 4 maps × both sides | 3/8 | 5,246 / 6,164 | 5,758 / 6,634 | 85 / 86 | 0 |
| E26: one Varg Durability Health shard | G2: 9 maps × both sides | 8/18 | 16,492 / 17,626 | 17,051 / 18,272 | 270 / 264 | 0 |
| E26: one Varg Durability Health shard | carrier hunter: 9 maps × both sides | 7/18 | 15,156 / 17,068 | G2 baseline: 15,461 / 16,614 | 299 / 274 | 0 |
| E26: one Varg Durability Health shard | altar denial: 9 maps × both sides | 11/18 | 13,098 / 14,532 | G2 baseline: 13,437 / 14,790 | 205 / 205 | 0 |
| E27: one capturer per cleared group | G2: 9 maps × both sides | 10/18 | 15,990 / 17,080 | 16,069 / 16,868 | 273 / 244 | 0 |
| E27: one capturer per cleared group | carrier hunter: 9 maps × both sides | 7/18 | 15,242 / 17,158 | G2 baseline: 15,461 / 16,614 | 314 / 274 | 0 |
| E27: one capturer per cleared group | altar denial: 9 maps × both sides | 11/18 | 13,204 / 14,990 | G2 baseline: 13,437 / 14,790 | 244 / 205 | 0 |
| E28: empty-bag capture owner | 4-map pilot, 24 matches | Same statistics JSON as E27 on all matching cases | — | — | — | 0 |
| E29: Tavi guards loaded Varg under threat | four-map G2/proxy pilot | Same statistics JSON as E27 on all 24 matching cases | — | — | — | 0 |
| E29: Tavi guards loaded Varg under threat | direct E27 comparison | 4/8 | 7,452 / 7,976 | E27: 7,452 / 7,976 | 105 / 105 | 0 |

The full G2 pressure baselines are now established: 6/18 versus the carrier hunter and 9/18 versus altar denial. E17 goes 5/18 versus the hunter, with 436 fewer submitted gems and 14 more deaths than G2; versus altar denial it goes 10/18, but submits 74 fewer gems and has seven more deaths than G2. E23's one-body guard gains 492 submitted gems in its G2 pilot but loses score to the hunter and altar proxies; its altar pilot gains one win but submits 356 fewer gems than G2's baseline pilot. E24's Tavi/Varg/Vendetta-first roster goes 8/18 versus G2 and loses both pressure pilots. E25's Tavi stun trigger trails G2 on all three four-map suites, including 692 fewer gems and one fewer win against altar denial. These rules and roster changes have matchup-specific signals but no general promotion case. E18–E20 spent economy on altar-lock responses without improving the overall score. E21 gained a little hunter resilience but lost nearly 1,000 submitted gems versus G2 in its pilot. E22 is the simple banking experiment: it exactly reproduced G2's ordinary four-map results and did not improve the hunter score, so it is rejected.

E26 buys exactly one Durability Health shard for Varg, then keeps the existing Power Strength purchase rule. The higher pressure win counts did not convert to more submitted gems, and its direct G2 matrix lost by 559 gems. Reject it and preserve G2's original build. Source and raw statistics are archived at `bots/archive/rejected_experiments/E26_varg_durability.zip`; replays remain under `replays/E26_varg_durability/`. All matches used 2,500,000 fuel per turn. The CLI result JSON contains no peak-fuel measurement; zero faults confirms successful runs, not the exact fuel margin.

E27's single-capturer rule produced a positive win-count signal but fewer submitted gems and more deaths across its full matrices. Its empty-bag refinement, E28, had no effect on the 24 tested files and is archived without a full sweep. Keep G2 canonical and require a full matched matrix for any next coordination change.

E29 added a single Tavi-to-Varg guard trigger for a large bag under visible threat. It had no measurable effect in the tested pilot and is archived without a full sweep. E27 collected more gems but failed to convert them into more submissions, so the next analysis should focus on the observed map/side conversion gaps rather than stacking escort rules.

E30 added one conditional safe route for a carrier with at least 50 gems when it could see a live enemy. On Corners, Interlock, Lanes and Packs, both sides, E30 scored 4/8 vs G2 (7,770 submitted / 8,144 collected; 106 deaths), 3/8 vs the carrier hunter (7,138 / 7,556; 115 deaths) and 4/8 vs altar denial (5,938 / 6,640; 76 deaths). The matched E27 pilot scored 5/8, 4/8 and 5/8 respectively. E30 gained 76 submitted gems against altar denial but lost 288 against the hunter; the win count fell by one in every suite. Reject the extra route logic. Raw records are archived at `bots/archive/rejected_experiments/E30_safe_banking_route.zip`; replays remain under `replays/E30_safe_banking_route/`. These fixed map/side screens are not independent randomized trials. As with the other results, zero faults confirms completion but does not reveal peak fuel use.

The next development pass follows the user's simpler-core guidance: inspect the existing farm/capture/bank path for repeated work that can be measured, then test one small algorithm change. Do not add another escort or threat model just because it sounds tactically plausible.

## Prior challenger records

### E32 — nearest-goal navigation simplification (rejected)

At `--fuel 100000` (2,500,000 Python fuel), E32 compared with E05A on Corners, Interlock, Lanes and Packs, both sides. It won 1/8 and submitted 3,160 / collected 3,422 gems with 87 deaths; E05A submitted 7,680 / collected 8,212 with 140 deaths. Both completed all matches with zero faults. E32 replaced multi-goal distance-field selection with geometric nearest-goal selection and SDK navigation. The 4,520-gem submission deficit outweighs the lower death count, so reject it. Exact fuel consumption was not exported. Source and stats are archived in `bots/archive/rejected_experiments/E32_nearest_goal_navigation.zip`; replays remain in `replays/fuel_corrected_20261014/E32fix_E05A_*`.

This test supports keeping the proven navigation core while looking for measured, low-cost improvements. Reducing computation alone is not a win if it reduces secured gems.

### E06 corrected-cap validation — pair-aware retreat (not promoted)

The exact E06 50% no-bag retreat rule was rebuilt at `--fuel 100000` and completed all nine maps, both sides, against G2, the carrier hunter, altar denial and starter (72 matches; zero faults).

| Opponent | E06 wins | Submitted / collected | Deaths | E05A wins | E05A submitted / collected | E05A deaths |
|---|---:|---:|---:|---:|---:|---:|
| G2 | 6/18 | 15,470 / 17,054 | 398 | 9/18 | 16,237 / 17,564 | 391 |
| Carrier hunter | 8/18 | 15,132 / 16,946 | 389 | 8/18 | 15,563 / 17,748 | 396 |
| Altar denial | 11/18 | 13,032 / 16,118 | 414 | 8/18 | 11,347 / 13,728 | 319 |
| Starter | 14/18 | 16,698 / 18,034 | 409 | 15/18 | 16,912 / 18,580 | 413 |

E06 improved the altar score differential (13,032 – 12,012 vs E05A's 11,347 – 12,611), but regressed against G2, the hunter and starter. Its linked-pair deaths were 202 vs G2, 194 vs the hunter and 238 vs altar denial, all higher than E05A's matching pair counts (194, 182 and 168). This does not validate earlier retreat as a general survival upgrade. Full stats are archived in `bots/archive/rejected_experiments/E06_correctcap_pair_safety.zip`; replays are `replays/fuel_corrected_20261014/E06cc_*`.

### E33 — threat-gated pair retreat (rejected)

E33 added the 50% pair retreat threshold only for bag-empty Cassi/Issac when a visible enemy was within four tiles, retaining the ordinary 35% rule otherwise. Its four-map/both-side pilot completed 32 matches with zero faults: 5/8 against E05A (7,040 submitted / 7,744 collected; 145 deaths), 4/8 against G2 (6,806 submitted), 2/8 against the hunter (7,246), and 3/8 against altar denial (5,486). The matched G2/proxy scores were 7,132 / 7,878 / 6,004. The threat gate did not improve either pressure matchup; reject it. Full pilot stats are archived in `bots/archive/rejected_experiments/E33_pair_threatened_recall.zip`, with replays under `replays/fuel_corrected_20261014/E33_*`.

The map-level breakdown of E05A versus G2 and both pressure proxies is in [STRATEGY_MAP_BREAKDOWN.md](STRATEGY_MAP_BREAKDOWN.md). It shows matchup-specific swings rather than one universally weak camp route.

| Experiment | Evidence | Status |
|---|---|---|
| E01 `larpbot3` | 0/4 vs G2 on Corners/Interlock | Rejected; archived source/results |
| E02 `economic_farmer_proxy` | 2/4 vs starter and 2/4 vs G2 on Corners/Interlock | Retained as a mixed-strength proxy only |
| E03 `vesper_gold` | 1/4 vs G2 on Corners/Interlock | Rejected; archived source/results |
| E04 `varg_monster` | 4/8 vs G2 on four maps; 0/2 vs starter on Interlock | Rejected for universal promotion; archived |

Raw JSON and candidate source snapshots are retained in `bots/archive/rejected_experiments/`. Replays remain under `replays/` in their experiment-named folders. The live roster proxy `bots/opponents/economic_farmer_proxy/` is intentionally preserved.

## Competitive intelligence

The current champion data is local. The observation that leading teams use Cassi & Issac and sometimes Stellar/Tavi or Varg/Vendetta comes from the user and has not been independently rechecked against live ladder data. No official submission, ranked challenge or account action has been performed.

## Core-efficiency ablation

### E34 — explicit nearest-step scan (not promoted)

E34 changed only the nearest-step selection implementation, preserving candidate order and tie behavior. At `--fuel 100000`, it completed eight mirrored matches against unchanged E05A on Corners, Interlock, Lanes and Packs with zero faults. E34 scored 5/8, submitting 6,930 gems with 140 deaths; E05A submitted 6,184 with 146 deaths. The small mirror screen does not compare E34 to E05A's matched G2/proxy baselines, and therefore does not establish a strategy gain. The runner has no per-turn fuel field; the WASM artifact was 256 bytes smaller, which does not prove a runtime fuel reduction. Archive source and stats: `bots/archive/rejected_experiments/E34_loop_min_scan.zip`; replays: `replays/E34_loop_min_scan/`.

### E36 — one Jungle Strength emblem for Cassi and Issac

At `--fuel 100000`, E36 completed all nine maps, both sides, against G2, the carrier hunter, altar denial and starter-python (72 matches; zero faults). Against E05A's matched full matrices, E36 scored 7/18 vs G2 (15,548 submitted / 17,344 collected; opponent 16,118; 383 deaths), 9/18 vs hunter (15,668 / 17,782; opponent 16,022; 389 deaths), 10/18 vs altar denial (12,348 / 14,766; opponent 11,998; 328 deaths), and 13/18 vs starter (16,534 / 17,896; opponent 12,984; 368 deaths).

E36's G2 baseline was 9/18 (16,237 submitted; opponent 16,344), hunter 8/18 (15,563; opponent 15,808), altar denial 8/18 (11,347; opponent 12,611), and starter 15/18 (16,912; opponent 12,596). The single purchase change gains 1,106 own submitted gems and three wins across the pressure suites, while reducing enemy submissions by 399; its pressure-suite score differential improves by 1,505. It loses 1,067 own gems and four wins across G2 and starter. Its overall secured-gem differential is only 276 above E05A across the four equal-sized suites. Keep E36 as an unpromoted pressure specialist; G2 remains canonical. Results are fixed map/side samples because the CLI exposes no seed control. Raw results: `bots/challengers/E36_pair_jungle_emblem/results/`; replays: `replays/E36_pair_jungle_emblem/`.

### E37 — Elkring-gated Jungle Strength purchase (unpromoted specialist)

E37 added one map condition to E05A's Cassi/Issac shop rule: use the Jungle Strength emblem only on Elkring, detected by its 30×30 dimensions; all other maps retain E05A's Power Strength purchases. Its 72-match correct-cap matrix (`--fuel 100000`) completed with zero bot faults. E37 scored 10/18 vs G2, 6/18 vs the carrier hunter, 9/18 vs altar denial, and 15/18 vs starter-python. Across all suites it submitted 61,323 gems and conceded 56,937 (net +4,386), versus E05A's 60,059 and 57,359 (net +2,700); both bots won 40/72.

On Elkring, E37's eight matches across all four opponents produced a +36 gem differential (6,192 submitted, 6,156 conceded), compared with E05A's -1,332 (5,778 submitted, 7,110 conceded). However, non-Elkring E37 outcomes also differ from historical E05A despite the build gate being inactive. The runner has no seed flag, so these fixed map/side samples are not controlled paired trials; treat the Elkring gain as a promising signal, not causal proof. The full matrix also shows a sharp carrier-hunter regression: 6/18 wins and 16,798 enemy gems conceded, versus E05A's 8/18 and 15,808. Keep E37 only as an unpromoted Elkring build hypothesis; G2 remains canonical. Raw results: `bots/challengers/E37_elkring_jungle_build/results/`; replays: `replays/E37_elkring_jungle_build/`.

### E38 — skip nonlethal attacks on empty-handed enemies (rejected)

E38 changed one condition in the active policy: attack an enemy champion if it carries gems, or if the attack would kill it; otherwise continue the farm loop. It was screened on Corners, Interlock, Lanes and Packs, both sides, against G2, E05A, the carrier-hunter proxy and altar-denial proxy (32 matches at `--fuel 100000`; zero faults). It won 8/32 and submitted 22,540 gems while opponents submitted 30,030. By opponent it went 1/8 vs G2 (5,920 submitted / 8,128 conceded), 2/8 vs E05A (5,886 / 7,668), 2/8 vs hunter (5,404 / 7,996), and 3/8 vs altar denial (5,330 / 6,238). It won all four Lanes games and all four Packs games but lost every Corners and Interlock game. Those narrow map wins do not offset the aggregate scoring deficit. Reject and archive the source/results; retain replay bundles at `replays/E38_value_attack_filter/`. This experiment supports keeping the core fight-and-farm loop simple, but also shows that skipping an attack is not automatically a scoring gain.

E38 archive: `bots/archive/rejected_experiments/E38_value_attack_filter.zip` preserves its source, build artifact, README and 32 result files; the failed working challenger folder was removed. Its 32 replay bundles remain under `replays/E38_value_attack_filter/`.
