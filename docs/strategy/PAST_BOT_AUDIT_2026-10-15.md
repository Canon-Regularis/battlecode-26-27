# Past bot audit — 15 October 2026

## Finding

The repository has repeatedly tested small modifications to a nearest-camp, immediate-bank policy. It has **not** established that a real local fight evaluator, coordinated withdrawal, or joint Cassi/Issac controller fails. Several experiments named after those ideas implemented much narrower rules, and two never ran their modified code. The successful local core is useful execution infrastructure, but online evidence rules out treating it as an adequate competitive strategy.

This audit reads local source, archived source, experiment records and the preserved online reports. It does not independently replay the historical matches. Reported outcomes below are recorded observations; causal explanations are marked as interpretations. ZIP citations name the internal source member so the exact implementation can be recovered without modifying the archived artifact.

## What actually ran

`bots/D1/src/main.py` imports `simple_policy.Bot`, not the larger `d1.py` implementation. The active policy merges available camp spawn tiles into one goal set, uses a native distance field, immediately banks any positive bag, and attacks an in-range enemy before farming when empty. The enemy attack branch does not compare force, escape routes, retaliation or ally arrival. Camp abilities are implemented separately in `combat.py`. D1's sophistication was primarily map/side draft choice, not coordinated gameplay. [D1 dispatcher](../../bots/D1/src/main.py), [active policy](../../bots/D1/src/simple_policy.py), [camp combat](../../bots/D1/src/combat.py).

The original strategy plan already described safe objective cycles, fight assessment, pair risk, route-aware banking and expiring assignments. Their appearance in a plan did not mean they reached the active entry point. This is the central process failure to prevent in the next implementation. [Original plan](plan.md), [live code diagnosis](../../bots/D1/D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md).

## Historical ideas and what their results really establish

| Experiment | Actual mechanism and evidence | Valid lesson |
|---|---|---|
| E08/E09 rally | Changes were made in inactive `bot.py`; `src/main.py` loaded `simple_policy`. Identical aggregates therefore did not test rally. | Prove the active behavior fires before evaluating strength. |
| E10 carrier beacon | 100-gem trigger; outcomes exactly matched unchanged G2 on the pilot. | A trigger can be effectively inert under immediate banking. Record activations. |
| E11 full escort | Empty allies converge on a carrier and idle within one tile; 40-gem banking threshold also changed. 1/8 vs G2, 5,318 vs 7,954 submitted, despite fewer deaths. | Whole-team escort can destroy farm income. This was not a clean isolation of one regroup decision. |
| E12/E13 limited escort | One rotating escort or altar-approach escort. E13's 6/8 G2 pilot became 1/4 vs carrier hunter. | Local mirror wins do not establish survival under a stronger pressure style. |
| E30 safe banking | Only carriers with at least 50 gems hard-block squares within enemy basic range + 2. If safe movement fails, immediately use normal movement. At corrected cap: 3/8 G2, 2/8 hunter, 2/8 altar. | This mask neither models move-and-attack/abilities nor provides an escape or wait decision when all routes are dangerous. Its failure does not reject threat-aware movement. |
| E33 pair safety | Below 50% health, an empty Cassi or Issac recalls when an enemy is within four tiles; ordinary 35% recall still exists. 2/8 vs hunter, 3/8 altar. | A health threshold plus interruptible recall is not joint pair survival. It ignores the partner, future enemy reach, local superiority and escape timing. |
| E40 hard split | Camp/champion handle modulo three partitions. 5/32, including 0/8 vs G2. | Arbitrary permanent allocation can remove the closest profitable camp and strand units. |
| E41 occupied-camp yield | Exclude groups occupied by a visible ally; fallback if no other goals. Improved altar suite but poor hunter pilot. | Distribution trades coverage against mutual support. Occupancy alone cannot choose that trade. |
| E42 “regroup on contact” | On any visible enemy, stop excluding ally-occupied camp goals. No rally point, shared target, retreat, arrival synchronization or force check. 5/18 vs hunter. | Restoring a common goal set is not coordinated regrouping. This result cannot reject the user's proposed behavior. |
| E43 pair roster + yield | E41 rule with Cassi/Issac/Stellar/Tavi; 10/32 and negative gems in every suite. | Extra bodies plus distribution do not compensate for linked exposure and missing combat support. |
| E48–E50 recall thresholds | Global or Varg-only earlier recall; lower deaths sometimes, markedly worse score. | Survival measures must include lost working time and retained map access, not just death count. |
| E51/G3 no empty recall | Removed low-health recall while empty; 16/18 vs G2, 12/18 hunter, 15/18 altar. | Empty-handed recall had substantial opportunity cost in this environment. This does not establish that walking into a losing fight is good. Avoidance and productive repositioning are different from recalling. |

