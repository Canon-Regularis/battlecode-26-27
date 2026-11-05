# CAMBC 2026 Meta Adaptation Plan

**Status:** planning and evidence synthesis only. No gameplay code or matches were changed or run for this document.  
**Evidence labels:** **[RULE]** documented in the local rules/API; **[OBSERVED]** visible in leaderboard, match or map-editor data; **[HYPOTHESIS]** strategic interpretation awaiting controlled testing; **[VERIFIED]** reproduced in a local match or test. This document records no new **[VERIFIED]** strategic findings.

## Executive summary

The original [competitive bot plan](plan.md) was right to centre the camp-clear → capture → bank loop, but it promoted **Tavi + Varg + Marcella** too early as the likely foundation and understated how valuable melee action economy and Vendetta’s reset passive may be. The current public leaderboard gives a strong reason to test **Vendetta + Varg + Ryth** and **Vendetta + Varg + Cassi & Issac** first. It does not establish that either lineup caused WHIM’s wins or is optimal.

The revised recommendation is to build a reliable, champion-aware economic baseline with Vendetta and Varg support from the first playable phase, while treating champion composition as a benchmark variable. Use map data and expected *secured gems per cycle* to assign objectives. Add combat interference after the baseline can capture and tribute dependably. Test high-impact rules interactions separately before making them dependencies.

Three changes matter most:

1. **[OBSERVED] Reorder champion experiments:** Vendetta is a high-priority challenger to Tavi as the default economic pick; Ryth and Cassi & Issac deserve direct controlled comparisons with Marcella. Keep Tavi and Marcella as serious map/matchup alternatives.
2. **[RULE + HYPOTHESIS] Treat melee movement-plus-attack as a measurable throughput advantage:** it may compound over long routes and fights, but it is not automatically superior to range, spell burst, safety, or Tavi’s field investment.
3. **[RULE] Optimize the full camp-to-bank cycle, not isolated camp value:** include pathing, clear, capture, risk, altar approach/channel, reward splitting, respawns and marginal upgrade value. A nearby repeatable route may beat an isolated high-value target.

Recommended first implementation phase remains **Stage 1: make the whole baseline loop correct**, now with basic Vendetta and Varg-specific action handling included. Use SDK `move_towards()` for initial routing and keep uncertain mechanics out of the foundation. Then benchmark controlled champion proxies and advance to economic optimization.

## 1. Leaderboard evidence and limits

### Public snapshot

