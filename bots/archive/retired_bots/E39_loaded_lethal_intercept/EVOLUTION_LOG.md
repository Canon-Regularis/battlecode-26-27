# LARPBOT Evolution Log

Entries are generations only after promotion; unpromoted candidates remain experiments.

## Fuel-budget calibration correction — 2026-10-14

The rulebook sets Python fuel at 25 times the C++/Rust quantum. The earlier benchmark commands used `--fuel 2500000`, which therefore allowed 62,500,000 Python fuel per turn, not the requested 2,500,000. Treat all experiment results recorded before this correction as oversized-budget exploratory evidence; they do not establish performance at the actual cap. The correct runner setting is `--fuel 100000`.

The corrected G2 matrix at `--fuel 100000` reproduced its 16/18 starter result exactly, with 17,707 submitted / 18,608 collected and 254 deaths. Its full pressure baselines are 7/18 (14,547 submitted / 16,058 collected; 265 deaths) against the carrier hunter and 7/18 (11,843 / 13,052; 190 deaths) against altar denial. All 54 corrected G2 matches reported zero faults. Raw stats are in `bots/benchmark_runs/2026-10-14_python_2p5m/`; replays are in `replays/fuel_corrected_20261014/`.

One instrumented E31 Corners match at the correct cap recorded a 1,416,091-fuel whole-turn high-water and zero faults. That figure includes measurement overhead and covers one map/side only; it is a useful diagnostic, not a full worst-case fuel guarantee. The runner stores debug stdout in the replay bundle's `team-a.stdout` / `team-b.stdout` entries even though the normal CLI summary suppresses it.

## 2026-10-13

### G1 — recovered Stage 1 foundation

- **Evidence:** 14/18 versus `starter-python` across nine maps and both sides, per the preserved recovery record.
- **Distinction:** starter-derived `simple_policy`, safer recall threshold, correct attack reset/combat handling, and draft memory.
- **Status:** superseded by G2; source retained in `bots/larpbot_baseline_20261013`.

### G2 — Tavi / Varg / Ren + lethal-carrier target

- **Evidence:** 16/18 versus `starter-python` across nine maps and both sides; 17,707 submitted gems, 18,608 collected gems, 254 deaths, zero reported faults. Matched map/side suite, not independent seeded trials.
- **Distinction:** Tavi/Varg/Ren draft priority and lethal-only basic-attack priority against enemy gem carriers.
- **Head-to-head:** 3/4 against the saved G1 baseline on Corners and Interlock; small, deterministic suite.
- **Known weakness:** Interlock A lost 560–1,028; Monolith A lost 856–1,016 in the starter matrix. G2 completed the corrected Python-cap matrix with zero reported faults; see the calibration correction at the top of this log.
- **Status:** current champion at `bots/larpbot`; complete source snapshot at `bots/larpbot/versions/10_larpbot2_20261013`.

### Experiment E01 — visible-ally camp deconfliction (`larpbot3`, rejected)

- **Starting generation:** G2.
- **Hypothesis:** champions sometimes select the same nearby camp because each independently paths to the nearest camp. An allied champion visibly clearing or capturing a group is evidence that another group may yield higher team throughput.
- **Mechanism:** camp rewards are split among allies in the region at capture; extra allies do not speed the five-round capture. Claiming a nearby camp is a local signal for a soft objective assignment.
- **Change:** challenger masks goals near visible living allies; if this removes every goal, it falls back to the original policy.
- **Counterargument:** shared focus can be valuable for clearing dangerous groups, and a one-tile proximity heuristic may misidentify a claimed camp or make objectives diverge.
- **Tests/results:** build passed. Four direct G2 matches on Corners/Interlock, candidate on both sides: **0/4 wins**. Candidate totals were 1,678 submitted / 2,080 collected gems, 60 deaths and 9 kills; G2 totals were 4,038 submitted / 4,338 collected, 39 deaths and 29 kills. Both bots had zero faults. A separate Interlock A smoke match vs starter lost 542–1,030 with zero crashes; its JSON export failed because the results directory had not yet been created, so only the runner summary and replay are retained for that match.
- **Decision:** reject. This is a substantial regression on this focused set. The evidence is consistent with over-spreading reducing combat support or efficient clearing, but the summary statistics do not prove the root cause. Do not promote or claim an Interlock fix.
- **Archive:** source/config/results are in `bots/archive/rejected_experiments/E01_larpbot3.zip`; replays remain under `replays/larpbot3/`.

### Experiment E02 — parallel-farming economy proxy (`economic_farmer_proxy`)

- **Starting code:** G2 gameplay policy; proxy draft selects Tavi, Cassi & Issac, Varg, Vesper and then Ryth. The pair adds a sixth body at five picks; Vesper adds passive gold income.
- **Hypothesis:** extra map coverage plus additional gold may improve secured-gem throughput enough to justify the pair's linked-death risk.
- **Tests:** Corners and Interlock, both sides, versus `starter-python` and G2; four matches per opponent, 2,500,000 fuel per turn.
- **Results:** 2/4 against starter and 2/4 against G2. Against G2, proxy wins were Corners B (1,032–934) and Interlock A (1,006–776); G2 won Corners A (1,010–474) and Interlock B (1,000–798). Proxy had zero crashes in all eight matches. Its deaths were high (19–26 in these matches); Vesper yielded high team gold but not reliable scoring superiority.
- **Decision:** keep as a distinct local matchup proxy, but do not call it a stronger economic benchmark and do not promote it. Side/map effects are substantial and the sample is four fixed scenarios per opponent.
- **Artifacts:** source at `bots/opponents/economic_farmer_proxy`; stats in its `results/`; replays in `replays/economic_farmer_proxy/`.

