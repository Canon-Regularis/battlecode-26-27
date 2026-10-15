# LARPBOT Evolution Checkpoint

Updated: 2026-10-14

## Objective

Pursue the objective in `docs/strategy/prompt.md`: keep improving the strongest local CAMBC 2026 bot to compete with top leaderboard teams, using disciplined challenger generations and strong local evidence. Preserve the champion. **Never submit, upload or participate officially; the user handles all official submissions.**

## Champion

- **Strongest validated generation:** G2 (`larpbot2`), canonical `bots/larpbot`.
- **Last successful champion build:** 2026-10-13; `cambc build bots/larpbot` completed.
- **Starter benchmark:** 16/18 wins across nine maps and both sides; 17,707 submitted / 18,608 collected gems, 254 deaths, zero reported faults.
- **Correct Python fuel setting:** the rulebook gives Python 25× the C++/Rust fuel quantum, so use `cambc run ... --fuel 100000` for 2,500,000 Python fuel. Historical commands using `--fuel 2500000` allowed 62,500,000 Python fuel; treat those comparisons as oversized-budget screens, not valid cap benchmarks.
- The runner exposes no seed flag. Its statistics JSON omits fuel use, but diagnostic bot stdout is retained in replay bundles; one instrumented Corners match measured a 1,416,091-fuel whole-turn high-water with profiling overhead. This is a single-map diagnostic, not a full worst-case audit.
- **Protection:** source snapshot `bots/larpbot/versions/10_larpbot2_20261013`; prior project snapshot `bots/larpbot_baseline_20261013`.

## Latest meta observation and experiments

The user reports that current leaders split units to farm, then regroup to bank gems and enter dangerous areas. Treat this as user-supplied competitive intelligence, not verified ladder data.

The user also cautions against strategy complexity and fuel-heavy decision trees. Keep the core farm/capture/bank loop small; try only a few observable conditional decisions, and require measured secured-gem value before retaining them.

