# Anchor: safe income, local superiority, controlled expansion

**Status: researched design and implementation plan, not a built or validated bot.**

The goal is a bot capable of competing around the top 100, with a foundation we can improve deliberately. Rank is an empirical target. No design can guarantee it before playing. The immediate deliverable is a coherent strategy, executable decision contracts and a build sequence that proves those contracts before relying on aggregate win rates.

## 1. The game we should play

Start by securing repeatable income in territory we can safely use. Spread out only as far as each worker can finish its job and escape. When a valuable next objective cannot be taken alone, assemble the smallest useful group at a safe staging point, take that objective, then distribute again. Fight to obtain or protect resources, deny a meaningful enemy deposit, or create safe space. Do not fight merely because an enemy is visible.

The recurring loop is:

**Scout the next route → take a safe camp cycle → finish capture → bank efficiently → recover or redeploy.**

When that loop is blocked:

**Identify the blocker → choose another safe cycle or assemble support → clear one objective → reassess.**

The principal resource is productive champion time. Death costs a bag, possibly hands it to the opponent, removes the champion for 60 turns and gives up map access. For the cats it removes two workers. But grouping five healthy workers around one small bag also destroys productive time. We must measure both loss and inactivity.

### Concrete examples

| Situation | Intended decision |
| --- | --- |
| Issac sees two healthy enemies covering the next camp; Cassi is too far away to influence their next attacks | Reject the advance. Ward the approach, move toward safe farm or a reachable rally, and keep the dash for exit. |
| Two enemies are low enough to die to a verified legal sequence, with no plausible lethal response | Allow the fight if it yields useful space or gems. Headcount alone is not the decision. |
| Cassi is threatened while Issac holds 120 gems elsewhere | Treat both bags and both workers as exposed. Cassi disengages; Issac stops taking additional risk and banks if safe. Neither blindly crosses the enemy to rescue the other. |
| Three allies arrive at an empty reward region | One captures; others clear nearby safe work or cover approaches. Extra occupants do not speed capture. |
| No safe local camp remains, but a neighboring camp is profitable with one helper | Request a short rendezvous behind cover. Advance only after the helper is actually able to contribute. |
| Help fails to arrive | Cancel the push at its deadline. Rotate, bank, scout or recover; do not wait indefinitely or advance alone. |
| A safe deposit will reach 1,000 | Protect and complete it. Stop taking optional farming and combat risks. |

## 2. What the evidence changes

Our current bots are not implementations of their most ambitious documents. Both D1 and gold_diamond run compact nearest-camp policies. Carriers bypass enemy tactics; PvP ability handling is missing or limited; the cats are independent workers with correlated deaths. The disabled richer policy still checks danger too crudely and cannot reliably reject a lethal destination. [Implementation audit](IMPLEMENTATION_GAP_AUDIT_2026-10-15.md).

The old regroup and pair-safety results do not reject the strategy above. E42 only changed camp filtering on enemy contact. E33 used a health threshold and recall. E30 fell back to unsafe routing if its danger mask prevented progress. E08/E09 changed an inactive module. Other escort experiments genuinely lost economic tempo. Preserve those lessons without pretending the full ideas were tested. [Past bot audit](PAST_BOT_AUDIT_2026-10-15.md).

The external gap is large: D1's recorded 103/126 local wins became 0/25 against live leaders; gold_diamond went 0/20 against teams down to rank 283. Our local opponents are useful regression fixtures, not a representative competitive field. [D1 live evidence](../../bots/D1/D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md), [gold_diamond live evidence](../../bots/gold_diamond/ONLINE_LADDER_RESULTS.md).

Today's top-team replays show two distinct games. Fish beat Hyperion on Expanse with 28 camps to 24 and zero kills or deaths on either side. Hyperion won Interlock with 27 camps to 26, four kills to two and 1,066 banked gems to 762. We need economic efficiency and competent contact decisions. Neither permanent grouping nor pure avoidance solves both. [Live replay notes and links](LIVE_REPLAY_NOTES_2026-10-15.md).

## 3. Safe production and the map

### Define a job as a complete resource cycle