### Experiment E03 — Vesper passive vs Ren (`vesper_gold`, rejected)

- **Hypothesis:** replacing Ren with Vesper preserves the G2 policy and roster size while adding a 20% gold passive; the extra upgrade income may repay the lost Ren mobility/retaliation.
- **Tests:** Corners and Interlock, both sides against G2; gameplay and shopping were unchanged; 2,500,000 fuel per turn.
- **Results:** 1/4 wins. Vesper won Corners A 1,022–662, while G2 won Corners B 1,000–482, Interlock A 1,006–876, and Interlock B 1,016–884. Zero faults. Candidate totals: 3,264 submitted gems, 3,630 collected, 62 deaths; G2: 3,684 submitted, 3,838 collected, 54 deaths. Vesper's gold did not reliably translate to scoring or survival.
- **Decision:** reject as a general roster improvement; preserve source and results. One Corners A win is not enough to promote.

### Experiment E04 — Varg Monster Strength build (`varg_monster`, rejected for universal play)

- **Hypothesis:** Monster Strength grants the same five shard stat gains as the current Power build at 150g, plus 10% camp damage; Power requires six shards for its one-extra-shard stat with no passive. Since Varg specializes in grouped camp damage, the Monster emblem may reduce clear time and camp retaliation enough to repay the weaker first five shards.
- **Change:** Varg buys Monster Strength shards; every other champion keeps the current Power Strength policy.
- **Tests:** Corners, Interlock, Expanse and Packs, both sides against G2; then Interlock both sides against starter. All matches used 2,500,000 fuel per turn; no faults.
- **G2 results:** 4/8. Candidate submitted 7,664 gems to G2's 7,668 and both teams recorded 101 deaths. Wins: Corners A, Interlock A/B, Expanse A. Losses: Corners B, Expanse B, Packs A/B. Results were near aggregate parity, not a repeatable overall gain.
- **Interlock vs starter:** 0/2 (868–1,002 as A; 950–1,028 as B). This did not repair the canonical Interlock weakness.
- **Decision:** reject for universal promotion. Preserve as a local build hypothesis; the Monster passive may be situational, but the current evidence does not justify a map-specific default either.
- **Artifacts:** `bots/archive/rejected_experiments/E04_varg_monster.zip`; replays remain under `replays/varg_monster/`.

## Promotion history

| Generation | Change | Evidence | Status |
|---|---|---|---|
| G1 | Recovery to compact camp / capture / bank policy | 14/18 starter wins (recorded) | Archived |
| G2 | Tavi/Varg/Ren draft and lethal-carrier attack | 16/18 starter wins; 3/4 focused G1 head-to-head | Champion |
| E01 | Visible-ally camp deconfliction | 0/4 vs G2 on Corners/Interlock; worse scores and survivability | Rejected; source retained |
| E02 | Parallel-farming economy proxy | 2/4 vs starter and 2/4 vs G2 on Corners/Interlock; high deaths | Mixed benchmark only; not stronger |
| E03 | Replace Ren with Vesper | 1/4 vs G2 on Corners/Interlock; 62 vs 54 deaths | Rejected; source retained |
| E04 | Varg Monster Strength emblem | 4/8 vs G2 over four maps; 0/2 vs starter on Interlock | Rejected for universal promotion |

## 2026-10-14 — E05–E09 meta and coordination follow-up

### E05A — Cassi & Issac / Stellar / Tavi roster

- Roster only; G2 gameplay unchanged; nine maps and both sides against G2; 2,500,000 fuel.
- 8/18 wins. Candidate 16,475 submitted / 17,886 collected gems, 394 deaths and 60,240 earned gold; G2 16,602 / 17,748, 265 deaths and 56,505 earned gold. Zero faults.
- Pair-specific stats: Cassi and Issac collected 5,428 and submitted 4,628 gems, with 196 combined death counts. This suggests a bag-security question but does not establish that pair deaths caused the whole-team score gap.
- Decision: do not promote. E05A is the better of these two roster screens and has two map/side wins on Collision and Packs, but the full fixed matrix does not beat G2.

### E05B — Cassi & Issac / Varg / Vendetta roster

- Roster only; G2 gameplay unchanged; same 18 G2 map/side matches and fuel.
- 7/18 wins. Candidate 15,069 submitted / 16,912 collected gems, 391 deaths and 60,985 earned gold; G2 16,254 / 16,990, 251 deaths and 55,035 earned gold. Zero faults.
- Decision: reject for general use; preserve as a composition hypothesis.

### E06 — higher no-bag recall threshold for the linked pair

- Compared the 50%-health recall rule for empty-bag Cassi/Issac to the G2 baseline over all nine maps and both sides.
- 5/18 wins; 15,310 submitted / 16,902 collected gems and 379 deaths, versus G2's 16,887 / 18,040 and 264 deaths. Zero faults.
- Decision: reject. The safety rule reduced no measured scoring risk and regressed the overall result.

### E07 — low-health rich-bag recall for Cassi/Issac

- Started from E05A. Only linked-pair carriers with at least 100 gems, below 50% health and outside immediate altar range recalled early.
- 8/18 wins; the complete aggregate exactly matched E05A: 16,475 submitted / 17,886 collected and 394 deaths versus G2's 16,602 / 17,748 and 265. Zero faults.
- Decision: no measurable improvement in this matrix; archive. The rule may not have triggered often enough to affect outcomes.

### E08 — local-vision rally / escort