- E05A selected Cassi & Issac / Stellar / Tavi with unchanged G2 play: 8/18 vs G2; 16,475 submitted / 17,886 collected; 394 deaths. Better of the two tested rosters, but not a promotion.
- E05B selected Cassi & Issac / Varg / Vendetta: 7/18; 15,069 / 16,912; 391 deaths.
- E06 pair safety threshold: 5/18; 15,310 / 16,902; 379 deaths.
- E07 high-risk pair-carrier recall: same aggregate as E05A; no measured change.
- E08/E09 rally changes were in inactive `bot.py`; their identical results are invalid as tests of coordination.
- E10's 100-gem beacon threshold had no measurable effect. E11 full-team escort at 40 gems won 1/8 and gave up scoring tempo.
- E12 one rotating escort: 7/18 against G2, with fewer deaths but fewer submitted gems. E13 escort near altar: 6/8 in a four-map pilot, but only 1/4 against the corrected carrier hunter and 2/4 against altar denial.
- E14's simple full-cycle camp-value estimate won 3/8 against G2 and submitted 1,182 fewer gems despite 53 fewer deaths. Rejected; G2 remains canonical.
- E15 in-range nonlethal carrier targeting: 4/8 against G2 and 0/4 against the carrier hunter, with lower submitted gems. Rejected; keep lethal-carrier attacks only.
- E16 shared threat/escort policy: 5/8 in its four-map G2 pilot, but 0/4 against the carrier hunter; not promoted.
- Full G2 pressure baselines now exist: 6/18 vs carrier hunter (15,461 submitted, 274 deaths) and 9/18 vs altar denial (13,437 submitted, 205 deaths); zero faults.
- E17's conditional Varg intercept: clean nine-map sweep 10/18 and +522 submitted gems versus G2, with seven fewer deaths. In full pressure suites it went 5/18 vs hunter (436 fewer gems and 14 more deaths than G2) and 10/18 vs altar denial (one extra win but 74 fewer gems and seven more deaths). Keep as a matchup hypothesis; reject as a general upgrade.
- E18–E20 altar-lock spending rules did not improve secured-gem results. E21 fixed Varg guard lost 976 submitted gems against G2 in its pilot.
- E22 safe 20-gem banking threshold exactly matched G2's ordinary four-map result and did not improve hunter performance. Keep immediate positive-bag banking.
- E23 nearby Varg guard: 5/8 vs G2 in a four-map pilot, but 0/4 against the hunter and 2/4 with fewer gems than the altar proxy. Reject; defensive escort did not protect score.
- E24 Tavi/Varg/Vendetta-first draft: 8/18 vs G2, 0/4 against the hunter and 1/4 against altar denial in pressure pilots. Reject the roster change.
- E25 Tavi emergency stun: 3/8 vs G2, 3/8 vs hunter, 3/8 vs altar denial on the common four-map pilot; it submitted fewer gems than G2 in each suite. Reject.
- E26 one Durability Health shard for Varg: full nine-map matrices gave 8/18 vs G2 with 559 fewer gems, 7/18 vs carrier hunter with 305 fewer gems than G2's matched baseline, and 11/18 vs altar denial with 339 fewer gems. Reject; the added survival investment cost too much scoring strength.
- E27 one capturer per cleared camp group: full matrices gave 10/18 vs G2, 7/18 vs carrier hunter, and 11/18 vs altar denial. Win counts improved against the matched baselines, but submitted gems fell in all three suites and deaths rose. Team stats show sharply more gems concentrated on Varg. Its rule does not account for loaded occupants leaving to bank; E28 tests whether only empty-bag allies should reserve a capture.
- E28 changed that reservation to count only empty-bag allies. All 24 pilot statistics were byte-for-byte identical to E27's four-map pilot; no observable effect. Reject and archive without a full sweep.
- E29 added one Tavi guard trigger for Varg carrying at least 50 gems under visible threat. It matched E27 byte-for-byte on the 24 G2/proxy pilot files and tied E27 directly 4/8; no measurable change. Reject and archive.
- E30 tried one safe-bank route when a champion carried at least 50 gems and saw a live enemy. On four maps and both sides it won 4/8 vs G2, 3/8 vs the carrier hunter, and 4/8 vs altar denial; each was one fewer win than E27 on the same pilot. It gained only 76 submitted gems vs altar denial and lost 288 vs the hunter. Reject; the extra route check did not deliver a broad score gain.
- Correct-cap G2 baselines (`--fuel 100000`, all nine maps and both sides): 16/18 vs starter (17,707 submitted / 18,608 collected, 254 deaths); 7/18 vs carrier hunter (14,547 / 16,058, 265 deaths); 7/18 vs altar denial (11,843 / 13,052, 190 deaths). All 54 matches reported zero faults.
- E13 altar-approach coordination at the correct cap completed all 54 matches: 10/18 vs G2, 5/18 vs hunter, 5/18 vs altar denial. It improved the G2 mirror and cut altar-denial submissions, but lost both pressure win suites and allowed more hunter score; reject as a general policy.
- E17's one-Varg intercept at the correct cap was a four-map screen: 4/8 vs G2, 1/8 vs hunter, 4/8 vs altar denial. Its hunter score fell by 804 gems against the matched G2 set; reject.
- E30 safe-bank routing at the correct cap: 3/8 vs G2, 2/8 vs hunter, 2/8 vs altar denial. It lost 716 gems in the G2 mirror and had no pressure win gain; reject.
- E05A's Cassi & Issac / Stellar / Tavi roster (unchanged G2 gameplay) completed full 18-match suites: 9/18 vs G2 (16,237 submitted / 17,564 collected; 391 deaths), 8/18 vs hunter (15,563 / 17,748; 396 deaths), 8/18 vs altar denial (11,347 / 13,728; 319 deaths), and 15/18 vs starter (16,912 / 18,580; 413 deaths). Against both pressure proxies, it beat G2's matched win count by one; it also reduced proxy submissions by 487 (hunter) and 860 (altar), but recorded over 250 more deaths across those suites. Keep as a pressure-roster challenger, not the universal champion.
- E05B's Cassi & Issac / Varg / Vendetta pilot did not improve on E05A: 2/8 vs G2, 4/8 vs hunter and 4/8 vs altar denial. Reject.
- E32 replaced multi-goal distance-field navigation with nearest-goal selection plus SDK pathfinding. Its corrected four-map/both-side E05A pilot completed cleanly but went 1/8, submitting 3,160 / collecting 3,422 with 87 deaths versus E05A's 7,680 / 8,212 and 140 deaths. Reject this shortcut: it reduced deaths but lost 4,520 secured gems. This pilot did not measure fuel; keep G2's movement core unless a simpler alternative preserves score throughput.
- E06 was rebuilt at the corrected cap and completed full 18-match suites vs G2, hunter, altar denial and starter (72 matches; zero faults). It scored 6/18 vs G2, 8/18 vs hunter, 11/18 vs altar denial and 14/18 vs starter. The altar result improved, but hunter submissions and G2/starter results regressed; Cassi/Issac deaths rose in all three pressure suites. Reject as a general survival upgrade.
- E33 limited the 50% pair retreat to low-health, bag-empty pair members with a visible enemy within four tiles. Its corrected four-map pilot completed 32 matches with zero faults: 5/8 vs E05A, 4/8 vs G2, 2/8 vs hunter and 3/8 vs altar. Reject; the trigger did not improve pressure performance.
- E34 replaced a temporary nearest-step candidate list and `min` callback with an order-preserving scan. It built and finished an 8-match actual-cap mirror screen vs E05A (5/8; 6,930 submitted, 140 deaths; zero faults), but did not establish a fuel or competitive improvement. Archive it; keep G2 unchanged.
- E36 changed only the Cassi/Issac shard purchase: complete one Strength Jungle emblem before returning to Power Strength. Its full 72-match correct-cap matrix scored 7/18 vs G2, 9/18 vs hunter, 10/18 vs altar denial, and 13/18 vs starter. Against matched E05A records, E36 gained 3 wins, 1,106 own submitted gems, and denied 399 more enemy gems across the two pressure suites, but lost 4 wins and 1,067 own submitted gems across G2 and starter. Keep it as an unpromoted pressure specialist; do not replace G2.
- E05A map breakdowns are recorded in `STRATEGY_MAP_BREAKDOWN.md`: Elkring and Expanse are weak against the hunter; Expanse is also weak against altar denial. Interlock reverses by opponent (strong vs hunter, weak vs altar). Avoid a universal retreat/escort rule for these different failure modes.
- The corrected results supersede earlier claims that every match used the actual 2,500,000 Python fuel cap. Those older matrices ran with the 25× larger Python allowance. G2 remains the protected champion. E05A and E36 are both unpromoted pressure challengers; E36 has stronger aggregate pressure scores but regresses against G2 and starter. E06 and E33 did not solve pair survival; E32 showed cheaper navigation can damage gem throughput.
- Full records and raw evidence: `bots/larpbot/EVOLUTION_LOG.md`, `bots/larpbot/COMPETITIVE_BENCHMARKS.md`, and `bots/larpbot/STRATEGY_MAP_BREAKDOWN.md`.