A camp job includes approach, clearing every member of the group, capture, leaving the spawn tiles, and a credible route to bank. A nearby gem cluster is not a separate reward if connected to a dangerous camp group. Monster HP, incoming damage and capture delay all matter. Gem clusters have 500 HP, no damage and 24 gems each; wolves have 1,350 HP, 20 damage, 22 gems and 90 gold. This makes clusters attractive for immediate score, while gold-producing camps can fund useful upgrades. [Mechanics audit](MECHANICS_AUDIT_2026-10-15.md).

Choose among a small set of reachable candidates. First reject infeasible cycles; then rank the remaining ones. Use path distance to legal attack/capture tiles, not straight-line distance to the group's center. Estimate remaining work from visible HP and champion-specific legal action sequences. Unknown camp state has an uncertainty cost and a scouting step.

```text
cycle time = approach + remaining clear + capture + bank detour + channel + recovery
cycle value = deliverable gems + near-term upgrade benefit - exposure cost
priority = cycle value / max(1, cycle time)
```

This is an ordering heuristic, not a claim of calibrated death probabilities. Hard survival checks happen before the score. Gold's value is the next useful purchase and how many subsequent cycles can repay it; reduce that value as the match approaches its finish. Do not spend the last part of the game farming gold that will never become useful strength.

### Use productive areas, not permanent ownership

Opening routes give each body a preferred safe area and avoid immediate duplication. These are preferences, never exclusive partitions. Camp reservations are soft hints. If an ally is clearing efficiently, prefer comparable free work; join when extra damage materially shortens a safe clear or protects a threatened capture. Reserve one capturer only after the group is actually cleared and the intended capturer can hold it.

Track a local frontier from terrain, recent contacts, usable altar approaches and verified allied presence. Enemy spawn distance is a weak prior, not proof that an area is safe or hostile. Do not let an unseen enemy permanently prohibit an entire half-map. Old sightings create expanding uncertainty, which can be resolved with wards and scouting or bypassed by another route.

Remember profitable respawn cycles, but never stand on a collected camp's spawn tile and suppress its respawn. A near-complete capture deserves persistence only while its hold remains survivable; sunk clearing time does not justify feeding both cats.

### Banking is a route and a channel

Compare banking now with one additional safe cycle. Bank when already near a safe altar, when continuing has poor marginal value, when exposure is growing, when the bag has been carried too long, or when the deposit wins. Continue nearby safe work only when the extra return outweighs the added exposure and delay. Avoid a universal large-bag threshold and avoid the current unconditional positive-bag detour.

Before starting, assess the entire remaining channel: `ceil(bag / 10)` turn-end ticks, followed by completion at the owner's next turn start. A 100-gem bag immobilizes its carrier for much longer than a 20-gem bag. Incoming nonlethal damage alone does not interrupt tribute; stun, death and enemy locks do. During the channel, still observe and decide whether continuing or cancelling survives. A winning safe channel should not be cancelled merely because a health threshold was crossed.

Distinguish friendly locks from enemy locks. An enemy lock may be worth clearing if three attacks are cheaper and safer than the alternative route. If all approaches are unsafe, use a safe holding position, request the minimum useful support, rotate to another altar or retreat to safety. Never let failed banking fall through to a known lethal route.

## 4. A fight evaluator that answers the actual question

The question is: **after this action, what can hit us before we can respond, what can our allies actually do in time, and what do we gain?**

### Build a conservative response envelope

For each candidate action sequence and final tile:

1. Estimate damage/control before the acting champion's next turn, then a second response horizon for escape and commitment.
2. Include enemies that can walk, dash, attack or cast legally, taking ranged movement/attack exclusion and one-cast-per-turn into account. Do not add every ability as if all can be cast together.
3. Include camp damage before the next champion phase. A neutral camp can finish a champion that survives the enemy attack.
4. Respect known current action completion and alternating team order. Unknown scheduling or cooldowns use the worst plausible legal case, not imaginary certainty.
5. Count allied support only if a visible, healthy ally can contribute before the relevant lethal response. A shared intention or a distant body contributes no guaranteed damage or rescue.
6. Apply shields and mitigation sequentially. Do not subtract one shield independently from every hit. Credit a stun only if the plan can actually apply it before the target acts.
7. Check an exit that remains usable after the exchange. A nonlethal forward step can still be a trap.