- Started from E05A. Empty-bag units rallied only to a visible rich carrier near an altar or visible enemy; they could attack an enemy close to the carrier first.
- **Invalid as a rally test:** the rally edits were in `bot.py`, but `src/main.py` loads `simple_policy.Bot`. The modified code never ran. The same-roster and G2 results reproduce the unchanged active policy and say nothing about rally effectiveness.

### E09 — shared-memory carrier position beacon

- Preserved the six camp-assignment bytes; used one assignment slot as the current rich-carrier marker and the last two shared bytes for its position. Empty-bag allies path to an adjacent tile; rich carriers refresh the position, and their marker clears after banking or death.
- **Invalid as a rally test:** like E08, its beacon/rally edits were in inactive `bot.py`; `src/main.py` loads `simple_policy.Bot`. Identical results are not evidence against the beacon. Future coordination tests must change the active module and verify beacon writes/reads.

### E10 — active-policy beacon at 100 gems

- Changed the loaded `simple_policy.py`; beacon threshold was 100 gems. Across Corners, Interlock, Lanes and Packs on both sides, it exactly matched G2 outcomes and aggregate statistics (4/8 team-A wins; 7,770 submitted / 8,144 collected; 106 deaths each). Zero faults.
- **Interpretation:** this threshold did not measurably activate a useful behavior. Identical results are a no-effect result, not proof that lower-threshold regrouping is ineffective.

### E11 — active full-team rally at 40 gems (rejected)

- All teammates rallied to the carrier. On the same four-map, both-side pilot against G2: 1/8 wins; 5,318 submitted / 6,654 collected and 78 deaths, versus G2's 7,954 / 8,332 and 95 deaths. Zero faults.
- **Decision:** reject this all-team escort rule. Lower deaths did not repay the large loss in secured gems.

### E12 — 20-gem rally with one rotating escort (not promoted)

- Full nine-map, both-side comparison against G2: 7/18 wins; 15,132 submitted / 16,264 collected, 204 deaths, zero faults. G2 recorded 15,665 / 16,708 and 258 deaths.
- Against the altar-denial proxy on Corners and Interlock, both sides: 1/4 wins. Survival improved against G2, but score and denial results do not support promotion.

### E13 — escort only on the altar approach (not promoted)

- Four-map, both-side G2 pilot (Corners, Interlock, Lanes, Packs): 6/8 wins; 7,788 submitted / 7,912 collected gems and 95 deaths, versus G2's 7,174 / 7,864 and 112 deaths. Zero faults. This is a promising but narrow pilot.
- Against altar denial on Corners/Interlock, both sides: 2/4 wins. Against the corrected carrier hunter: 1/4 wins (Corners A); the hunter won the other three, including both Interlock sides. Zero faults in these matches.
- **Decision:** keep unpromoted. The G2 pilot does not hold up against focused carrier pressure.

### E14 — cheap full-cycle camp utility (rejected)

- Kept G2's draft, combat, shopping, retreat and banking; changed only camp choice. A cached estimate ranked gem reward against approximate approach, clear, capture, altar-return and channel turns, then routed to one chosen group. It uses straight-line distance to group bounds and does not model obstacles or enemy pressure.
- Four-map, both-side G2 pilot (Corners, Interlock, Lanes, Packs) at 2,500,000 fuel per turn: **3/8 wins**. E14 submitted 5,406 / collected 5,570 gems and had 48 deaths; G2 submitted 6,588 / collected 6,860 and had 101 deaths. Zero faults. E14 won both Corners and Interlock B, but scored only 180 and 96 gems on the two Lanes sides.
- **Decision:** reject this version of the utility rule. Its lower death count did not repay lost economic tempo. Map variance suggests the geometric estimate and lack of target persistence can send units toward poor loops. Keep G2 canonical.

### E15 — in-range carrier attack priority (rejected)

- Kept G2 unchanged except for a single target-order rule: after lethal carrier opportunities, choose an in-range nonlethal gem carrier before another enemy champion. This spends the same attack action and adds no chase or pathfinding.
- Four-map, both-side pilot against G2: 4/8 wins, 7,332 submitted / 7,662 collected and 111 deaths, versus G2's 7,746 / 8,188 and 103 deaths. Zero faults. E15 won both Interlock sides and lost both Packs sides; side/map variation is substantial.
- Corners/Interlock, both sides against the corrected carrier-hunter proxy: 0/4; E15 submitted 2,782 gems to the proxy's 4,072, collected 3,282 to 4,284, and recorded 69 deaths to 55. Zero faults.
- **Decision:** reject as a general target-order change. Attacking a carrier with the same action was not enough to produce a scoring or pressure advantage. Keep lethal-carrier priority only.

### E16 — shared danger alert and one escort (not promoted)

- Added a round-stamped shared carrier-threat alert and conditional regrouping; otherwise one rotating escort guarded the altar approach. Restored immediate banking of any positive bag.
- Against G2 on Corners, Interlock, Lanes and Packs, both sides: 5/8 and 7,138 submitted versus G2's 7,380; deaths were 88 versus 105. Against the carrier hunter: 0/4, 2,914 submitted versus 4,030; against altar denial: 2/4, 2,082 versus 2,370. Zero faults.
- **Decision:** do not promote. Lower deaths and the altar result do not offset poor hunter performance or the G2 score gap. Raw JSON is retained with E16.

### E17 — conditional Varg carrier intercept (unpromoted)