Outcome source: [evolution log](../../bots/larpbot/EVOLUTION_LOG.md). Direct implementation checks: [E08 archive](../../bots/archive/rejected_experiments/E08_local_rally_escort.zip) `src/main.py`; [E11](../../bots/archive/rejected_experiments/E11_split_bank_escort.zip) `src/simple_policy.py:309–332`; [E30](../../bots/archive/rejected_experiments/E30_safe_banking_route_corrected_cap.zip) `src/simple_policy.py:205–224`; [E33](../../bots/archive/rejected_experiments/E33_pair_threatened_recall.zip) `src/simple_policy.py:221–253`; [E42](../../bots/archive/rejected_experiments/E42_regroup_on_contact.zip) `src/simple_policy.py:89–132`.

The E11 source has an explicit idle return beside the carrier. That supplies a concrete mechanism for lost uptime, although the final statistics alone cannot quantify how much of the loss came from waiting versus altered banking, travel or fights. E30's unsafe fallback is directly visible in source; no claim is made that it caused every lost match.

## Objective selection and execution cannot be evaluated separately by accident

E32 was described as a navigation simplification, but it changed the goal-selection metric: geometric Chebyshev nearest tile followed by `move_towards`, instead of a field over all goals. The corrected implementation excluded blocked goals and still went 1/8 against E05A, submitting 3,160 versus 7,680. It tested changed destinations and reachability behavior as well as implementation cost. Preserve useful multi-goal navigation until a replacement chooses equally good reachable objectives. [E32 archive](../../bots/archive/rejected_experiments/E32_nearest_goal_navigation.zip), `src/simple_policy.py:35–51`; [record](../../bots/larpbot/EVOLUTION_LOG.md).

E14's full-cycle scoring used straight-line distances and omitted enemy pressure; its Lanes scores fell to 180 and 96. D1.2's hard objective commitment went 0/8; D1.3's capture commitment also went 0/8. These reject those scoring estimates and commitment policies, not the concept of finishing valuable captures. A new objective must have a reachable approach, expected remaining clear/capture time, visible contest risk and explicit cancellation conditions. [E14 record](../../bots/larpbot/EVOLUTION_LOG.md), [D1 development](../../bots/D1/DEVELOPMENT_RESULTS_2026-10-14.md).

E27's single capturer collected more than its G2 proxy baselines but submitted less and died more. The record notes that payout concentrated on Varg; E28's empty-carrier reservation refinement was byte-identical on the pilot. Distinguish clear, capture and cash-out success. A claim should convey an actual intention and expire; an ally standing on a group is not necessarily staying to capture it. [E27/E28 record](../../bots/larpbot/EVOLUTION_LOG.md).

## Why the local champion was not competitive online

D1.15 won 103/126 against seven local opponents and 16/18 against G3. Its five top-team online groups were 0/25 maps, averaging 273 banked gems. The local result was accurately labeled a local result, but it did not expose the ladder's tactical and economic strength. All those local opponents are related policies or purpose-built proxies, not seven independent competitive systems. [Local evaluation](../../bots/D1/D1_15_OTHER_TEAMS_REPORT_2026-10-14.md), [online evaluation](../../bots/D1/D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md), [proxy dispatcher](../../bots/opponents/carrier_hunter_proxy/src/main.py).

Two distinct losses matter. Against hello on Collision, D1 repeatedly lost champions and never stabilized a safe camp loop. Against Mite on Expanse, neither team had a champion kill near the analyzed endpoint, but Mite led camps 29–21 and gems 972–722. Better fight avoidance alone cannot solve the second failure. The next bot must improve safe camp throughput and conversion as well as combat survival. [Replay observations](../../bots/D1/D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md).