Exact cooldown and action-order access needs an engine fixture before enabling prediction based on it. Begin with conservative legal envelopes and refine only where measurement shows overcaution. Predictions are bounds with known/unknown fields, not a single unexplained danger number.

### Admission rules

Reject a voluntary approach when it creates lethal exposure, has no credible escape through the second horizon, or requires unsupported allies to save it. An unsupported healthy 1v2 without a verified quick kill fails the initial rule. A 2v2 can also fail if our caster is one hit from death or their stun lands before our support acts.

Among survivable plans, compare the resource outcome: protected deposit, stolen bag, completed capture, safer next farm cycle, lost farming time and possible deaths. A stolen bag changes both teams' potential score. For a rough value comparison, losing a bag `G` to an enemy costs up to `2G` in relative opportunity, plus recovery and map access; it is not already-banked score. Keep this separate from certainty about whether either team would successfully bank it.

Allow narrow explicit exceptions for a verified immediate winning deposit or preventing an otherwise imminent certain loss. Record the exception. Do not use a generic aggression multiplier to turn safety off.

### Execute useful combat

Choose one locally shared focus target from actual kill feasibility, enemy carried value, threat removal and objective relevance. Target the vulnerable cat when it safely removes both opposing bodies. Do not chase an unseen low-health target past the last safe exit.

Use the whole kit: walking-compatible control while withdrawing, shields before the response, resets after basic attacks, ranged damage when holding position is safe, and movement abilities when they create a safe useful end state. A ranged basic attack can consume the escape move; action ordering must evaluate that trade before attacking.

If already trapped, choose the least damaging feasible response: shield/stun and leave, a verified kill that removes incoming damage, or movement that reduces exposure. Holding still is a candidate, not an automatic answer. Preserve safety under reduced planning budget.

## 5. Regrouping and pushing

Regrouping is worthwhile when a named objective has better expected value with a small group than the members' independent safe jobs. Examples: opening an altar approach for a valuable carrier, taking a high-value contested camp, dislodging a weaker isolated enemy, or defending a nearly finished capture. Lack of a nearby camp alone is not an order for the whole team to cluster.

Every regroup mission has:

- A reachable rally behind the contact line, away from hostile camp range and outside dangerous area-effect overlap.
- One concrete objective and a fallback objective.
- Required contribution, such as one healthy frontline body plus one ready source of control—not merely a headcount.
- A latest useful arrival and an expiration time.
- A check based on observed arrivals before anyone commits.

While waiting, take safe actions near the rally: clear a nearby cluster, ward the approach, reposition or bank. Send only the minimum useful help. Leave other workers productive. If no feasible productive waiting action exists, charge that waiting time to the mission; cancel when it no longer pays.

Once assembled, push one objective or one defensible step beyond the current position. Reassess after each move, new sighting, lost ally or used escape ability. Stop when the objective is complete, the advantage disappears, the exit closes, support separates or the deadline expires. Do not turn a successful local fight into an indefinite chase.

At respawn, reconsider the route that just killed us. Record a short-lived local loss marker; regroup, scout or use a different cycle before retrying. A death loop through the same corridor is a distinct failure condition.

## 6. Cassi and Issac: two workers, one survival constraint

Their HP is not a combined health pool. The pair survives only if **both** survive. Every offensive or economic commitment must account for the weaker projected survivor, both bags and both lost production streams.

Use three practical pair behaviors:

| Behavior | Preconditions | Positioning and exit |
| --- | --- | --- |
| Safe parallel work | Both have fresh safe status; jobs are independently safe; no speculative enemy-side travel | Separate nearby routes are allowed. Stale or danger reports end aggressive separation. |
| Supported contact | Partner locally observed; both can survive; support arrives in time | Cassi stays behind a safe front with a legal stun/retreat lane; Issac does not dash beyond support. Avoid exposing both to the same area spell. |
| Pair withdrawal | Either reports danger, one cannot survive the next response, or the plan loses support | Exposed cat exits first if feasible; other cat stops increasing risk and protects/banks its bag. Rescue only if it improves pair survival. |

Cassi's stun and Issac's dash are often the pair's escape tools. When contested, do not spend them on low-value camp damage without showing that the next enemy response is still survivable. In safe territory they may be used for throughput.