- One healthy, empty Varg may pursue a visible enemy gem carrier only when that carrier is near a visible allied carrier. The ordinary farm loop and lethal carrier attacks remain intact.
- Clean rebuild, then nine maps and both sides against G2 at 2,500,000 fuel: **10/18 wins**, 16,929 submitted / 17,872 collected, 254 deaths versus G2's 8/18, 16,407 / 17,446 and 261 deaths. Zero faults. This is a modest positive result, but still one fixed suite.
- Full nine-map, both-side carrier-hunter matrix: **5/18 wins**, 15,025 submitted / 16,442 collected, 288 deaths versus the proxy's 13/18, 17,751 / 18,500 and 235 deaths. Zero faults. Earlier Corners/Interlock pilot was also 0/4 against this proxy.
- Full nine-map, both-side altar-denial matrix: **10/18 wins**, 13,363 submitted / 14,696 collected, 212 deaths versus the proxy's 8/18, 12,331 / 13,824 and 220 deaths. Zero faults.
- The matched G2 baselines are 6/18 vs carrier hunter (15,461 / 16,614, 274 deaths) and 9/18 vs altar denial (13,437 / 14,790, 205 deaths). E17 loses 436 submitted gems and adds 14 deaths versus G2 against the hunter; against altar denial it wins one more map, submits 74 fewer gems, and adds 7 deaths.
- **Decision:** reject as a general upgrade. It has a small win-count signal against altar denial but does not improve secured gems and regresses against the hunter. Keep the files as a matchup hypothesis and return to G2's simpler behavior.

### E18–E20 — altar-lock responses (rejected)

- E18: Tavi buys one lock and interrupts visible high-value tribute; 3/8 G2 pilot, 7,362 submitted versus 7,972; pressure outcomes matched G2's earlier pilot.
- E19: allow all champions to buy one lock; 3/8 G2 pilot, 5,522 submitted versus 5,962; 1/4 carrier-hunter wins with 1,512 submitted versus 2,590; altar-denial score tied at 1,246. Upgrade cost erased the gain.
- E20: attack a visible blocking lock only when no unlocked altar goal is available; 2/4 G2 pilot with equal 3,864 submitted, and 1/4 against altar denial (1,906 versus 2,080). This did not improve on G2 routing.
- **Decision:** reject all three as general strategy changes; preserve their source and raw matches.

### E21 — fixed Varg altar guard (not promoted)

- Replaced E13's rotating escort with Varg as the fixed escort. Against G2 on four maps and both sides: 3/8, 6,964 submitted versus 7,940. Against the carrier hunter: 2/4 (2,812 versus 3,532); against altar denial: 2/4 (1,826 versus 1,714). Zero faults.
- **Decision:** a small hunter matchup gain does not repay the G2 scoring loss. Keep G2's split-farming default.

### E22 — safe 20-gem banking threshold (rejected)

- Changed only the banking trigger: below 20 gems, continue farming unless a living visible enemy is within four tiles; otherwise bank. This is a deliberately small threshold-plus-danger rule.
- Corners, Interlock, Lanes and Packs, both sides against G2: exactly the same aggregate and outcomes as G2 (4/8, 7,770 submitted / 8,144 collected, 106 deaths). Against the carrier hunter it remained 0/4 with 3,056 submitted; against altar denial it was 1/4 with 1,906 submitted. Zero faults.
- **Decision:** reject. The rule produced no broad improvement and did not change the carrier-hunter score. Keep immediate positive-bag banking.

### E23 — nearby Varg defensive guard (rejected after pilot)

- Started from G2. Only a healthy, empty Varg within six tiles guarded a visible allied carrier when a visible enemy was within five tiles of that carrier. Varg moved beside the carrier or held if already adjacent; no enemy chase or team-wide rally.
- Four maps × both sides against G2: 5/8, 7,872 submitted / 8,166 collected, 103 deaths versus G2's 7,380 / 7,704 and 106 deaths. Zero faults.
- Corners/Interlock vs carrier hunter, both sides: 0/4, 2,982 submitted / 3,268 collected, 72 deaths versus the proxy's 4,108 / 4,226 and 54 deaths. This is slightly worse on score than the matched G2 pilot (3,056 submitted) and remains a clear hunter loss.
- Corners/Interlock vs altar denial, both sides: 2/4, 1,550 submitted / 2,058 collected, 36 deaths versus the proxy's 1,624 / 2,146 and 40 deaths. It won one more game than G2's earlier 1/4 pilot but submitted 356 fewer gems.
- **Decision:** reject. The four-map G2 gain is not robust under pressure; standing guard reduces deaths modestly but loses secured gems. Preserve the local candidate and replays as evidence against unconditional escorting.

### E24 — Varg/Vendetta-first draft (rejected)

- Kept G2 gameplay intact; changed draft priority only to Tavi, Varg, Vendetta, Ryth, Ren. This screens the user-reported Varg/Vendetta combination without adding gameplay logic.
- Nine maps × both sides against G2: **8/18**, 15,473 submitted / 16,508 collected, 264 deaths versus G2's 10/18, 16,773 / 17,912 and 248 deaths. Zero faults.
- Corners/Interlock, both sides: 0/4 against the carrier hunter (2,036 submitted / 2,478 collected, 72 deaths versus 4,072 / 4,272 and 46 deaths); 1/4 against altar denial (1,538 / 1,950, 45 deaths versus 2,062 / 2,586 and 36 deaths). Zero faults.
- **Decision:** reject as a general draft. Vendetta earlier in the order does not solve either pressure matchup and materially lowers the G2 mirror result. Popularity is a reason to test a pick, not evidence it improves our policy.

### E25 — Tavi emergency stun (rejected after pilot)