## Next action

1. Keep G2 protected; retain E05A and E36 as unpromoted roster/build challengers with different pressure results.
2. Preserve independent camp farming and immediate gem banking as the baseline. Before adding regrouping or denial logic, use replays to verify a specific case where two allies split poorly or a loaded carrier dies before banking.
3. Test one low-cost rule at a time. Compare secured-gem differential (our submissions minus enemy submissions), own submissions, wins, and deaths across all nine maps and both sides; reject gains that depend on one map or one proxy.
4. E35's diagnostic sample used about 51% of the Python cap at its measured peak, with profiling overhead and only four matches. The runner does not export per-turn fuel; do not claim exact savings from source size or successful runs.
5. Keep G2 unchanged, preserve useful specialist challengers, archive failed experiments, and promote only after broad improvement against G2, pressure proxies, and starter.

## Protected artifacts and housekeeping

- Canonical bot and final local package remain unchanged.
- E01 and E03–E09 rejected challengers are moved into ZIP source/results archives under `bots/archive/rejected_experiments/`; their replay bundles remain under `replays/`.
- All rejected challengers (E05B, E06, E10–E25, E27, E30–E34) and the E31 fuel diagnostic are archived under `bots/archive/rejected_experiments/`. E05A and E36 remain active as unpromoted challengers. Replays remain under `replays/`.
- E02 `bots/opponents/economic_farmer_proxy` remains available as a mixed-strength local proxy, not a champion.
- No official action has been taken.

Resume locally with `cambc build bots/larpbot` and the commands in this checkpoint after reviewing `docs/strategy/prompt.md`.

## Latest iteration — 2026-10-14

- E37 tested one conditional build choice: a 30×30 Elkring-only Jungle Strength emblem for Cassi/Issac. Its 72-match matrix tied E05A at 40/72 wins and showed a promising but unpaired Elkring score swing; the hunter suite regressed. Keep it as an unpromoted map/build hypothesis.
- E38 tested one combat condition at the actual cap. It finished 32 matches with zero faults but won 8/32 and had a -7,490 secured-gem differential. Reject and archive it; preserve G2's validated fight/farm ordering.
- Preserve the simple foundation: one low-cost condition at a time, measure both our secured gems and opponent denial, and keep the proven movement and attack/farm core unless the change improves both across multiple maps and matchups.
- G2 remains canonical and protected. No official submission or external participation occurred.
- E38 archive: `bots/archive/rejected_experiments/E38_value_attack_filter.zip`; the failed challenger directory has been removed, and all 32 local replays remain in `replays/E38_value_attack_filter/`.
- Canonical `bots/larpbot/src/*.py` still matches all seven files in the protected G2 snapshot by SHA-256.
- Next: inspect a specific replay failure for a concrete gem-throughput or carrier-denial loss, then test one small change while retaining G2's proven movement and fight/farm loop.