An unseen partner is neither healthy nor dead. A fresh report can authorize safe independent work; it cannot authorize a tight two-body combat sequence requiring exact current positions and HP. Aggressive pair maneuvers require local observation. This is a deliberate limit imposed by the game's information model.

## 7. Information and communication we can actually afford

Each body has its own vision and ward; there is no free team-wide live world. Use private recent sightings plus a small explicit shared protocol. The 1,024 draft bytes hold immutable roster/role mapping, map orientation and a bounded set of safe-region anchors. The eight mutable bytes hold advice, never an omniscient team plan. [SDK and mechanics evidence](MECHANICS_AUDIT_2026-10-15.md#5-information-is-local-coordination-must-be-designed-around-that).

**Proposed first protocol, to validate before implementation:** reserve 16 bits for each cat, and 8 bits for each of the other four possible bodies: `2×16 + 4×8 = 64` bits. Fewer bodies leave spare capacity. Cat slots contain region (5 bits), mode (2), self-assessed safety (2), bag band (2), round epoch (5). Other slots contain region (5) and mode (3). Each body owns its own slot. Read/write only documented shared-memory operations; verify that updates preserve every other slot.

Region is one of at most 32 deterministic anchors/areas, not an exact coordinate or a camp handle. Define the table once in draft; safely coarsen if there are more areas. A region hint resolves to local reachable tasks and is not an exclusive camp claim. Cat safety has four values: ready, threatened, recovering, dead. Bag bands communicate exposure, not exact arithmetic. Modes distinguish farm, deliver, rally and push. Noncat modes additionally identify retreat/recovery/death/unknown. Document exact bit ordering and sentinel values before coding.

Cat messages expire after a small number of rounds, initially three as a test parameter. Epoch arithmetic must not revive an unchanged 32-round-old message: each receiver tracks observed slot changes and its last absolute receipt round; after a reader gap or ambiguous wrap, treat it as unknown until a fresh update is observed. Noncat messages have no timestamp in this layout and are never counted as combat support; they are weak routing hints, overridden by current observation. This explicitly trades rich camp claims for pair safety.

Choose rally anchors deterministically from the proposed objective region and safe approach. Read another body's hint as a request, not an order. Arrival and force are verified locally. Protect against oscillating requests using a stable initiator rule, objective persistence and expiration. No unseen promise can switch the fight gate from unsafe to safe.

For the proposed encoding, bytes 0–1 belong to Cassi, 2–3 to Issac, and bytes 4–7 to the other roster slots. Each cat word uses bits 0–4 for region, 5–6 for mode, 7–8 for safety, 9–10 for bag band and 11–15 for epoch. Start with bag bands 0, 1–24, 25–79 and 80+; the top band has no finite inferred upper bound. Noncat bytes use bits 0–4 for region and 5–7 for mode. Draft memory declares the protocol version and slot mapping. An uninitialized slot is invalid until a fresh epoch transition or local observation validates it; zero-filled memory must not imply a ready cat at region zero. Write each cat's complete two-byte slot using the documented buffer write, and test interrupted publication/read behavior rather than assuming atomicity.

The allocation is a design proposal with an acceptance fixture, not a claim that 64 bits can carry complete positions, HP, cooldowns, bags and camp reservations. If it cannot support the required behavior, change the protocol before adding features.

## 8. Roster, roles and purchases

Build reliable behavior for a small roster first. The initial competitive hypotheses are **Cassi/Issac + Stellar + Ren** for contested access, and **Cassi/Issac + Stellar + Varg** where safe clustered clears dominate. They are supported as candidates by live top-team appearances, not proven optimal for us. Start comparison with one fixed roster; do not confound tactical changes with counterdrafting.

The cats supply two useful workers and controlled local pressure. Stellar supplies ranged area damage/control. Ren supplies an alternative frontline/control kit; Varg supplies multi-target clears and shielding. Ryth is the first additional pick for larger rosters; the fifth pick is the remaining supported frontline/clear specialist. All selected champions need functioning abilities in both camp and PvP contexts before their draft is enabled. Tavi, Vendetta and Marcella remain later alternatives tied to a measured problem, rather than more initial implementation branches.

Purchases should improve a role's next useful action. Test Focus on spellcasters and Strength on basic-attack farmers; buy health/mitigation when it changes a survival threshold. Jungle's camp mitigation may matter on dangerous neutral routes; Durability may matter in contact. Do not assume the same Strength-only build is appropriate for every champion. Use spawn/death shopping opportunities, and recall to upgrade only when the resulting improvement repays travel and channel time. Tavi's field health purchase does not heal current damage.

Draft adaptation comes after the policy works: respond to already revealed picks, map access and roster size. Do not tune a map/side pick table solely to beat the local proxy family.

## 9. Implementation foundation

Create a new candidate under `bots/anchor/`. Keep the old artifacts as reference opponents. Begin in the existing supported language/toolchain with compact records, native masks and distance fields. Decide on a language change only after measuring startup and hot-path costs; it must preserve the same strategic contracts.

There is one active decision pipeline. The baseline already includes safety; the reduced-budget path still includes safety. Do not ship an economic fallback that bypasses the advertised strategy.

| Module and small interface | Responsibility and invariant |
| --- | --- |
| `observation.observe(memory) -> View` | Current legal facts, visible units, aged sightings, partner hints and static references. Known, remembered and inferred fields remain distinct. |
| `tactics.assess(view, candidate) -> Assessment` | Response damage/control, timely support, pair survival, escape and reason. Same assessment is used for farm, bank, capture, retreat and push. |
| `missions.choose(view, current) -> Mission` | One job with phase, target region/tile, deadline, cancellation conditions and fallback. Includes economic scoring and bounded rally intent. |
| `actions.plan(view, mission, budget) -> Plan` | Small legal action bundles with final tile, action costs, projected outcome and assessment. |
| `actions.execute(plan) -> Outcome` | Revalidate before each mutation; stop/reobserve when movement, vision, target state or action availability differs. |
| `signals.read/write` | Owned packed slots, freshness rules and conservative decoding. |

Champion kit models live inside tactics/actions, not as separate strategic bots. Navigation proposes legal steps toward objectives, including sideways/backwards escape and staying still; tactics filters them before economic ranking. Cache static terrain and reusable distance fields. Do not build a giant global model before taking the first action.

The plan lifecycle is `observe → select mission → propose actions → assess → execute → publish → end turn`. Tactical danger may interrupt any mission. A mission is not completed by issuing a command: confirm payout, tribute, safe arrival or recovery. The current bot's top-level carrier return and channel return are specifically forbidden shortcuts.

### Computation and action timing

Measure from program entry, before imports and initialization, through first useful action. Compare with a minimal SDK bot to separate runtime startup from our own overhead. Historical round-29/round-71 first-action reports are not acceptable unexplained baselines. Draft precomputation and lazy gameplay initialization must make the first useful action as early as the measured runtime permits.

Bound candidate work: initially shortlist at most 12 nearby/resource-relevant camps and about 24 legal action bundles, then measure. These numbers are tunable starting budgets, not game constants. Cheap current/destination survival assessment runs before optional scoring. If budget runs short, reduce candidate refinement and choose a previously assessed safe action. Never resume stale planning after an involuntary fuel suspension; use epoch checks and explicit turn boundaries. Run at the actual configured competition fuel, not a raised local cap.

### Documentation that stays connected to code

Keep `STRATEGY.md` (decision priorities and examples), `ARCHITECTURE.md` (interfaces/data ownership), `PARAMETERS.md` (units, defaults, reason, evidence), `BEHAVIOR_CONTRACTS.md` (fixtures and production-path coverage), and `RESULTS.md` (artifact hashes, opponents, maps, side, metrics and decisions) alongside the future bot. Every strategic promise links to its active function and behavioral fixture. One startup log identifies policy version/build hash and enabled capabilities.

Use reason codes such as `UNSUPPORTED_CONTACT`, `PARTNER_UNSAFE`, `CHANNEL_EXPOSED`, `RALLY_EXPIRED`, `SAFE_CYCLE`, `WINNING_BANK`. Log mission changes, rejected dangerous moves, successful casts, partner alarms, failed movement, channel interruptions and death context. Rate-limit routine logs; ensure diagnostic instrumentation is included in the measured artifact or measure its overhead explicitly.

### Initial tuning parameters

These are falsifiable starting choices, not rules of the game or claimed optima. Keep them together in configuration and record every changed value with its experiment.

| Parameter | Initial choice | Failure it must avoid |
| --- | --- | --- |
| Combat horizon | Next own response plus one further response | Surviving the immediate hit but becoming trapped |
| Partner freshness | At most 3 rounds, with wrap/reader-gap invalidation | Treating an old safe report as current permission |
| Rally deadline | Latest observed feasible ally arrival + 2 rounds, capped at 12 rounds from proposal | Waiting indefinitely or committing before support; reject requests needing longer travel in the first version |
| Noncat unseen intent | Advice only; expire local reliance after 3 rounds without direct confirmation | Ghost reservations and imagined support |
| Mission switching | New job must beat current feasible job by 25% estimated value; safety/win events override immediately | Repeated retargeting versus stubborn commitment |
| Enemy uncertainty | Expand from last sighting by legal movement opportunities; refresh with personal ward/vision | Erasing an enemy on disappearance or permanently forbidding safe territory |
| Economic/action shortlist | At most 12 camp candidates / about 24 action bundles | Planning cost delaying useful turns |

Use no global HP percentage as the main fight/retreat rule. HP matters through predicted survivability, recovery time and the value at risk. Tune these parameters against traces and held-out opponents, not a single mirror score.

## 10. Build sequence and non-negotiable acceptance cases

| Stage | Deliverable | Gate before proceeding |
| --- | --- | --- |
| 0. Evidence and runtime | Reproduce first-action timing, exact fuel, visibility, action order, pair death, capture and tribute timing | Mechanics assumptions used by the planner have executable evidence; runtime and bot startup costs separated. |
| 1. Safe working economy | Observer, action executor, complete camp/capture/deposit loop plus destination survival veto | Productive safe loop on an open map; unsupported 1v2 rejected; safe alternate route still taken. |
| 2. Useful combat | Champion-specific legal bundles, two-response escape check, target selection and PvP abilities | Fight/retreat scenarios below pass through the same entry point intended for submission. |
| 3. Linked pair | Owned signals, freshness, combined loss and paired withdrawal | Both exposed-cat and safe-partner scenarios work; stale reports never authorize a dive. |
| 4. Team objectives | Soft area hints, minimum useful regroup, arrival checks, one-objective push | A group takes a feasible objective; missing helper expires; unrelated workers keep farming. |
| 5. Economic refinement | Full-cycle scoring, bank-now versus one-more-cycle, role purchases | Income improves without restoring the original dangerous moves; no new indefinite waiting. |
| 6. Competitive evaluation | Frozen bundled artifact, live bracket opponents and held-out maps/teams | Evidence below supports promotion; losses have replay explanations. |

The implementation order can combine stages 1–3 internally, but a build without them is a development baseline, not the proposed strategic bot.

### Behavioral fixtures

These are specified tests to build, not tests already run. Use controlled engine scenarios for mechanics and recorded observations for pure decision checks. Assert outcome and reason, not the implementation's private branch structure.

| Case | Required observable behavior |
| --- | --- |
| Lone healthy unit, two ready enemies, safe alternative path | Does not enter their combined response zone; continues useful safe work. |
| Ally nearby geometrically but behind a wall or acting too late | Does not count that ally as immediate rescue. |
| Visible enemy just outside current basic range with ready dash/spell | Destination check includes its legal next-turn reach. |
| Ranged champion must escape | Does not spend movement on a basic attack or incompatible spell first. |
| Low-health enemy can be safely killed | Takes the valuable verified kill; safety does not become blanket passivity. |
| Camp retaliation plus enemy hit is lethal | Rejects the plan even if either source alone is survivable. |
| One cat endangered, other cat healthy and loaded | Exposed cat withdraws; partner protects combined value and does not dive. |
| Cats on adjacent area-effect tiles | Chooses a formation that avoids unnecessary shared exposure. |
| Partner unseen/stale, epoch wraps or reader skips many turns | No fabricated healthy partner or renewed old permission. |
| Safe empty gem group | Clears, completes capture, banks and leaves respawn tiles; safety causes no paralysis. |
| Near-complete capture becomes lethal | Abandons it safely despite sunk work. |
| Friendly lock, enemy lock, unsafe alternate altar | Correct lock handling; no unsafe fallback. |
| Nonlethal damage during tribute versus lethal/control threat | Continues the safe channel; cancels/repositions only when justified. |
| Regroup succeeds versus helper absent | Commits only with timely support; expires rather than waits indefinitely. |
| All progress moves unsafe | Sideways/backwards movement or least-loss response remains available. |
| Hidden blocker returns false | Refreshes observation and retries safely without assuming action consumption. |
| Recall arrival | Stays for end-turn healing; does not walk out unhealed. |
| Low computation budget and respawn after repeated corridor death | Retains safety and avoids immediately repeating the failed approach. |

## 11. Proving improvement and approaching the top 100

Freeze the exact executable and source hash for each comparison. Repeat an identical artifact only to check reproducibility; do not count deterministic repeats as independent evidence. Record side, map, roster, engine/fuel settings and opponent version where available. The installed CLI previously exposed no seed option; verify current support before claiming controlled seeds.

Use three layers of evidence:

1. **Behavior:** the fixtures above and trace examples prove the promised strategy actually runs. A tactic that never activates is not a tested success or failure.
2. **Local regression:** nine maps, both sides against D1, gold_diamond and distinct adversaries that actually coordinate focus fire, use control, punish cat separation, deny altars or outfarm passivity. Inspect representative losses. Existing related proxies remain a floor, not the promotion authority.
3. **Live competition:** start with a small screen around ranks 200–300; then several teams around 75–125, chosen for differing observed rosters/styles. Use fixed available maps spanning Expanse, Collision/Corners and an obstructed map. Record service-assigned side; do not promise side reversal if the challenge UI cannot choose it. Preserve opponent versions through previous-match challenges when supported.

Proposed promotion panel: eight distinct teams around ranks 75–125, two five-map groups each, split across two observation sessions. Include at least two teams held out from tuning. Require a positive aggregate map record, wins against a majority of the opponent teams, and no repeated catastrophic collapse on contact-heavy maps. These are engineering promotion targets, not a statistical guarantee of rank. A live ranked position sustained around/inside 100 is the actual outcome measure.

Do not demand that every improvement beat every old local matchup. Reject a tactical regression that recreates feeding, but permit a small local score trade when live results and causal traces show the requested strategy working. Keep a frozen previous candidate for A/B comparison. Do not change draft, combat and banking simultaneously and then assign the result to one feature.

Track at least: banked gems over time; captured versus banked gems; carried gems lost (including both cats); camp/PvP deaths; first useful action; clear-to-capture and capture-to-bank delay; productive/idle/rally turns; unsafe-move rejections; successful supported pushes; aborted pushes; repeat corridor deaths; fuel suspensions and invalid actions. Compare checkpoints such as rounds 50, 100 and 200 as well as final totals. Survival with no income fails. High income followed by repeated stolen bags fails.

If a live panel fails, classify the failure before editing: poor camp selection, slow clear, abandoned capture, banking exposure, losing fight admission, incorrect combat execution, stale coordination, startup cost or missing observation. Fix the dominant mechanism and rerun its fixture plus the relevant competitive cases. Avoid another cycle of arbitrary health-threshold tuning.

## 12. First implementation milestone

The first useful milestone is **a complete safe farmer that refuses the demonstrated unsupported dive, uses real PvP escape/control, and protects both cats while still finishing resource cycles**. Show a replay for each behavior and a productive Expanse game before adding advanced push scheduling or draft optimization.

The design deliberately keeps one strategic identity across every stage: earn reliable gems, preserve productive bodies, assemble only useful support, and take one justified objective at a time. The supporting audits record what is documented, observed and still hypothetical; future implementation must retain that distinction.

### Supporting documents

- [Mechanics audit](MECHANICS_AUDIT_2026-10-15.md)
- [Past bot and experiment audit](PAST_BOT_AUDIT_2026-10-15.md)
- [Implementation-pack and source gap audit](IMPLEMENTATION_GAP_AUDIT_2026-10-15.md)
- [Current live replay observations](LIVE_REPLAY_NOTES_2026-10-15.md)