- Kept G2's roster and farm/bank policy. Only Tavi may spend her slot-1 stun on a legal visible enemy currently submitting gems or within five tiles of a visible allied carrier. No pursuit or regroup movement.
- Corners, Interlock, Lanes and Packs, both sides against G2: 3/8, 7,232 submitted / 7,758 collected, 108 deaths versus G2's 5/8, 7,572 / 7,978 and 101 deaths.
- Same four-map, both-side proxy suites: 3/8 vs carrier hunter, 6,606 submitted / 7,266 collected and 116 deaths; G2 scored 3/8, 7,116 / 7,534 and 115 deaths. Against altar denial E25 went 3/8, 5,246 / 6,164 and 85 deaths; G2 scored 4/8, 5,938 / 6,640 and 76 deaths. Zero faults.
- **Decision:** reject. Spending the stun on these visible triggers did not protect enough score to compensate for reduced farming performance. Preserve the challenger and pilot evidence; do not reserve Tavi's spell in the canonical policy.

### Simplicity and fuel note

The E22 threshold is a direct test of a low-cost conditional and had no measurable benefit. E17's modest G2 gain failed the full carrier-hunter matrix. No current challenger improves both ordinary scoring and pressure resilience. All matches used the 2,500,000 per-turn cap; exported results do not expose peak fuel, so no exact fuel savings or margin is claimed.

### E26 — one Varg Durability Health shard (rejected)

- Started from G2 and changed only Varg's first shop purchase: buy one Durability Health shard, then resume the existing Power Strength purchase rule. Varg purchased exactly one Health shard in all 18 matches; the remaining champions and farm/bank loop were unchanged.
- Built successfully; 54 matches across all nine maps and both sides, against G2, the carrier-hunter proxy and altar-denial proxy. Each match used 2,500,000 fuel per turn. Zero reported faults.
- Against G2, E26 won 8/18 and submitted 16,492 gems / collected 17,626, against G2's 10/18, 17,051 / 18,272. E26 recorded 270 deaths versus 264.
- Against the carrier hunter, E26 won 7/18, submitting 15,156 / collecting 17,068 with 299 deaths. The matched G2 full baseline was 6/18, 15,461 / 16,614 and 274 deaths. The extra win did not offset 305 fewer submitted gems and 25 more deaths.
- Against altar denial, E26 won 11/18, submitting 13,098 / collecting 14,532 with 205 deaths. The matched G2 baseline was 9/18, 13,437 / 14,790 and 205 deaths. Two extra wins came with 339 fewer submitted gems.
- **Decision:** reject. This compact purchase conditional improves win count in the two pressure suites but loses submitted gems in every full comparison and loses the direct G2 match. Archive source and raw statistics at `bots/archive/rejected_experiments/E26_varg_durability.zip`; keep replays under `replays/E26_varg_durability/`. Leave G2's all-Strength build and split-farm/bank loop canonical. Exact peak fuel remains unavailable from the CLI.

### E27 — one capturer per cleared camp group (unpromoted)