The user-provided scrape is dated 13 October 2026. The public [leaderboard](https://2026a.battlecode.co.uk/game/ladder) was re-opened during this analysis and showed it had updated shortly afterward. At that later page view, the first six entries were approximately:

| Rank | Team | Elo | W–L | Most-picked champions shown for recent 50 games |
|---:|---|---:|---:|---|
| 1 | WHIM | 1,628 | 20–4 | Ryth, Varg, Vendetta |
| 2 | SSSA | 1,609 | 15–3 | Cassi & Issac, Ryth, Vendetta |
| 3 | Nameless | 1,606 | 22–17 | Cassi & Issac, Ren, Vendetta |
| 4 | Cabbage | 1,604 | 16–10 | Cassi & Issac, Ryth, Vendetta |
| 5 | Emperor Tung | 1,596 | 24–10 | Cassi & Issac, Varg, Vendetta |
| 6 | Nyx | 1,593 | 21–10 | Cassi & Issac, Stellar, Vendetta |

Other leading entries also showed variations such as Tavi/Varg/Vendetta and Ryth/Varg/Vendetta. Values are a changing public snapshot, not a stable dataset. The displayed popular picks indicate frequency in recent games, not the exact full lineup in each game.

The public [WHIM profile](https://2026a.battlecode.co.uk/game/team/4ce66a67-dc60-44f3-81f5-03997b963594), [WHIM–orZers group](https://2026a.battlecode.co.uk/game/match-groups/682ac9c9-1ae5-4149-80a3-59a78e77b6ac) and [WHIM–larp group](https://2026a.battlecode.co.uk/game/match-groups/729f44ba-28c4-49a8-8dab-89ff1183b04d) were also inspected. The latter page labels the finished 5–0 set **unranked**. In the orZers set, WHIM won 4–1 and lost Corners; the displayed Corners result was 734–1,032 in 606 rounds, while WHIM won Interlock 1,000–154 in 365 rounds. In the larp set, the five displayed maps were wins, including a close Lanes score of 1,008–984. Match-page scores can differ slightly from the supplied scrape snapshot as pages update; retain source and retrieval time when tracking them.

### What these observations support

- **[OBSERVED]** Vendetta is exceptionally common among the displayed leading teams, and Ryth, Varg and Cassi & Issac are also frequent. Multiple high-Elo teams use different combinations, including Ren and Stellar. This makes the champions worth prioritizing in experiments.
- **[OBSERVED]** WHIM performed strongly across several displayed maps and lost one reported map on Corners. That single loss motivates a Corners audit; it does not prove a map-specific weakness or reveal its cause.
- **[OBSERVED]** The results include short, decisive wins and a narrow Lanes win. Scores and duration alone do not reveal farming routes, early lead, combat, capture count, deaths, or tribute timing.

### What they do not support

No replay movements, action logs, exact compositions for every game, build choices, map-side balance, or opponent policy were available in the replay visualiser during the scrape; it required WebGL2. Accordingly, do not state that WHIM wins because of melee action economy, Vendetta resets, coordinated farming, or any other specific cause. The live ladder is a source of candidate hypotheses, not causal evidence. Elo and record are affected by opponent strength, game volume, match selection and recency.

**Recommendation — Mechanism:** use leaderboard pick frequency and map results to nominate compositions. **Why:** it directs limited engineering time toward plausible high-value choices. **Expected benefit:** faster discovery of a strong roster. **Failure/counter:** copying picks may copy no underlying policy and can overfit one team or a transient meta. **Test:** run the same bot policy with alternative compositions, then the same composition with alternative policies. **Priority:** immediate experiment design; no fixed meta roster yet.

## 2. Re-evaluate the champion meta

Rules references below are from [`GameRules.md`](../GameRules.md); API constraints are in [`BotAPIPython.md`](../api/BotAPIPython.md). Champion build and ability hypotheses are also documented in [`CHAMPIONS_AND_BUILDS.md`](CHAMPIONS_AND_BUILDS.md). Exact damage and action use must follow current champion ability definitions and action guards.

### Melee action economy: a plausible multiplier, not a conclusion

**[RULE]** Melee champions normally may move and basic-attack on the same turn; ranged champions generally share the movement/attack allowance. This potentially means one fewer idle repositioning turn whenever a melee farmer is in range of a valid target while needing to move. Across travel, pursuit and sustained combat, it can add many attacks or bring capture arrival forward. However, it adds no attack when the melee unit is stationary and already attacking; ranged units can attack from farther away, avoid some camp retaliation, and may use spells that exceed basic attack range. A spell that excludes walking can also give a ranged champion an effective damage turn while it cannot move, but cooldown and cast limits constrain cadence.

**Recommendation — Mechanism:** value melee mobility as an action-economy term inside each champion’s clear-time estimate. **Why:** expected damage per attack alone ignores the turns spent approaching and repositioning. **Expected benefit:** better route throughput estimates and fairer champion comparisons. **Failure/counter:** a route estimate can overvalue movement turns where no target is attackable; high-range farming or incoming damage can favor ranged units. **Test:** on fixed maps and camps, compare damage actions, successful movement turns, total clear turns, health lost, capture arrival time and gem yield per round for melee/ranged champions. Repeat with them already in range and with long approach distances. **Priority:** Stage 1 champion-aware logic; validate in the first benchmark suite.

### Vendetta: reset chains and high-strength melee

**[RULE]** Vendetta starts with high Strength (70 per the rules summary), basic melee attacks, an attack-reset ability and a dash. On any kill, including a neutral camp monster kill, her passive refreshes both ability cooldowns. This creates a credible sequence: cast one ability, secure a kill, have cooldowns ready on the following turn, and potentially carry mobility/attack-reset availability through a string of weak monsters. The one-successful-ability-per-turn limit still applies; cooldown refresh is not a second cast. A kill also has to be secured by Vendetta, so allied overkill and damage timing matter.

The strongest potential value is likely **combined**: good basic-attack damage while advancing, kill-dependent ability availability, and chase/rotation mobility. Which contribution dominates depends on the map and camp HP thresholds. Do not let her chase a low-value last hit if it delays capturing a group or risks a valuable bag.

**Recommendation — Mechanism:** target monsters to make kill-credit and overkill useful; after a reset-producing kill, reconsider the newly ready ability next turn. **Why:** it converts passive cooldown refresh into clear tempo rather than treating ability readiness as a fixed schedule. **Expected benefit:** fewer idle cooldown turns, potentially more attacks and shorter rotations. **Failure/counter:** reset has no value if abilities are not currently useful, a teammate takes the kill, targets are too durable, or pursuing a last hit costs more than its tempo. **Test:** controlled Vendetta matches with ability policy enabled/disabled, plus target-order ablation; log reset events, successful casts, monster kills credited, damage, clear time, health and gems secured. Test both attack-reset extra-hit sequencing and dash-plus-movement separately; neither interaction is assumed. **Priority:** implement only documented, ordinary ability behavior in Stage 1; optimize kill sequences in Stage 2; uncertain stacking in Stage 4.

### Varg: measure splash at the group level

**[RULE]** Varg’s basic attack splashes Strength damage to other valid enemies/camps within radius one of its primary target; he also has an attack reset and a temporary shield. A grouped camp can therefore yield much more than single-target nominal Strength suggests. The valuable measure is time to clear the entire group and claim its capture reward, less survival and repositioning costs—not the number of units visually hit.

Map group composition matters: a tight group of low-health gem clusters can be excellent splash material; widely spaced durable monsters may not be. The early map survey found strong differences in groups and initial resources, including a Monolith map with a very large special group and Rows/Expanse with larger groups. These metadata make Varg a sensible test target, not an automatic pick on every map.

**Recommendation — Mechanism:** select the primary target using total splash damage against valid adjacent targets while avoiding overkill. **Why:** the best primary target may be the one that exposes several useful secondary targets. **Expected benefit:** fewer attacks per cleared group and earlier capture payout. **Failure/counter:** a splash hit can overkill a low-health secondary or leave the actual high-threat monster alive; clusters may be far apart; Varg can lose health while closing. **Test:** fixed target arrangements with splash-aware versus first-target policies; record predicted and observed targets/damage, turns per monster and full group, payout timing, incoming damage and throughput on each map. **Priority:** basic eligibility/damage handling in Stage 1; exact target scoring in Stage 2.

### Ryth: durable objective control

**[RULE]** Ryth has high base health, an area stun, an attack reset, and bonus Strength tied to bonus health. These may combine into a robust melee farmer and a strong contest/capture defender. The area stun could disrupt a group of attackers or protect a carrier; however, its cast excludes walking, is cooldown-limited, and using it on a neutral camp sacrifices a possible move. High health and scaling Strength do not alone establish higher gems per time.

**Recommendation — Mechanism:** benchmark Ryth as a stable frontliner/farmer and as an objective controller, assigning him to groups and contested routes where survivability and area control can prevent lost capture progress. **Why:** high health reduces retreat/death risk, while stun can create conversion or escape windows. **Expected benefit:** reliable captures under pressure and stronger team fights. **Failure/counter:** opponents can disengage, use altar locks, avoid grouping for AoE, or simply outfarm while Ryth spends turns fighting; stun immunity (e.g. Marcella) counters the control component. **Test:** compare Ryth and same-policy alternatives on uncontested groups and on scripted capture contests; track cleared gems, capture resets prevented/caused, deaths, carrier survival, casts, and enemy turns denied. **Priority:** include him in initial meta proxy; sophisticated role assignment in Stage 3.

### Cassi & Issac: an extra acting body for correlated risk

**[RULE]** One draft selection creates Cassi and Issac, independently positioned and independently acting. This can add a second farming/capture route and an extra turn stream without using a second draft slot. Their linked-death rule means either death kills both, however; both bags and the pair’s map coverage can be lost at once. The benefit should be largest where independent profitable objectives are numerous and travel distances allow parallel work. It may be smaller where the team is already able to keep all camps assigned or on a map with few groups.

**Recommendation — Mechanism:** treat the pair as two agents with a shared risk constraint, keep bags modest, avoid sending both into overlapping camp retaliation/enemy threat regions, and use their independent vision to cover distinct routes. **Why:** extra body turns have value only when there is useful parallel work, while correlated death raises the cost of risk. **Expected benefit:** greater coverage and more simultaneous captures, especially on group-rich maps. **Failure/counter:** a competent enemy can kill the weaker-linked member to remove both; four selections of pair-heavy composition may create excessive fragility or poor upgrade assignment. **Test:** hold policies fixed and compare Cassi & Issac with one solo champion across maps of differing group count; record useful action count, objective overlap, capture coverage, shared deaths, gems lost and score rate. Add a risk separation ablation. **Priority:** Stage 1 supports both bot identities; map-dependent draft promotion after controlled tests.

### Reconsidering Tavi and Marcella

**Tavi — [RULE]:** field purchases can convert otherwise idle shopping/return time into earlier damage or survivability upgrades; selling shards at spawn for full value and field purchase access can also make investment more flexible. He is ranged and relatively fragile, and a field Health shard does not heal. His ranged spell’s focus scaling and stun may be useful but has cooldown/action costs.

**Mechanism → why → benefit:** field buying turns gold into stats without a spawn detour; this may improve gem rate where frequent upgrades repay immediately. **Failure/counter:** shard purchases can consume gold that should secure a tribute/lock and do not necessarily save an attack; Tavi may fall to focused pressure; ranged movement tradeoffs reduce approach tempo. **Test:** same policy and maps with Tavi field buying enabled/disabled, recording spend timing, cost, attack breakpoints, bank time, health and score. **Priority:** preserve as a high-value Challenger from Stage 2; basic legal shop only in Stage 1.

**Marcella — [RULE]:** stun immunity addresses one major control class, and her enhanced attack/reset and ranged spell offer a flexible kit. But stun immunity does not prevent death, locks, ordinary damage, or forced path denial. She may be particularly valuable against Ryth-heavy compositions if she can still contest safely.

**Mechanism → why → benefit:** remove stun as an interruption channel against her while channeling or fighting. **Failure/counter:** opponents can lock the altar or deal lethal damage; she might give up economic action economy compared with Vendetta/Ryth. **Test:** paired matches versus stun-heavy opponents and neutral baselines; measure canceled channels, deaths, gems lost, camp clear time and total tribute. **Priority:** retain as a matchup counter candidate; not a mandatory courier.

**Stellar, Ren, Vesper and other picks:** leaderboard appearances make Stellar and Ren real candidates. Stellar may trade safety for spell burst; Ren’s melee kit and retaliation/stun/dash could punish focused aggression; Vesper’s gold bonus may compound only if early gold converts to stronger future clearing quickly enough. Willow’s healing may improve grouped fight uptime; Prism may reward carried gems but makes bag-risk management more important. These are specialist hypotheses, not rejected champions. Test them where their mechanic answers a concrete policy gap.

### Composition shortlist by selection count

The nine-map metadata show roster sizes of 3 on Collision, Expanse and Packs; 4 on Interlock and Rows; 5 on Corners, Elkring, Lanes and Monolith.

| Selections | Primary proxy | Challenger(s) | What this isolates |
|---:|---|---|---|
| 3 | Vendetta + Varg + Ryth | Vendetta + Varg + Cassi & Issac; Tavi + Varg + Marcella | Extra body coverage vs Ryth durability/control vs Tavi investment and Marcella stun answer |
| 4 | Vendetta + Varg + Ryth + flexible | Replace Ryth with Cassi & Issac; test a mixed Tavi or Marcella slot | Marginal value of fourth selection and body count |
| 5 | Vendetta + Varg + Ryth + Cassi & Issac + flexible | Replace each slot systematically with Tavi, Marcella, Stellar, Ren, Vesper or Willow | Whether pair plus core is worth linked fate and opportunity cost |

These are test rosters, **not final recommendations**. Select the remaining flexible champion through map and opponent tests. Draft should use public information only, and map-dependent group metadata must not be assumed accessible until the draft API discrepancy is tested in the runtime.

## 3. Competing explanations for WHIM’s results

Each hypothesis is plausible but unproven. More than one can be true; the experiments should estimate independent and interaction effects.

| Hypothesis | Mechanics and rationale | Evidence / counterevidence | Measure and response if supported | Competent counter |
|---|---|---|---|---|
| **Economic efficiency** | Camp rewards only matter when captured and tributed; fewer actions per permanently banked gem wins the race. | High Elo across several shown maps supports general effectiveness, but no economy trace is public. A 1,000–154 win could reflect combat or opponent collapse too. | Gems secured per 100 rounds, clear/capture/bank timing, lost bags. If strong, prioritize full-cycle utility and routes. | Contest profitable camps, force detours or kill carriers. |
| **Action economy** | Melee can generally move and attack in one turn; Vendetta/Ryth/Varg all provide melee action. | Champion pattern is consistent with this hypothesis, but picks do not reveal action logs. Range and spells may offset it. | Movement turns with attacks, attacks during approach, total clear time vs ranged control. If strong, value approach mileage and melee roles. | Keep camps spread, kite melee away from efficient targets, exploit melee exposure. |
| **Capture efficiency** | Five uncontested capture rounds are a fixed conversion cost; securing a tile quickly and not splitting payouts improves yield. | Wide wins could reflect reliable captures, but no capture stats are displayed. | Capture attempts/successes, resets, allies present at payout, time from final kill to payout. If strong, improve assignment and persistence. | Contest/reset timers, threaten carrier, exploit overconcentration. |
| **Scoring efficiency** | Tribute is the victory condition; risk-aware bag size, altar choice and channel timing can reduce lost gems and avoid wasted channel time. | Short wins demonstrate scoring happened; no bag/tribute timeline is visible. | Round of each tribute, channel cancellation, bag losses, secured score divided by carried score. If strong, tune bank policy and escort allocation. | Lock altars, ambush predictable routes, pressure alternate altar. |
| **Combat advantage** | Kills steal carried gems; Vendetta reset and Ryth control could deny enemy conversion while farming. | One-sided map results may include combat, but match pages do not expose causation. | Enemy deaths, bag value taken, own deaths, time diverted, tribute denied. If strong, target high-value exposed carriers selectively. | Split bags, keep vision/escorts, avoid fights, use Marcella vs stuns. |
| **Map adaptability** | Maps vary in roster size, total gems, group count and topology; ability to choose targets/routes per map increases consistency. | WHIM wins on several reported maps and one Corners loss; sample is too small to infer specific adaptability. | Per-map win rate and secured-gem tempo across sides, not just aggregate. If strong, draft/route policy should condition on observed map data. | Force contests on the bot’s map-specific bottlenecks. |
| **Champion synergy** | Varg group splash, Vendetta resets and Ryth durability/control may cover farming, mobility and contested play jointly. | Popular pairing is suggestive; exact joint selection in each game is unknown. | Factorial roster-policy tests and pairwise interaction terms. If synergy is weak, choose by marginal contribution, not meta imitation. | Draft counters or attack the role the composition lacks. |

**Implementation consequence:** the first performance dashboard must distinguish mechanics, algorithm and roster. Champions compared under different policies do not answer whether the roster or the bot caused a gain.

## 4. Economic objective selection

### Objective: expected permanently secured value per time

The relevant output is not raw camp reward or damage. It is expected team gems permanently secured, with gold valued by how much it improves future performance. For champion (i), candidate group (g), and route/strategy (r), estimate:

```text
cycle_time(i,g,r) = approach_turns
                  + clear_turns
                  + capture_wait_turns
                  + travel_to_altar_turns
                  + tribute_turns
                  + expected_recovery_or_detour_turns

P_secure(i,g,r) = P(capture completes | clear)
                * P(carrier reaches altar | capture)
                * P(channel completes | arrival)

net_cycle_value = P_secure * expected_new_gems
                 + gold_shadow_value * expected_gold
                 + denial_value_in_gem_equivalents
                 - expected_own_gem_losses
                 - opportunity_cost_in_gem_equivalents
score_rate(i,g,r) = net_cycle_value / max(estimated_cycle_time, 1)
```

This is a **decision aid**, not a claim that the engine’s stochastic risks are known exactly. The probability terms are conditional stages in the route, not assumed independent factors. At the victory threshold, direct gems dominate the score function. Gold’s shadow value should be learned from benchmarked purchase breakpoints (e.g. turns saved by a shard), and fall toward tiebreak-only value once purchases no longer improve the match. Avoid subtracting the same death/channel risk twice: use either reduced expected secured value or an explicit expected loss term for each distinct consequence.

For a group, estimate:

```text
approach_turns = SDK path distance to a legal attack position / effective movement
clear_turns = turns needed under this champion's basic and ready ability actions
capture_wait_turns = remaining capture timer, else 5 capture phases after clear
travel_to_altar_turns = shortest safe route to an unlocked altar approach tile
tribute_turns = max(1, ceil(expected_bank_bag / 10)) owner end-turn ticks
```

Account for the important details:

- **[RULE]** A group pays only after all its monsters die and an ally occupies a spawn tile uncontested for the capture period. Emptying/contesting resets progress; allies do not accelerate it; allies present at payout split reward. Leaving one monster alive or walking away can make prior work worthless.
- **[RULE]** Groups respawn after the longest member cooldown; occupying a spawn tile can delay the whole respawn. A group can be unavailable or contested; value only the reward expected to become available within the relevant planning horizon.
- **[RULE]** Carried gems can be lost on champion death. Camps destroy a bag; an enemy killing a carrier can take the bag. A high-gem route may be dominated by a safer route if its completion probability is low.
- **[RULE]** Tribute length depends on gems at channel start, while captures resolve before channels; whole-bag snapshot timing remains an exploit hypothesis from [`MECHANICS_AND_EXPLOITS.md`](MECHANICS_AND_EXPLOITS.md), not baseline behavior to rely on.
- **[RULE]** Gold purchases are normally tied to spawn/death except Tavi’s field shard buying. Account for actual next purchase opportunity and whether the item changes actions-to-kill, survival or movement.
- **[RULE]** Visible enemy positions and channels are observations; hidden opponents, bags and camps should be modeled as uncertainty, not known facts. Vision is not automatically shared.
- **[RULE]** Ranged attack allowance, ability movement restrictions and one successful cast per turn influence clear time; use per-champion action simulators or conservative estimates.

### Short cycle versus maximum isolated payout

A nearby, moderate-value camp can be better than the largest isolated camp if it shortens approach and altar travel, has fewer monsters to clear, is less likely to be contested and can be repeated safely. Compare both over **completed route cycles**, not one camp’s gross gems. Conversely, a high-value camp such as a Monolith group may dominate when a team can clear it efficiently and safely. Do not encode “nearest” or “richest” as a universal policy.

**Recommendation — Mechanism:** rank full camp-to-tribute cycles and use marginal value of a route relative to the next-best route. **Why:** capture and banking are mandatory conversion steps with material time/risk costs. **Expected benefit:** more permanent score and fewer stranded bags per round. **Failure/counter:** uncertain opponent threat can skew probabilities; estimates of spell turns or capture timing can be inaccurate; a locally best loop may be predictable. **Test:** compare nearest-camp, highest-gross-reward and full-cycle scoring policies on the same champions/maps; record score rate, bag loss and win rate. **Priority:** Stage 2 after a correct fixed-target loop exists.

### Team assignment, persistence and switching

Each champion’s best objective cannot be chosen independently if they all select the same group. Draft roles should produce a portfolio of assigned routes. A simple feasible assignment is a small greedy auction: calculate the best few group/altar cycles per champion; award the highest marginal team value; remove or discount that objective for other allies; repeat. Add a teammate already en route/clearing/holding a capture tile as a large assignment cost. Avoid assigning several champions to capture the same payout, which splits rewards without shortening the fixed capture timer.

The bot should persist its target across turns. Without **hysteresis**, small changes in position, cooldown/readiness or visibility can flip the apparent best target and cause oscillation. Keep the current objective unless it becomes invalid, blocked, completed, threatened beyond tolerance, or the new objective exceeds it by a meaningful threshold (initially a tunable margin, then calibrated). Replan at meaningful events: camp clear, capture start/completion/reset, respawn, enemy sighting, bag threshold, failed move, or major score change.

Stuck detection should record objective ID, last position/progress round, last successful action and repeated `move_towards()` false results. If position or distance has not improved after a small window, try an alternate legal tile/approach, refresh vision and objective state, then abandon only if still unreachable or dominated. A false SDK move may mean already at target, blocked/unreachable, or a newly revealed hidden occupant; distinguish these cases before discarding the plan.

**Recommendation — Mechanism:** objective persistence plus state-triggered replanning and stuck recovery. **Why:** turn-by-turn local greed can repeatedly reverse direction and waste the very movement/attack economy the strategy seeks to exploit. **Expected benefit:** lower idle/travel turns and fewer failed actions. **Failure/counter:** persistence can make the bot stubborn after a new enemy contest or stale shared assignment. **Test:** instrument target switches, progress distance, false moves, idle turns and completed cycles; compare with no persistence on identical replays/configurations. **Priority:** Stage 2, with simple fallback in Stage 1.

### Pathfinding and fuel budget

Start with SDK `me.move_towards()` when a destination tile is known and legal. It supplies a shortest path step while accounting for known terrain/occupants and hidden-obstruction failures; handle `False` safely and retry a different route only when needed. This avoids spending fuel and implementation time rebuilding basic pathfinding. Use native `Bitboard`, reachability and `DistanceField` only where they add needed decisions, such as choosing among several weighted attack/capture tiles or estimating a safety-adjusted route. A custom pathfinder is justified only when benchmarks show shortest paths cause a measurable, correctable risk or objective-selection loss.

Python’s fuel budget is finite (the rules describe it as 25× the C++ allotment); each champion has its own bot instance, while team shared memory is only eight mutable bytes. Draft memory is 1,024 bytes, read-only during gameplay. Do not serialize full plans or map grids into shared memory. Use compact deterministic role/objective identifiers, tolerate stale/missing data and preserve safe local decisions. Vision remains champion-local. Stop optional search when fuel is low; measure worst-case fuel on large maps and visible combat states.

## 5. Map pool and map-specific hypotheses

The installed map editor was used to inspect map setup and camp-group summaries. Counts and reward totals below are **[OBSERVED] map-editor metadata**, not match-performance data. Group-size and reward combinations are included to show why total camp count can mislead; confirm type/position details from `game_map.camp_groups()` in each relevant runtime. A broad map rendering can suggest corridors and clusters, but exact camp-to-altar distances, sightlines and safe routes have not been calculated here.

| Map | Grid; selections/team | Groups / camps | Starting camp gems / gold | Strategic question to test |
|---|---|---:|---:|---|
| Collision | 41×41; 3 | 10 / 13 | 268 / 945 | Few groups are unusually large (one 4-camp bundle). Is a high-body roster worth the lost solo kit, and does Varg exploit that bundle? |
| Corners | 71×71; 5 | 15 / 23 | 496 / 1,850 | Large grid and many camps create route/contest choices. Is the WHIM loss associated with spawn-side access, choke routes, group ownership, side or opponent strategy? Measure rather than infer from the name or one result. |
| Elkring | 30×30; 5 | 5 / 10 | 180 / 975 | Dense small grid but very few groups, each reported as a two-camp group. Does five selections overconcentrate, and is safe ranged pressure more efficient? |
| Expanse | 80×80; 3 | 15 / 32 | 614 / 1,370 | Largest grid and many groups, mixed one- and multi-camp bundles. Long-distance coverage may reward extra bodies; custom navigation only if SDK shortest paths prove inadequate. |
| Interlock | 40×40; 4 | 8 / 12 | 210 / 730 | Low initial gem pool and several multi-camp groups. Banking, respawn timing and enemy denial may be more important than maximizing early gold. |
| Lanes | 90×30; 5 | 21 / 21 | 450 / 1,395 | Long, narrow footprint, all single-camp groups in the editor summary. Potential corridor interceptions and travel asymmetry; map-side and altar-route tests matter. |
| Monolith | 50×50; 5 | 11 / 22 | 626 / 1,375 | One reported 9-camp, 392-gem/300-gold bundle includes the Monolith-scale reward pattern. Test whether concentrated investment can clear and safely convert this payout or whether split routes dominate. |
| Packs | 31×31; 3 | 4 / 10 | 180 / 610 | Few groups and lowest initial resources, so respawns and camp denial may dominate later yield. Extra Cassi & Issac body could cover parallel tasks, but direct test is necessary. |
| Rows | 50×50; 4 | 5 / 14 | 646 / 1,515 | One reported 4-camp, 448-gem/600-gold group plus three wolf groups and a gold-only group. Huge reward concentration invites race/contest strategies and focused Varg testing. |

Initial gems in the map are below 1,000 on every map. Therefore a win generally requires some combination of respawns, opponent bag capture or a high-value resource pattern; a strategy that treats the initial board as a one-pass race may stall. This is a map-total deduction from editor metadata, not a claim about the exact timing of any match.

### Map-specific hypotheses and tests

- **Collision:** compare Varg’s splash and a two-body Cassi & Issac selection against less clustered alternatives. The observed group sizes include mostly singles and one four-camp bundle; the bundle’s location and path access determine whether it is worth a draft slot.
- **Corners:** do not infer that the map caused WHIM’s loss. Analyze match replay/statistics if available: start side, champion roster, group clear/capture sequence, deaths, gem bags, tributes and time. Run many paired games versus the same policies on both sides. Candidate causes include spawn-side route asymmetry, contested central high-value camps, path/vision chokepoints, opponent matchup or ordinary variance. Verify each from map positions or replay data.
- **Elkring and Packs:** low resource count makes idle turns costly and respawn-aware looping important. Compare spread route assignment with concentrating to finish captures faster (which normally does not shorten the fixed timer). Check whether ranged range-4 spells can safely pressure camps from outside their range 3.
- **Expanse and Lanes:** large or elongated geometry may raise travel cost and benefit independently operating champions, but open-looking visuals do not substitute for shortest-path computation. Measure spawn-to-group, group-to-altar and group-to-group travel using SDK/runtime or offline map parser before draft specialization.
- **Monolith and Rows:** concentrated camp rewards make expected clear time, capture defense and bag protection important. Varg may help against dense valid splash targets, but a durable large target or linked pair can expose the whole investment to a contest.
- **Interlock:** the leaderboard result WHIM–orZers was decisive, but a result alone cannot diagnose why. Use it as one matchup/mirror benchmark, not as proof that WHIM’s approach is map-optimal.

**Recommendation — Mechanism:** keep per-map priors for team size, resource totals and group layout, then learn routes from actual success metrics. **Why:** the same champion’s splash, travel and exposure value changes with group geometry and map scale. **Expected benefit:** less overfitting to a one-size-fits-all route. **Failure/counter:** map-specific parameters can overfit a small sample or depend on draft data unavailable at runtime. **Test:** cross-validate map policy on separate games/sides and test draft visibility in actual runtime. **Priority:** collect data during Stages 1–2; promote specialized drafting in Stage 5.

## 6. Revised implementation stages

The original [plan.md phases](plan.md) remain useful, but the sequence should be adjusted to bring champion-critical behavior into the first baseline, then separate economic, combat and experimental complexity.

### Stage 1 — Correct, complete baseline loop

Implement: **select group → approach → use legal basic/ability actions → clear every camp in group → occupy a spawn tile → hold capture → receive rewards → choose altar → tribute → repeat**. Include basic Vendetta kill-reset awareness and Varg splash-aware legal primary target selection from the first champion-capable version. Handle death, channeling, shop/legal guards, hidden obstructions, unreachable objectives, stale/empty data and per-champion state. Keep conservative fallback behavior if an ability/action fails.

Use `move_towards()` for ordinary navigation. Add a small explicit state machine (`APPROACH`, `CLEAR`, `CAPTURE`, `BANK`, `RECOVER`) and simple target persistence. Do not start with complex team auctions, opponent prediction or custom global pathfinding.

**Why first:** a bot that cannot finish capture and safely convert its bag loses the value of every sophisticated fight or route model. This phase validates API and timing assumptions and creates a measurable baseline. **Success gate:** reproducible matches complete the loop without systematic invalid actions, abandoned capture timers, failed tribute attempts, crashes or fuel exhaustion; report completed cycles and score. **Counter/failure:** basic route choice can be predictable and inefficient; that is acceptable for a correctness baseline and addressed in Stage 2. **Priority:** now.

### Stage 2 — Economic and coordination optimization

Add full-cycle camp ranking, champion-specific clear estimates, marginal purchase valuation, separate allied objectives, assignment conflicts, capture payout splitting, persistence/hysteresis, stuck detection, altar route safety and respawn-aware loops. Include short-cycle-vs-rich-target comparison and limited gold shadow value from observed breakpoints. Support Tavi field shards as a measured option.

**Mechanism → why:** attacks/capture/banking/time compete; fitting expected secured value to the actual objective should raise score tempo. **Expected benefit:** more gems tributed with less idle/travel and fewer lost bags. **Failure/counter:** model error and opponent contest can invalidate a planned cycle. **Test:** compare each economic feature by ablation, map and side; inspect observed vs estimated durations. **Priority:** immediately after Stage 1 passes.

### Stage 3 — Combat, defense and counterplay

Add threat estimates from visible opponents’ position, likely attack range, health, ready abilities, action order and current own bag/role. Protect the highest-value carrier only when the escort’s score value exceeds lost farming; prioritize a kill only when a plausible outcome protects or steals enough gems or stops a win. Contest captures selectively; evaluate locks and lock-clearing by timing and expected tribute denied; retreat/recall when survival benefit repays the lost turns. Add stun/cooldown coordination and anti-stun matchup handling.

**Mechanism → why:** combat can steal a bag, stop a tribute or preserve reward conversion; otherwise it spends actions that could farm. **Expected benefit:** convert only favorable fights into scoring tempo and reduce catastrophic losses. **Failure/counter:** hidden enemies make threats uncertain; an enemy may bait escorts or use alternate altars. **Test:** scripted aggressor, carrier assassin, altar-locker and capture-denial bots; compare own bags lost, opponent score delayed, farm loss and win rate. **Priority:** after economy can be measured.

### Stage 4 — Isolated mechanics/exploit experiments

Use controlled fixtures and replay/event logs to test the items listed in Section 8. No speculative mechanic enters the default policy until engine behavior, map availability and net score impact are established.

**Mechanism → why:** phase ordering or ability action interaction could create disproportionate value. **Expected benefit:** a verified rules advantage without destabilizing ordinary play. **Failure/counter:** an apparent gain may be fixture-specific, timing-sensitive or fixed by an engine change. **Test:** minimal reproducible cases, explicit pass/fail conditions, then full matches with feature toggle. **Priority:** experiments can run in parallel with optimization design, but integration follows reliable evidence.

### Stage 5 — Competitive adaptation

Add matchup/map-aware drafting, data-backed champion rankings, item/build optimization, self-play and a diverse opponent suite. Use observed leaderboard trends to generate new proxies, not to dictate composition. Preserve a known-good release, promote changes only after paired benchmarks, and keep anti-meta options.

**Mechanism → why:** opponent policies and the public meta will evolve, and composition value is conditional. **Expected benefit:** retain performance as opponents adapt and discover counters faster. **Failure/counter:** overfitting to a narrow set of benchmark bots or recent pick frequency. **Test:** held-out opponent versions/maps, mirror tests and periodic live performance comparison. **Priority:** once a stable base and benchmark harness exist.

## 7. Combat and objective counterplay policy

Combat is justified when its expected impact on secured gems exceeds its farming opportunity cost:

```text
fight_value = expected_bag_stolen
            + expected_enemy_tribute_delayed_or_prevented
            + expected_capture_reward_denied
            + own_carrier_loss_prevented
            + verified kill / tiebreak value
            - expected_own_bag_loss
            - expected_farm_and_capture_value_forgone
```

Use visible facts only; uncertain enemy bag value should lower confidence. A nominal kill is not enough. Prefer focused attacks when allied turns can plausibly finish the target before its next score/escape opportunity. Vendetta is a natural high-damage finisher candidate; Ryth can punish grouped attackers; Marcella can resist stuns; Varg should avoid abandoning a productive camp to chase a low-bag target.

Decision priorities, with event-aware overrides rather than rigid unconditional rules:

1. Prevent a near-certain enemy win or immediate lethal loss of a valuable bag if a legal action can change it.
2. Take an immediately winning safe tribute; do not add turns for combat flair.
3. Preserve a capture that is close to payout when doing so is more valuable than switching targets.
4. Interrupt a valuable enemy channel with an altar lock only if action order allows cancellation before completion; consider remaining timer, lock availability/range and 10g cost.
5. Attack a vulnerable carrier or contest a capture when expected gem denial exceeds the farm cycle being sacrificed.
6. Otherwise continue productive farming and avoid extended pursuit.

**Locks:** [RULE] A 10g altar lock prevents opposing tribute, cancels an active channel, and is cleared by three successful basic attacks; trying to tribute through a lock attacks it. Phase order matters: if the enemy’s next turn start completes the channel before our move, the lock is too late. Counter by scouting, using another unlocked altar or clearing the lock when that beats farming. Do not assume locks expire.

**Captures:** [RULE] A contest resets capture progress. Contest only when the reward/denial is valuable and an ally can remain or win control; otherwise a feint can drain turns from both teams. Avoid having multiple allies split a reward unless their presence is needed to prevent reset or to win the fight.

**Carrier defense:** bank bags before they become an attractive target when travel/channel risk is high; avoid a fixed “always bank now” rule. Assign escort/cover to a valuable carrier only if the expected prevented loss justifies the lost objective coverage. Since vision is local, the escort cannot promise omniscient scouting; share only recent confirmed sightings and age them.

## 8. Advanced interaction research queue

The existing [`MECHANICS_AND_EXPLOITS.md`](MECHANICS_AND_EXPLOITS.md) and [`EXPERIMENTS.md`](EXPERIMENTS.md) contain proposed tests. Run each first as a minimal fixture against the engine/runtime, then assess full-match utility. Do not treat hypothesis descriptions as evidence.

| Priority | Interaction | Why it may matter | Required verification / integration gate |
|---:|---|---|---|
| 1 | Tribute duration snapshot plus capture payout | Potentially banks a much larger capture reward with a shorter initial-bag channel. | Verify adjacent altar/camp geometry exists; exact capture-before-channel payout eligibility; channel start/resolve ticks; repeat with counter conditions. Keep experimental until proven on tournament maps. |
| 2 | Range-four spells vs range-three camp attacks | May allow damage with reduced retaliation and safer carrier/farmer health. | Verify spell/camp targeting rules, camp aggro and cast/walk restrictions; compare health and full group clear time against melee. |
| 3 | Vendetta reset chains on neutral kills | Could refresh mobility/reset abilities across clustered weak targets. | Log cooldown before/after kill, who owns the kill, current action allowance and next-turn casts; measure route clear time. |
| 4 | Attack reset interactions | Could allow a second basic attack in a turn, perhaps after a normal attack or after movement. | Enumerate legal turn sequences per champion and verify successful hit counts; one ability cast/turn remains binding. |
| 5 | Dash plus ordinary movement and ranged attack | Potentially compresses traversal or combines travel and damage. | Test each action ordering, ability walking compatibility, movement allowance, path/hole constraints and fuel; do not generalize one champion’s result. |
| 6 | Ground-target spell and hidden units | Could affect an unseen unit or contest bush positions. | Verify legitimate targeting/vision requirements and damage outcomes; ensure no information leak is assumed. |
| 7 | Respawn manipulation and spawn occupancy | Occupying a camp spawn can delay a whole group; may deny an enemy repeat route. | Measure denial value versus one champion’s opportunity cost and safety, on groups with useful rewards. |
| 8 | Capture theft, timing and reward split | May convert opponent clearing effort into our payout or deny them a nearly finished reward. | Test capture eligibility, contest reset, owner-presence rules, reward division and round-start phase ordering. |
| 9 | Altar-lock timing and priority | Low-cost cancellation can deny a large score if the actor precedes completion. | Test all relevant team order/turn boundary cases and lock-clear sequences; include enemy turn priority. |
| 10 | Priority manipulation | `set_priority` affects next round and may change who can interrupt/claim timing-sensitive action. | Test action ordering and compare objective value against other actions spent setting priority. |

The draft access inconsistency needs an explicit smoke test: API prose says `game_map.camp_groups()` is empty during draft, while the SDK implementation docstring describes map camp data as static and available. Build a tiny draft probe and query actual runtime on multiple maps. If unavailable, draft using team size, accessible terrain/altar data and observed champion picks only; gameplay bots can read static groups after draft. Do not infer API access from source comments alone.

## 9. Benchmark and experiment programme

### Opponent and roster matrix

Maintain versioned, deterministic-if-supported bots for:

| ID | Opponent/proxy | Purpose |
|---|---|---|
| B0 | Original Python starter bot | Measures baseline lift and guards against regression to starter behavior. |
| B1 | Improved nearest-profitable-camp farmer | Separates economic route quality from starter flaws. |
| B2 | WHIM-inspired Ryth + Varg + Vendetta proxy | Tests a leaderboard-informed roster with our policy; **not a copy of WHIM**. |
| B3 | Vendetta + Varg + Cassi & Issac proxy | Tests reset/splash plus additional-body coverage and linked risk. |
| B4 | Tavi + Varg + Marcella challenger | Tests original shortlist, field investment and stun immunity. |
| B5 | Aggressive PvP / carrier assassin | Tests combat, bag protection and disengagement. |
| B6 | High-efficiency farmer | Tests whether our routes/tempo are competitive without combat. |
| B7 | Frequent-banking bot | Tests whether we are over-banking or allowing inefficient channels. |
| B8 | Large-bag hoarder | Tests punishment, threat response and denial timing. |
| B9 | Altar-lock and capture-denial bot | Tests contested capture persistence, alternate altar and interruption. |
| B10 | Current best bot mirror | Detects asymmetric or unstable policy, side bias and regressions. |

First compare compositions using the same policy. Separately compare policies on fixed rosters (especially B2 roster). If budget allows, use a small factorial design for key roles: Vendetta on/off, Varg on/off, Ryth vs Cassi & Issac, and policy features on/off. Do not attribute a win-rate gain to a champion if the bot policy changed at the same time.

### Tools and matchup protocol

Use installed `cambc build`, `cambc run` and `cambc run-batch`, recording CLI version/options, bot artifact hashes, map, round cap, fuel, timeout, side, opponent version and date. Save `.replay` and completed-match statistics for representative and anomalous games. Runner help exposed no seed option; if this remains true, document seed control as unavailable and use many games, both starting sides, and same-map paired batches. Do not claim statistical significance from a handful of games.

Suggested sequence:

1. Run a smoke batch over all nine maps against B0, both sides, to find crashes, fuel failures, and obvious map-specific loop failures.
2. Run targeted policy/roster comparisons against B1–B4 across every map on which the composition is legal; run both sides and pair configurations as closely as runner permits.
3. Add adversarial B5–B9 tests after their roles exist. Record the exploit each bot tests, not merely win/loss.
4. Run mirror B10 repeatedly. Analyze side bias, camping/oscillation and draw/round-cap behavior.
5. For promising differences, start with at least 30 paired games per important matchup/map-side cell where compute permits; report uncertainty and raw counts. Increase sample count when confidence intervals overlap or map variance is large. For preliminary smoke, label results exploratory.
6. Keep a held-out map/opponent/version slice for promotions so tuning does not simply memorize the benchmark.

No new runs or score claims are included in this planning document.

### Required metrics

1. Win rate and outcome distribution per opponent, map and starting side.
2. Round/turn of first 1,000-gem tribute and each preceding tribute.
3. Gems tributed per 100 rounds and percentage of captured/carried gems secured.
4. Gold earned, gold spent, purchase timing and marginal actions saved.
5. Camp full-group clear time, capture completion rate/time, resets, and reward split.
6. Turns spent moving, attacking, casting, channeling, idle, returning and failed actions.
7. Deaths, death cause, gems lost, enemy bags captured, and linked Cassi & Issac deaths.
8. Vendetta kill resets/casts and Varg splash targets/damage versus available opportunities.
9. Objective switch count, stuck events, duplicate assignments, travel distance and unreachable goals.
10. Fuel minimum/maximum/median, crashes, invalid actions and run failures.

### Ablations and promotion standard

Toggle one feature at a time where possible: melee attack-while-moving awareness; Vendetta reset target ordering; Varg splash target selection; Cassi pair risk separation; objective hysteresis; portfolio assignments; purchase logic; bank risk policy; lock response; map-specific prior. Compare across multiple maps and opponent types, not just aggregate Elo proxy.

Promote a feature when (a) its implementation passes correctness fixtures, (b) paired matches show a repeatable gain in secured-gem tempo or win probability on its intended cases, (c) no material regression appears against a plausible counter or held-out map, and (d) fuel and invalid-action rates remain safe. Keep specialist features conditional if their benefit is narrow. If results are mixed, retain the feature behind a policy switch or reject it; do not rationalize noise as confirmation.

## 10. Adapt as the competition evolves

Keep a dated snapshot table of leaderboard rank/Elo/record and recent champion popularity, alongside available match-group results and direct links. Track pick-frequency changes over time rather than treating the “last 50” panel as a season-long fact. Distinguish high Elo with many matches and repeated results from small-sample early streaks. Public champion choices do not reveal match-by-match synergy, policy or causality.

When a composition becomes common:

1. Add it as a benchmark proxy and build a counter that tests its actual likely strengths (e.g. stun resistance/control, ranged spacing, focused carrier pressure, or objective denial).
2. Preserve general baseline tests so a counter does not weaken farm tempo against the rest of the field.
3. Review performance by opponent type and map. If losses cluster on one map, verify resource routes and side before changing champion rankings.
4. Maintain versioned known-good bot artifacts, matchup result files, replay links and a change log with expected mechanism and outcome. Compare candidates against the current best before promoting.
5. Update champion value by **marginal team contribution** and role interactions, not raw pick frequency. Use controlled roster swaps and held-out tests to prevent overfitting to one popular competitor.
6. Revisit leaderboard and strategy data on a regular cadence (e.g. weekly or after meaningful competition updates); do not react to a single match or one narrow streak.

The goal is a strategy-discovery process: leaderboard signals nominate tests, the benchmark suite determines whether an idea works for us, and anti-meta testing checks whether it survives informed opposition.

## 11. Risks, failure modes and open questions

- **Leaderboard confounding:** champion frequency and Elo correlate but do not explain wins. Exact compositions and match policies are unknown.
- **Map metadata availability:** `camp_groups()` during draft is contradictory between API prose and SDK documentation; runtime behavior must settle it.
- **Map summary precision:** editor totals are static map facts, not proof of optimal routes. Camp positions, altar adjacency, choke/path distance and spawn symmetry need explicit API/editor extraction before map-specific policy.
- **Runtime access to outcomes:** confirm whether replays and completed-match stats expose reliable per-turn resource/action data; if not, add debug logging without exceeding fuel/output limits.
- **No seed flag observed:** no seed control appeared in CLI help during prior inspection. Batch comparisons must use larger samples and side balancing.
- **Action-order detail:** ability resets, movement/attack sequencing, capture-vs-channel payout and priority timing are easy to misread from high-level prose. Build fixtures before relying on them.
- **Model uncertainty:** danger probability, future respawn and gold shadow price can be misestimated. Start with simple transparent rules and compare prediction to realized results.
- **Overcoordination:** eight shared mutable bytes cannot hold a rich global world model; stale messages and non-shared vision can cause duplicate or unsafe assignments. Every champion needs local fallback.
- **Cassi & Issac correlated loss:** the extra body advantage may be erased by one kill, especially if both carry gems or share exposure.
- **Fuel and complexity:** per-turn full-map searches or deep opponent simulations can exhaust Wasmtime fuel. Profile worst-case map and combat visibility before expanding search.
- **Contest opportunity cost:** endless PvP over a camp or altar can lose the economic race. Make combat value explicit and abandon non-profitable contests.
- **Map-specific overfit:** specialized opening routes can fail when contested or stale. Preserve alternate objectives and a general fallback.
- **Corners result data caution:** the reported loss is a valuable test case but its small sample and potentially changing page figures do not establish systematic weakness.

Open questions for the first coding/verification cycle:

1. Does draft runtime expose all camp groups despite the API documentation claim?
2. What exact per-turn logging and completed stats can `cambc run` and replay files provide?
3. Does every supported map have profitable altar-adjacent capture geometry relevant to tribute snapshotting?
4. Which champion/item thresholds actually reduce full group clear turns, and what purchase opportunities are legal per action sequence?
5. How do maps’ spawn-to-camp/altar shortest-path distances and reachable approach tiles compare?
6. Which action reset/dash combinations are legal in each order under runtime action allowances?
7. How consistent are the leaderboard’s displayed recent-pick counts and match groups over time?

## 12. Changes recommended for the original plan

Keep the original plan’s reliable capture/tribute focus, API-safe actions, uncertainty labels and incremental implementation. Amend the original choices as follows:

1. **Replace the provisional Tavi + Varg + Marcella “foundation” with a controlled shortlist.** Include Vendetta + Varg + Ryth and Vendetta + Varg + Cassi & Issac as leading proxies, retain Tavi + Varg + Marcella as a serious challenger/counter roster, and do not crown a winner before tests.
2. **Promote straightforward champion-critical behavior into Stage 1.** Vendetta kill-reset awareness and Varg legal splash-aware target selection belong in the first functional baseline; deeper sequence optimization remains a later ablation.
3. **Make full-cycle secured gem rate the explicit objective function.** Include capture time/splitting, altar approach/channel, death risk, gold’s marginal value and assignment conflict in target ranking. Compare a short repeatable cycle with maximum gross camp reward.
4. **Add melee action-economy as a logged hypothesis.** Measure movement-plus-attack turns versus ranged range/safety and spell value; do not encode “melee is better” as a universal rule.
5. **Add an evidence-backed map appendix.** Record current map sizes/team sizes, groups/camp counts and reward totals, then calculate actual path/altar/choke features before adapting drafts. Investigate Corners without attributing the single loss to layout.
6. **Expand benchmarks into roster × policy × opponent comparisons.** WHIM-inspired compositions are proxies, not reconstructions. Use fixed policy to test champions and fixed roster to test algorithms, plus sides/maps/mirror and opponent archetypes.
7. **Move initial exploit work toward low-cost, high-impact tests while keeping it out of the baseline.** Test tribute snapshotting, safe range-four farming, Vendetta resets and action sequencing with fixtures and clear integration gates.
8. **Correct the experiment-log tooling assumption.** `cambc run`/`run-batch` and replay/statistics support are available locally; the inspected CLI help showed no seed parameter. Revise test procedures accordingly when implementation begins.
9. **Resolve the draft map API mismatch empirically.** Do not depend on `game_map.camp_groups()` in drafting until a runtime probe confirms it.
10. **Introduce a promotion rule and meta-update workflow.** Keep known-good versions, ablate changes, require repeatable paired gains on intended maps/opponents and hold out tests against overfitting.

## Final recommendation

Start with a dependable end-to-end camp, capture and tribute loop. Keep Vendetta and Varg’s basic legal kit usage in scope from the beginning, but hold champion rankings open. Treat **Vendetta + Varg + Ryth** and **Vendetta + Varg + Cassi & Issac** as the first leaderboard-informed proxies, and test them against **Tavi + Varg + Marcella** under identical policies. Build the objective function around expected gems permanently secured per estimated cycle, then use replay/statistics and ablations to determine whether melee action economy, resets, splash, extra bodies or scoring discipline actually explain gains.

This recommendation is deliberately less certain about a fixed roster than the original plan. Its advantage is a short path to a playable, measurable bot and an experiment structure that can discover when popular mechanics help, when they fail, and what an opponent can do about them. No leaderboard observation or unverified timing interaction should become a single point of failure.

## User-reported meta signal and local rally experiments — 2026-10-14

The user reports that leading teams split units for resource gathering, then regroup to submit gems and enter dangerous areas. This should guide the next competitive hypotheses, but remains user-supplied rather than independently verified ladder intelligence.

E05 roster screens tested Cassi & Issac with Stellar/Tavi and with Varg/Vendetta while leaving G2 gameplay fixed. Neither broadly improved over G2. E06/E07 tested pair-specific recall and did not improve the result. An audit found E08/E09 changed inactive `bot.py` while `src/main.py` loads `simple_policy.Bot`; those runs are invalid rally tests.

E10–E13 exercised the active policy. Full-team escort gave up too much gem throughput; one rotating escort reduced deaths but trailed G2's submitted gems across the full matrix. Escort near the altar won 6/8 in a four-map pilot, then only 1/4 against the corrected carrier hunter and 2/4 against altar denial. E14's compact full-cycle camp estimate won 3/8 and submitted 1,182 fewer gems than G2, despite 53 fewer deaths. G2 remains the protected local champion. No official competition action is authorized or performed.

## Updated evidence and operating rule — 2026-10-14

An active-module audit found that E08 and E09 placed their coordination changes in `bot.py`, while `src/main.py` loads `simple_policy.Bot`. Those runs did not test rally behavior. Later experiments changed the active policy: whole-team escort lost too much gem throughput; one rotating escort reduced deaths but still trailed G2's score over the full map/side matrix. Escort near the altar won 6/8 in a four-map pilot, but only 1/4 against the corrected carrier hunter and 2/4 against altar denial. The result is promising for ordinary farming matchups but not robust under pressure.

A compact full-cycle camp-ranking experiment (E14) also failed: 3/8 against G2 on four maps and 1,182 fewer submitted gems, despite 53 fewer deaths. The approximate geometric model and no target persistence were not enough to beat nearest-camp routing. This supports a simpler, evidence-first approach: retain the fast proven farm loop, add only a few conditional decisions with clear triggers, and measure the action opportunity cost.

The strategic score to optimize is **net secured gems per action**. Farm and bank as the default. When an enemy carrier, altar channel, or valuable capture presents a concrete opportunity, estimate the enemy gems prevented or carrier value protected against the own farming tempo lost. Regroup, attack, or lock only when the expected swing is favorable. Keep these conditions local and cheap; do not add a general opponent simulator or complex map-wide utility search without evidence that it improves gem throughput under the 2,500,000 fuel budget. E15's in-range nonlethal carrier targeting also failed to improve its four-map G2 pilot (4/8) and lost 0/4 against the carrier hunter, so retain the champion's lethal-carrier attack rule. G2 remains canonical; E13–E15 are unpromoted challengers.

## Simplicity check and E16–E22 results — 2026-10-14

The user cautioned against adding too much strategy and fuel cost. Treat this as a design constraint: keep the proven split-farming and immediate-banking loop; add one local condition at a time, and count only gains in permanently submitted gems that justify the actions and computation spent.

E16–E21 did not establish a robust upgrade. The shared threat/escort design reduced deaths but lost score to G2 and failed against the carrier hunter. Lock purchases and fixed escort roles also did not repay their opportunity cost. E17's one-Varg carrier intercept won 10/18 against G2 and submitted 522 more gems in the clean full-map matrix. Full G2 baselines are now available: G2 itself goes 6/18 against the carrier hunter and 9/18 against altar denial. E17 falls to 5/18 against the hunter (436 fewer submitted gems and 14 more deaths than G2), but reaches 10/18 against altar denial (one more win, while submitting 74 fewer gems and recording seven more deaths). This mixed result suggests a possible opponent-specific effect, not a general upgrade; do not add pursuit to the champion.

E22 tested a simple banking condition: keep farming a bag below 20 gems unless a visible enemy is within four tiles, then bank. It exactly matched G2 on the four-map, both-side ordinary pilot and remained 0/4 against the carrier hunter with the same submitted-gem total as G2's earlier pilot. Reject this threshold and retain immediate positive-bag banking.

All these runs completed at the 2,500,000 fuel cap without reported faults, but the runner does not export peak fuel. Do not infer the fuel cost of an algorithm from line count or successful completion alone. Keep G2 canonical. E23 tested the proposed separation of defensive regrouping from offensive carrier pursuit; see the follow-up results below.

## Follow-up: defensive guard and meta draft screen — 2026-10-14

The matched pressure baselines are now full-map and both-side: G2 scores 6/18 against the carrier hunter and 9/18 against altar denial. E23 tested the proposed one-body defensive guard (Varg moves beside a nearby threatened ally carrier). It went 5/8 against G2, but 0/4 against the hunter and 2/4 against altar denial while submitting fewer gems than the proxy. The G2 pilot gain does not survive pressure.

E24 changed only draft order to Tavi, Varg, Vendetta, Ryth, Ren. It went 8/18 against G2 and 0/4 versus the hunter and 1/4 versus altar denial on the pressure pilot. The user-reported popular Varg/Vendetta pairing is not automatically advantageous under G2's farming policy. Keep lineup frequency as a test hypothesis, not a draft rule.

E25 made Tavi reserve her available stun for a visible enemy channel or an enemy near an allied carrier. On Corners, Interlock, Lanes and Packs from both sides, it went 3/8 against G2, 3/8 against the carrier hunter, and 3/8 against altar denial. It submitted 510 fewer gems than G2 in the hunter suite and 692 fewer in the altar suite. This direct interrupt was not enough to repay the spell opportunity cost; reject it.

Current evidence favors the compact G2 farm-and-bank loop over richer escort logic, the tested meta draft, and the stun trigger. Keep every challenger separate. The next pass should inspect the core camp-to-capture-to-bank cycle and per-map loss patterns for a concrete source of missed gems before adding another tactical rule.

## E26: simple purchase conditional — 2026-10-14

E26 made one small change to G2's shopping rule: Varg buys one Durability Health shard, then follows the existing Power Strength purchases. Its draft, target selection, combat and farm/bank behavior were unchanged. Varg bought exactly one such shard per match. The challenger built and completed 54 local matches (all nine maps, both sides, against G2 and both pressure proxies) at 2,500,000 fuel per turn with zero reported faults.

E26 scored 8/18 against G2 (16,492 submitted / 17,626 collected, 270 deaths) while G2 scored 10/18 (17,051 / 18,272, 264 deaths). Against the carrier hunter it went 7/18, submitted 15,156 and recorded 299 deaths; G2's matched full baseline was 6/18, 15,461 and 274 deaths. Against altar denial it went 11/18, submitted 13,098 and recorded 205 deaths; G2's baseline was 9/18, 13,437 and 205 deaths. The higher proxy win counts do not compensate for lower secured-gem totals, and ordinary head-to-head regressed.

Reject E26 and keep G2 canonical. This experiment supports the user's simplicity constraint: a small condition is still unjustified when it spends early Strength and does not improve submitted gems. Continue with the proven split-farming and immediate banking policy; next candidate should target an observed source of score loss and be measured by submitted gems before win count alone. Fuel headroom remains unknown because result exports do not include peak consumption.

## E27: one capturer per cleared group — 2026-10-14

The capture rules say allies do not shorten the five-round timer and split the payout if present at completion. E27 adds a local condition only while a cleared group is awaiting capture: keep one occupant on the group and send other occupants or approaching farmers to another available group. It does not check the occupant's bag, while G2's immediate-bank rule makes loaded occupants leave. This avoids the broad E01 heuristic, which excluded goals near any ally regardless of capture state and lost 0/4.

E27 completed full nine-map, both-side matrices at 2,500,000 fuel per turn with zero faults. Against G2 it went 10/18, submitted 15,990 / collected 17,080, with 273 deaths; G2 in the paired games went 8/18, 16,069 / 16,868, with 244 deaths. Against the carrier hunter it went 7/18 and submitted 15,242; G2's full baseline was 6/18 and 15,461. Against altar denial it went 11/18 and submitted 13,204; G2's baseline was 9/18 and 13,437. E27 actually collected more than G2's pressure baselines (17,158 vs 16,614 against the hunter; 14,990 vs 14,790 against altar denial) but deposited less. The win-count signal is positive, yet submitted gems fell and deaths rose against every comparison.

Champion end stats also show the intervention changed reward distribution: E27's Varg collected 7,280 gems in the G2 matrix versus G2 Varg's 4,946; E27's Tavi collected 1,260 versus G2 Tavi's 2,039. This is consistent with a richer carrier being exposed, though final stats do not prove the cause of the death increase. Do not promote E27. E28's empty-bag reservation check and E29's threatened-carrier guard had no measurable effect in their pilots. Keep G2's banking and navigation core unchanged.

E28's four-map, both-side pilot against G2 and both pressure proxies completed without faults. All 24 result JSON files were byte-for-byte identical to E27's matching pilot files, so the empty-bag refinement produced no observable change. E29 then added a Tavi guard for a Varg carrying at least 50 gems under visible threat. Its 24 G2/proxy pilot files were again byte-for-byte identical to E27's, and it tied E27 directly 4/8 with identical aggregate stats. Reject and archive both without spending full matrices on no-op changes. Next, inspect the map-specific collection-to-submission gaps and identify a concrete farm/bank bottleneck; don't layer another tactical response onto E27.

## E30 and simpler-core direction — 2026-10-14

E30 gave a rich carrier a threat-avoiding route to an altar when an enemy was visible. This was one bounded conditional with a normal-route fallback, yet it lost one win in each four-map suite against the matched E27 pilot and lost submitted gems to the carrier hunter. Reject it; fewer deaths in two suites did not repay the added route work in score.

The user emphasizes that strong performance should come from an efficient core, with only a few conditional decisions. Keep G2's split farming and immediate banking as the baseline. First measure where its farm/capture/bank cycle spends turns and computation; make one change only against a concrete bottleneck, and judge it by secured gems and opportunity cost. Match completion at 2,500,000 fuel demonstrates that the candidate stayed within the cap but does not measure peak fuel. Do not claim exact fuel reductions until the runner or explicit in-bot telemetry provides them.

## Correct-cap audit — 2026-10-14

The earlier `--fuel 2500000` runs used the runner's base quantum; Python received 25× that value. They allowed 62,500,000 Python fuel, so they are useful exploratory comparisons but are not official-budget evidence. The correct command for 2,500,000 Python fuel is `--fuel 100000`.

At the corrected cap, G2 reproduced 16/18 versus starter (17,707 submitted / 18,608 collected, 254 deaths), and scored 7/18 against both pressure proxies. Its hunter suite was 14,547 / 16,058, 265 deaths versus the proxy's 16,295 / 17,058, 233 deaths; its altar-denial suite was 11,843 / 13,052, 190 deaths versus 13,471 / 14,936, 207 deaths. All 54 matches reported zero faults.

E13's full corrected suite improved the G2 mirror (10/18) and reduced altar-denial submissions, but lost both pressure suites (5/18 each). E30's safe-bank rule lost its G2 mirror (3/8) and did not improve proxy wins (2/8 each). E17's one-Varg intercept lost 1/8 to the hunter. These targeted tactical rules do not beat the simple G2 core broadly.

E05A changed only the roster to Cassi & Issac / Stellar / Tavi. At the corrected cap it tied G2 9/18 in the mirror and scored 8/18 against each pressure proxy, one more win than matched G2 in both cases. It improved the score differential against both proxies, while recording 129–131 extra deaths; against starter it won 15/18, one fewer than G2. Keep E05A as the active pressure-roster challenger. E06 and E33 tested simple linked-pair survival conditions; their complete findings follow. Retain G2's core policy and the user's simplicity constraint.

## E32: lower-cost nearest-goal navigation — 2026-10-14

E32 kept E05A's composition and turn policy but replaced the multi-goal distance-field/reachable-tile search with geometric nearest-goal selection plus SDK pathfinding. On Corners, Interlock, Lanes and Packs, both sides, at `--fuel 100000`, it won 1/8 and submitted 3,160 / collected 3,422 gems with 87 deaths. E05A submitted 7,680 / collected 8,212 with 140 deaths. Both completed without faults. The lower death count did not repay the lost farm throughput; reject this navigation shortcut. The result does not measure fuel savings because the CLI exposes no per-turn fuel usage. Keep the proven G2 core and accept a simpler replacement only when it preserves secured-gem output.

## E06: corrected-cap pair retreat — 2026-10-14

The earlier E06 matrix used the wrong Python fuel quantum, so the exact 50% no-bag retreat rule was rebuilt and run at `--fuel 100000`. Across nine maps and both sides it went 6/18 vs G2 (15,470 submitted / 17,054 collected; 398 deaths), 8/18 vs the carrier hunter (15,132 / 16,946; 389 deaths), 11/18 vs altar denial (13,032 / 16,118; 414 deaths), and 14/18 vs starter (16,698 / 18,034; 409 deaths). All 72 matches had zero faults.

E06's altar-denial differential improved substantially: 13,032 own gems versus 12,012 for the proxy, compared with E05A's 11,347 versus 12,611. Against the hunter, E06 submitted 431 fewer gems than E05A and let the proxy submit 617 more. It lost three G2 mirror wins versus E05A. Pair deaths were higher than E05A in each pressure suite (202/194/238 vs 194/182/168 against G2/hunter/altar). This is an altar matchup shift, not a pair-survival upgrade. Reject as the general bot.

## E33: threatened pair retreat — 2026-10-14

E33 restricted the 50% threshold to bag-empty Cassi/Issac below 50% health when an enemy was visible within four tiles; otherwise the established 35% rule remained. Its four-map/both-side screen completed 32 matches with no faults. It went 5/8 vs E05A (7,040 submitted / 7,744 collected; 145 deaths), 4/8 vs G2 (6,806 submitted), 2/8 vs the hunter (7,246) and 3/8 vs altar denial (5,486). Matched opponents submitted 7,132 / 7,878 / 6,004 gems. Reject the threat gate; it does not preserve pressure score.

## Map-level readout

`bots/larpbot/STRATEGY_MAP_BREAKDOWN.md` compares E05A and G2 against both pressure proxies. E05A loses both sides to the hunter on Elkring and Expanse; Expanse is also a two-side loss to altar denial. Elkring is opponent-dependent: E05A scores much better than G2 against altar denial but worse against the hunter. Interlock shows the opposite split, with a 2/2 hunter sweep and 0/2 against altar denial. These crossovers are evidence against a universal retreat/escort toggle. Keep the core simple; choose the next strategy around verified map/opponent behavior rather than aggregate deaths alone.