`gold_diamond` then went 0/20 against ranks 34, 96, 186 and 283. On one Collision replay it had captured 10 camps by round 223 yet banked zero. Its active carrier branch returns directly after `bank()`, without tactical self-defense. Those observations strengthen the need for a tactical layer that runs for carriers too. They do not establish exactly how many gems were lost to deaths, inaccessible altars or interrupted channels; the current report lacks that action-level accounting. [Gold Diamond online report](../../bots/gold_diamond/ONLINE_LADDER_RESULTS.md).

## Evidence quality corrections

1. Early experiments passed `--fuel 2500000`, which granted Python 62,500,000 fuel because of the 25× multiplier. Correct-cap runs use `--fuel 100000`. Prefer explicitly corrected sections over old summaries. Most strategic regressions cited above completed with zero faults; there is no evidence that fuel exhaustion explains them. [Calibration correction](../../bots/larpbot/EVOLUTION_LOG.md).
2. Identical artifact repeats are reproducibility checks, not new independent samples. D1's report explicitly records changed outcomes after rebuilding even on unchanged draft branches. Freeze and hash artifacts; separate repeated runs of one build from different initialization exposure. [D1 development](../../bots/D1/DEVELOPMENT_RESULTS_2026-10-14.md).
3. Historical documents disagree on “deterministic” versus “unseeded” language. What is supported is exact repeats for some frozen artifacts, no exposed seed control, and changes after rebuild. Do not infer randomness or paired causality beyond that evidence.
4. Earlier global reviews still describe G2 as canonical and E08/E09 as uneventful rally tests; later evolution-log corrections establish their inactive code and G3 promotion. Treat the reviews as dated records, not current truth. [Earlier review](../strategy_reviews/2026-10-14-larpbot-global-review.md), [corrections](../../bots/larpbot/EVOLUTION_LOG.md).
5. Zero faults proves runtime completion, not correct tactical execution. A tactic can be unreachable, inert or semantically wrong without throwing.

## Requirements for the next foundation

These are design recommendations inferred from the evidence, not validated performance claims.

- Run a common safety and action-selection layer before farm, bank, capture or regroup actions. A nonempty bag must not bypass combat judgment.
- For every candidate movement, assess enemy reach before the unit can act again, ally arrival timing, escape availability, and linked-partner exposure. Enemy count alone is insufficient, but an unsupported 1v2 must be an explicit rejected case.
- Treat Cassi/Issac as one shared loss budget with two workers. Separate only when both assignments are independently safe and a partner emergency can cancel the other's risky work.
- Make regroup a reachable rendezvous with required participants, a deadline and a specific next objective. Cancel or choose another objective if the force cannot assemble safely. Do not idle the full team indefinitely around a small bag.
- Value economic actions by secured gems over useful time, including camp retaliation, capture hold, banking trip and channel exposure. Record each stage separately so fewer deaths cannot conceal economic inactivity.
- Keep claims soft, expiring and observable; preserve a reachable fallback. Avoid handle partitions and rigid whole-map commitments.
- Demonstrate tactical scenarios before large score matrices: lone unit faces two enemies; ally too far away to help; pair member threatened while partner carries; unsafe altar approach; contested capture; enemy vanishes into fog; regroup cannot complete. Trace the selected action and the reason.
- Make the shipping entry point and active policy identity visible in logs. Record tactic activation, threatened movement rejection, objective changes, regroup wait time, camp clear-to-payout time, bag loss at death and channel interruption.
- Use local bots as regression and failure-scenario opponents. Gate competitive claims on fresh actual ladder games near the intended rank, with both open and contact-heavy maps. Do not tune map/side rosters until one artifact happens to beat every local case.

The old strategy review's broad “avoid contact-triggered regroup states” conclusion exceeds its evidence. E42 did not implement such a state. Keep its warning about opportunity cost and unmeasured conditions, but build and evaluate the real behavior the user requested. [Review conclusion](STRATEGIC_REVIEW_2026-10-14.md).