- Started from G2. Only when a group is visibly `RewardAvailable`, one allied occupant remains to finish its fixed five-round capture; others occupying or approaching it farm another available group. If several allies already occupy the group, the lowest engine handle remains. The condition does not check carried gems, although G2's immediate-bank behavior makes a loaded occupant leave. No team memory, custom route search, or banking changes.
- Full nine-map, both-side matrices (54 matches) at 2,500,000 fuel per turn; zero reported faults. Against G2: 10/18, 15,990 submitted / 17,080 collected, 273 deaths versus G2's 8/18, 16,069 / 16,868, 244 deaths. Against the carrier hunter: 7/18, 15,242 / 17,158, 314 deaths; the matched G2 baseline was 6/18, 15,461 / 16,614, 274 deaths. Against altar denial: 11/18, 13,204 / 14,990, 244 deaths; G2's baseline was 9/18, 13,437 / 14,790, 205 deaths.
- This is a mixed signal: E27 adds one or two proxy wins and two G2 head-to-head wins, but submits fewer gems and records more deaths in every comparison. Team stats show a large shift toward Varg (7,280 gems collected vs G2 Varg's 4,946) and away from Tavi (1,260 vs 2,039). Concentrating payouts may create a richer carrier without enough survival support.
- E27 collected more total gems than the matched G2 pressure baselines (17,158 vs 16,614 against the hunter; 14,990 vs 14,790 against altar denial) but submitted fewer. This is consistent with a conversion/survival bottleneck, though end stats do not establish the cause.
- **Decision:** do not promote. The rule may cause empty allies to avoid a camp whose loaded occupant will leave to bank. Keep G2 canonical and test this specific capture-handoff issue in E28.

### E28 — empty-bag capture owner (no measurable effect)

- Started from E27 and changed only the capture reservation check: an allied occupant blocks other farmers only if that occupant has no carried gems. This accounts for G2's immediate-bank behavior when loaded allies leave.
- Four maps × both sides against G2, carrier hunter and altar denial (24 matches) at 2,500,000 fuel per turn; zero reported faults.
- The 24 exported statistics JSON files are byte-for-byte identical to E27's matching pilot files. There was no observable strategy change in this set.
- **Decision:** reject as a no-op and do not expand it to nine maps. Archive source and results at `bots/archive/rejected_experiments/E28_empty_bag_capturer.zip`; preserve replays under `replays/E28_empty_bag_capturer/`.

### E29 — Tavi guards a threatened Varg carrier (no measurable effect)

- Started from E27. Empty-bag Tavi moves beside visible Varg when Varg carries at least 50 gems and a visible enemy is within five tiles. This is one local guard trigger; it adds no team memory or custom path search.
- Built successfully; 32 matches on Corners, Interlock, Lanes and Packs, both sides, against G2, E27 and both pressure proxies. All used 2,500,000 fuel per turn; zero reported faults.
- The 24 files against G2 and pressure proxies are byte-for-byte identical to E27's matching pilot statistics. The direct E27 comparison tied 4/8, with equal submitted gems (7,452), collected gems (7,976) and deaths (105).
- **Decision:** reject without a full sweep. Archive source/results at `bots/archive/rejected_experiments/E29_varg_carrier_guard.zip`; keep replays under `replays/E29_varg_carrier_guard/`.

### E30 — threat-avoiding bank route (rejected)

- Started from G2. Only a champion carrying at least 50 gems with a visible living enemy tried a return route that blocked tiles within the enemy's attack range plus two. If the safe route could not advance, it fell back to G2's normal bank route. No draft, farm, combat, shopping, or retreat behavior changed.
- Built successfully; 24 matches on Corners, Interlock, Lanes and Packs, both sides, against G2, the carrier hunter and altar denial. All used 2,500,000 fuel per turn and reported zero bot faults.
- Against G2, E30 went 4/8 and submitted 7,770 / collected 8,144, with 106 deaths. The matched E27 pilot went 5/8 and submitted 7,330 / collected 7,698, with 98 deaths.
- Against the carrier hunter, E30 went 3/8 and submitted 7,138 / collected 7,556, with 115 deaths. E27 went 4/8 and submitted 7,426 / collected 8,246, with 126 deaths.
- Against altar denial, E30 went 4/8 and submitted 5,938 / collected 6,640, with 76 deaths. E27 went 5/8 and submitted 5,862 / collected 6,688, with 86 deaths.
- **Decision:** reject. The rule lost one win in every suite; the small score gain against altar denial did not offset lower hunter score. Fewer deaths in two suites did not translate into more wins. Archive source and statistics at `bots/archive/rejected_experiments/E30_safe_banking_route.zip`; keep replays under `replays/E30_safe_banking_route/`. Leave G2 unchanged.

### Updated simplicity constraint

The user advises against stacking plans or expensive decision logic. Keep the compact G2 loop as the baseline, measure the cost or failure in the core cycle, and add a conditional only for an observable situation when its score benefit can repay its movement, action and computation cost. E30's threat-aware route was already a narrow exception, but its results did not justify keeping the extra route work. Before another behavioral rule, inspect the current core for a measurable repeated cost and prefer a smaller algorithmic improvement if supported by evidence.

## Updated strategic direction

**Updated decision rule:** E08/E09 modified an inactive module and are invalid rally tests. E10–E13 changed the active policy: full-team escort reduced deaths but lost gem throughput, while conditional escort has not held up against carrier hunters. E14's cheap full-cycle estimate also lost economic tempo. Use net secured gems per action: farm independently by default, and spend movement/attack actions on regrouping or denial only when expected enemy gems prevented or carrier value secured can repay the farming tempo. Favor small conditional rules with observable triggers. Keep G2 canonical until a challenger improves across broad map/side and pressure matchups.

The initial E08/E09 coordination plan was invalidated by an inactive-code-path audit. E10–E13 exercised the active module; E14 tested compact camp-cycle ranking; E15 tested same-action carrier target priority. Across these trials, avoiding lost farm tempo mattered more than reducing deaths alone. See the result summaries above and `COMPETITIVE_BENCHMARKS.md`. G2 remains canonical.

## Correct-cap follow-up — 2026-10-14

All matches below used `--fuel 100000`, which supplies the actual 2,500,000 Python fuel cap under the rulebook's 25× language multiplier. Each suite covered the stated maps and both team sides. The fixed map/side scenarios have no exposed seed control.

### G2 corrected baselines

- Against `starter-python`, G2 reproduced 16/18 wins, 17,707 submitted / 18,608 collected gems, 254 deaths, and zero faults.
- Against the full-map carrier-hunter proxy, G2 scored 7/18, submitted 14,547 / collected 16,058, and recorded 265 deaths. The proxy submitted 16,295 / collected 17,058 with 233 deaths.
- Against the full-map altar-denial proxy, G2 scored 7/18, submitted 11,843 / collected 13,052, and recorded 190 deaths. The proxy submitted 13,471 / collected 14,936 with 207 deaths.
- All 54 corrected G2 baseline matches completed with zero faults. Raw stats and replays are under `bots/benchmark_runs/2026-10-14_python_2p5m/` and `replays/fuel_corrected_20261014/`.

### E13 — altar-approach regroup at the actual cap (rejected)

- Full nine-map matrices completed with zero faults. E13 went 10/18 against G2 (16,932 submitted / 17,760 collected, 231 deaths), but only 5/18 against each pressure proxy. Against the hunter it submitted 14,404 / collected 16,104 with 282 deaths; against altar denial it submitted 11,476 / collected 13,106 with 168 deaths.
- Matched G2 pressure results were 7/18 in each suite. E13 allowed the hunter 17,215 submitted gems versus G2's matched 16,295; it reduced altar-denial submissions to 11,677 versus G2's 13,471. It has a denial signal against altar denial but loses both proxy win suites and its own secured gems against altar denial. Do not promote it universally.

### E17 — one Varg intercept at the actual cap (rejected)

- Four-map pilot (Corners, Interlock, Lanes, Packs), both sides, zero faults. E17 scored 4/8 against G2 (7,344 submitted / 7,712 collected, 99 deaths); 1/8 against the carrier hunter (5,800 / 6,518, 111 deaths); and 4/8 against altar denial (5,608 / 6,508, 86 deaths).
- On the same pressure maps, G2 scored 2/8 against each proxy and submitted 6,604 against the hunter and 5,566 against altar denial. The intercept rule lost 804 submitted gems against the hunter and gained only 42 against altar denial. Reject the extra pursuit behavior.

### E30 — safe-bank route at the actual cap (rejected)

- Four-map pilot on the same maps/sides, zero faults. E30 scored 3/8 against G2 (7,130 submitted / 7,552 collected, 101 deaths), 2/8 against the hunter (6,254 / 6,750, 106 deaths), and 2/8 against altar denial (5,744 / 6,448, 95 deaths).
- Matched G2 pressure pilots scored 2/8 in both suites, submitting 6,604 against the hunter and 5,566 against altar denial. E30 gained 178 submitted gems against altar denial but lost 350 to the hunter and 716 in its direct G2 matchup. Reject the route rule.

### E05A — Cassi & Issac / Stellar / Tavi (pressure roster, not universal)

- Only draft priority changed; the G2 gameplay policy stayed fixed. Full nine-map suites completed with zero faults: 9/18 against G2 (16,237 submitted / 17,564 collected, 391 deaths), 8/18 against the carrier hunter (15,563 / 17,748, 396 deaths), 8/18 against altar denial (11,347 / 13,728, 319 deaths), and 15/18 against starter-python (16,912 / 18,580, 413 deaths).
- In the direct G2 mirror, submissions were nearly tied (E05A 16,237; G2 16,344) and wins tied 9/18, but E05A had 134 more deaths. Against the carrier hunter, it improved on G2's matched baseline by one win and 1,016 submitted gems while reducing the proxy's submitted gems by 487. Against altar denial, it improved on G2's win count by one and reduced proxy submissions by 860, while submitting 496 fewer of its own gems; its score differential improved by 364.
- E05A is the strongest current pressure-roster result, with a substantial death increase. Keep it as a challenger for a single linked-pair survival ablation; do not replace G2 yet. Raw stats are under `bots/challengers/E05A_meta_cassi_stellar_tavi/results/python_2p5m/`, with replays under `replays/fuel_corrected_20261014/E05A_*`.

### E05B — Cassi & Issac / Varg / Vendetta (rejected after screen)

- Four-map corrected pilot, both sides, zero faults: 2/8 against G2, 4/8 against the hunter, and 4/8 against altar denial. It submitted 6,680 / 6,180 / 6,120 gems respectively, compared with matched G2 scores of 7,764 / 6,604 / 5,566. Deaths were 160 / 156 / 133. The alternate popular roster does not show enough score benefit to continue.

### E32 — nearest-goal navigation simplification (rejected)

E32 kept E05A's roster and gameplay, replacing the all-goal distance-field plus reachable-tile scan with geometric nearest-goal selection and the SDK navigator. At the actual 2,500,000 Python fuel cap, its corrected four-map/both-side mirror pilot completed with zero faults but won 1/8 against E05A. E32 submitted 3,160 / collected 3,422 gems and had 87 deaths; E05A submitted 7,680 / collected 8,212 and had 140 deaths. Fewer deaths did not offset the 4,520-gem submission deficit. An initial version targeted occupied camp tiles and was inactive; the measured result uses a filter that excludes blocked goals. Reject this implementation and do not promote it. The CLI did not expose fuel use, so no exact fuel saving is claimed. Raw results are in the E32 archive, with replays under `replays/fuel_corrected_20261014/E32fix_E05A_*`.

The test supports a specific lesson: less pathfinding work is not an improvement if target selection damages the camp-clear/capture/bank cycle. Keep the proven G2 movement policy until an alternative preserves secured-gem throughput. Simplicity remains a design constraint, not a reason to replace a useful core algorithm without evidence.

### E06 corrected-cap validation — pair-aware retreat (not promoted)

The original E06 records used the oversized 62,500,000 Python fuel setting. To make its evidence usable, the exact 50% no-bag Cassi/Issac retreat rule was rebuilt and tested at `--fuel 100000` on all nine maps, both sides, against G2, the carrier hunter, altar denial and starter (72 matches; zero faults). Results were 6/18 vs G2 (15,470 submitted / 17,054 collected; 398 deaths), 8/18 vs hunter (15,132 / 16,946; 389 deaths), 11/18 vs altar denial (13,032 / 16,118; 414 deaths), and 14/18 vs starter (16,698 / 18,034; 409 deaths). E05A's matched full suites were 9/18, 8/18, 8/18 and 15/18 respectively.

E06 is a useful altar-denial matchup shift: it submitted 1,685 more gems and allowed 599 fewer proxy gems in that suite. It submitted 431 fewer gems against the hunter, allowed that proxy 617 more, and lost three wins in the G2 mirror. Pair deaths increased versus E05A in each pressure suite (202 vs 194 against G2, 194 vs 182 against the hunter, and 238 vs 168 against altar denial). Reject the rule as a general survival upgrade; archive complete corrected-cap evidence in `bots/archive/rejected_experiments/E06_correctcap_pair_safety.zip`.

### E33 corrected-cap screen — threatened pair retreat (rejected)

E33 retained E05A's 35% ordinary retreat and added a 50% threshold only for bag-empty Cassi/Issac when a visible enemy was within four tiles. Its four-map/both-side screen completed 32 matches against E05A, G2 and both pressure proxies with zero faults. It went 5/8 against E05A (7,040 submitted / 7,744 collected; 145 deaths), 4/8 against G2 (6,806 submitted), 2/8 against the hunter (7,246), and 3/8 against altar denial (5,486). In the matched E33-vs-G2/proxy games, those opponents submitted 7,132 / 7,878 / 6,004 gems. The added threat gate did not improve either pressure matchup; reject and archive at `bots/archive/rejected_experiments/E33_pair_threatened_recall.zip`.

### Map breakdown follow-up

The corrected E05A and G2 pressure results are summarized by map in `STRATEGY_MAP_BREAKDOWN.md`. Elkring and Expanse are E05A's repeatable carrier-hunter trouble spots; Expanse is also a loss to altar denial. Elkring differs by opponent: E05A loses sharply to the hunter but performs better than G2 against altar denial. Interlock is strong against the hunter but weak against altar denial. This matchup spread argues against applying E06's altar-specific gain as a universal retreat rule. Keep G2 canonical and E05A as an unpromoted pressure-roster challenger.
### E34 — explicit nearest-step scan (not promoted)

E34 changed only `move_towards_closest`: instead of allocating `[origin, *reachable.positions()]` and calling `min(..., key=field.get)`, it scans reachable positions and retains the first position with the lowest distance-field value. This preserves the original candidate order and strict-less-than tie handling; there is no new tactical rule. It built successfully and completed eight actual-cap (`--fuel 100000`) mirrored matches against the unchanged E05A copy on Corners, Interlock, Lanes and Packs, with zero bot faults. E34 went 5/8 and submitted 6,930 gems; E05A submitted 6,184. That small screen is not a matched comparison to the historical E05A baseline and does not establish a competitive gain. The runner exports no per-turn fuel usage, so the proposed reduction in Python list/callback overhead is not measured. The compiled artifact was 256 bytes smaller than E05A's, which is not evidence of lower runtime fuel. Reject as an unverified optimization and keep G2 unchanged. Source and eight statistics files are archived at `bots/archive/rejected_experiments/E34_loop_min_scan.zip`; replays remain in `replays/E34_loop_min_scan/`.

### E36 — Cassi/Issac Jungle Strength emblem (unpromoted pressure specialist)

E36 changed only the linked pair's shard order: buy five Strength Jungle shards to complete one Jungle Strength emblem, then resume the existing Power Strength shard. The full correct-cap matrix used `--fuel 100000` (2,500,000 Python fuel), nine maps, both sides, and four opponents: 72 matches, all with zero faults. The runner has no seed option, so map/side results are fixed samples rather than independent randomized trials.

| Opponent | E36 wins | E36 submitted / collected | E36 enemy submitted | E36 deaths | E05A wins | E05A submitted / collected | E05A enemy submitted | E05A deaths |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| G2 | 7/18 | 15,548 / 17,344 | 16,118 | 383 | 9/18 | 16,237 / 17,564 | 16,344 | 391 |
| Carrier hunter | 9/18 | 15,668 / 17,782 | 16,022 | 389 | 8/18 | 15,563 / 17,748 | 15,808 | 396 |
| Altar denial | 10/18 | 12,348 / 14,766 | 11,998 | 328 | 8/18 | 11,347 / 13,728 | 12,611 | 319 |
| Starter | 13/18 | 16,534 / 17,896 | 12,984 | 368 | 15/18 | 16,912 / 18,580 | 12,596 | 413 |

The build change improved the combined pressure suites by three wins and 1,106 own submitted gems, while reducing the pressure opponents' submissions by 399. Its pressure-suite score differential improved by 1,505 gems. It regressed against G2 and starter by four wins and 1,067 own submitted gems combined. Across all four equal-sized suites, E36 submitted 60,098 gems and conceded 57,122 (net +2,976); E05A submitted 60,059 and conceded 57,359 (net +2,700). That 276-gem aggregate edge is small and trades away the direct G2/starter results, so E36 is retained only as an unpromoted pressure specialist. Keep G2 canonical; do not generalize this build rule to every match.

Raw JSON is in `bots/challengers/E36_pair_jungle_emblem/results/`; replays are in `replays/E36_pair_jungle_emblem/`. These results measure match score and reliability, not per-turn fuel; all 72 matches had zero bot faults.

### E37 — Elkring-gated purchase conditional

E37 started from E05A and added only a 30×30 map gate for Cassi/Issac's Jungle Strength emblem. Its full 72-match correct-cap matrix had zero faults and tied E05A's total wins 40/72. The aggregate secured-gem differential was +4,386 versus E05A's +2,700, with a +1,368 Elkring map-differential swing over E05A. However, the runner exposes no seed option and outcomes differed on maps where the gate was inactive, so this is not a controlled paired comparison. E37 also lost two hunter-suite wins and conceded 990 more gems than E05A in that suite. Keep only as an unpromoted Elkring build hypothesis; do not promote G2.

### E38 — value-filtered champion attacks (rejected)

E38 changed one condition in the active fight loop: attack carriers at any health, plus any enemy when the attack is lethal; otherwise farm. Its 32-match actual-cap screen across Corners, Interlock, Lanes and Packs against G2, E05A and both pressure proxies finished with zero faults. It won 8/32, submitted 22,540 gems and conceded 30,030. It scored 1/8 vs G2, 2/8 vs E05A, 2/8 vs the carrier hunter and 3/8 vs altar denial. All wins were on Lanes and Packs; it lost every Corners and Interlock match. Reject and archive it. The change is simple but damages the scoring core on half the pilot maps, so keep G2's existing attack/farm ordering.
