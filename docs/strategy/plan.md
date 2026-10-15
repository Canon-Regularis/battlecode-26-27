# CAMBC 2026 Competitive Bot Plan

**Status:** planning only; no gameplay implementation or match experiments have been started.

## A. Repository and mechanics assessment

### Repository state

- Event documentation identifies `cambc2026a`. Project configuration is `cambc.toml` with SDK version `2.1.3` and supported project languages `cpp` and `python`.
- The selected implementation target is the Python starter at `bots/starter-python/src/`: `main.py` dispatches draft/game turns; `draft.py` picks randomly; `bot.py` greedily attacks visible enemies/camps, walks toward camp spawn tiles, banks any carried gems, buys a randomly selected Power Shard stat at spawn, recalls below 35% health, and writes round data to shared memory. It has no team objective assignment, matchup-aware draft, item valuation, explicit combat threat model, target-group state machine, or measured purchase policy. Its draft `hello world` is demonstration data, not a strategy.
- `docs/cambc/strategy/` contains five research/blueprint files: `README.md`, `BOT_PLAYBOOK.md`, `CHAMPIONS_AND_BUILDS.md`, `MECHANICS_AND_EXPLOITS.md`, and `EXPERIMENTS.md`. They are hypotheses and proposed experiments, not match results; the experiments log says none have been run. There is no `docs/strategy/` directory.
- The current map pool in `maps/` has nine `.map26a` files: `collision`, `corners`, `elkring`, `expanse`, `interlock`, `lanes`, `monolith`, `packs`, and `rows`. Use actual map queries or match data before labelling one map as clustered, open, or gem-rich.
- Local execution tooling is installed as `cambc.exe`. `cambc run <BOT_A> <BOT_B>` accepts map, round cap, replay, visualizer, fuel and completed-match statistics options. `cambc run-batch` accepts a four-column manifest and parallel job/round/fuel/timeout settings. `cambc build <BOT>` is available. No seed option appears in these help outputs. This corrects the experiment document's claim that no local runner invocation is available; deterministic seed control remains an open tooling question.
- Engine implementation is not present among the checked-in project sources. The runner is an installed external CLI, so authoritative interaction testing must use it and its replay/statistics outputs. Checked-in C++ SDK contract/API tests reference `Engine/` and `Deep/` private/public include trees that are not in this workspace; they are not a Python match-testing harness and may not be runnable here. No Python unit-test suite or bot-specific baseline fixtures are present.
- No `AGENTS.md` or `CONTEXT.md` project instructions were found. The workspace currently has existing user changes/untracked files, including `.gitignore`, `.vscode/`, and the strategy directory; preserve them. `plan.md` is a new root file.

### Rules and API that constrain the design

- Win by tributing 1,000 gems; at the 2,000-round limit compare tributed gems, lifetime gold earned, then champion kills (Team B wins an exact tie). Carried gems do not count until tribute and are lost to enemy kills; camps destroy the bag when they kill a carrier.
- Each team drafts 3–5 selections depending on the map. Cassi & Issac are one selection but two independently acting bodies with linked deaths. The draft bot has 1,024 bytes of memory for match bots; bots also share only 8 match-long bytes. Vision belongs to each champion and its ward, not the whole team.
- A cleared cardinally connected camp group pays only after an uncontested five-round occupation of at least one spawn tile. Emptying or contesting resets capture. Completion-time allies split rewards; additional allies do not speed capture. The group then respawns on the longest member cooldown; any occupied spawn tile delays the group. Camps have range 3, vision 8, see through bushes, do not chase, wake on damage, and sleep after two rounds with no in-range champion.
- Tribute duration is `max(1, ceil(starting gems / 10))` of the owner's turn-end ticks, including the starting turn; completion is at the owner's next turn start once the timer is zero. The whole bag at completion is deposited, captures precede channel completion, ordinary damage does not cancel tribute, but stun, death and an altar lock do. Recall takes five owner turn ends (three with Home), is interrupted by damage/stun/death, and retains gems; spawn heals at the end of the arrival turn if the champion remains there.
- An altar lock costs 10 gold, can be placed within two tiles, blocks opposing tributes, cancels an active opposing channel and is removed by three basic attacks. Items/shards are normally bought on spawn or while dead. Tavi can buy shards anywhere (not consumables); field-bought Health increases maximum HP without healing. Shards cost 30g; five matching shards make an emblem, but the Power family requires six; duplicate family passives do not stack, while shard stats do.
- Turns allow one basic attack, movement subject to champion class/action allowances, and one successful ability cast across both slots. Abilities have eight owner-turn-end cooldowns. Ability-specific walking restrictions matter. Teams alternate who starts each round; higher priority acts first within a team, and a priority update applies next round. World phases (including capture/camp attacks) and channel start/end timing make action order material.
- Python API offers current champion state, `can_move/can_attack/can_cast`, ability readiness and estimated damage/healing, attack/cast/move/shop/recall/submit/ward/consumable methods, map terrain, group metadata/state, visible units and locks, bitboards, native reachability and `DistanceField`, draft/team memory, round/score, and fuel remaining. Movement can return `False` for a newly revealed hidden obstruction without spending the action; known-invalid actions can raise. Only act on visible dynamic unit data and documented legal masks/preconditions.
- A significant evidence conflict remains: the published Python API doc says `game_map.camp_groups()` is empty during draft, while the checked-in `sdk/python/cambc/game_map.py` docstring says groups are also available during draft. Treat draft camp metadata visibility as unresolved and probe it before relying on map-specific camp assignments in draft. The separate `vision.camp_groups()` is expressly vision-limited.

## B. Strategic findings

Rankings are design priors, not observed win rates. “Opponent resistance” estimates how well a strategy retains value when opponents adapt; no competition population assumptions have been measured.

| Rank | Strategy | Effectiveness | Reliability | Cost | Counter resistance | Map dependence | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | Finish the camp → capture → bank loop; choose targets by expected secured gems per full cycle | Very high | High once implemented | Medium | High | Medium | Core. Capture correctness and conversion beat raw damage/kill chasing. |
| 2 | Coordinate distinct camp assignments; evaluate travel, clear turns, capture time, bank detour and likely risk | Very high | Medium-high | Medium | High | High | Core, with local fallback if shared memory is stale or contested. Avoid allied reward splitting and duplicate walks. |
| 3 | Tavi field shard purchases when the marginal upgrade repays itself | High | High | Low | High | Low | Early economic engine; choose Strength/Focus by real attack/cast breakpoints and role, not a fixed stat. |
| 4 | Survival-aware tribute timing and carrier protection; route to safest reachable altar, account for channel finish turn | Very high | Medium | Medium | Medium-high | Medium | Core; bags are both score potential and a kill bounty. A fixed “bank immediately” or fixed hoard threshold is inferior. |
| 5 | Varg focused on profitable splash geometry; use shield/reset when the cast's marginal value justifies it | High when clustered | Medium-high | Low-medium | Medium | High | Draft/build only when map and measured camp geometry support it. Compare total clear-and-bank throughput. |
| 6 | Deny channels/captures with locks, contests, or attacks on rich carriers when value exceeds lost farming tempo | High swing potential | Medium-low | Medium | Medium-low | High | Reactive, selective objective denial; maintain regular farming and an alternate scoring plan. |
| 7 | Composition and build adapt to team size/map/opponents; exploit two-body Cassi & Issac if expected joint-loss cost is tolerable | Potentially high | Medium | Medium | Medium | Medium | Test; extra actions/coverage could dominate a nominally safe third solo pick, but linked death amplifies risk. |
| 8 | Vesper/Vendetta/Stellar/Ryth/Willow/Ren/Prism specialisation | Situational | Medium | Medium | Variable | High | Keep as matchup/map substitutes; don't assume paper damage or passive synergies imply better score rate. |
| 9 | Tribute “snapshot” using a small initial bag and capture payout during channel | Potentially huge | Low/unverified | Low if applicable | Low | Very high | Experimental only: rules imply whole completion bag and capture-before-channel order, but required adjacent altar/camp geometry and channeling payout eligibility are unverified. |
| 10 | Deliberate death to camps, spawn-tile respawn camping, or hidden-AoE/dash action exploits | Low/uncertain | Low | High | Low | High | Do not use in baseline; verify only with a specific expected-value case and engine evidence. |

An additional candidate not highlighted in the research ranking is **safe ranged camp pressure**: many spellcasters have range-4 damage while camps attack only within 3 and do not chase. If a legal visible target can be hit from distance 4, spell damage may avoid retaliation. Cooldowns, one-cast-per-turn, movement restrictions and actual camp aggro/targeting may erase the advantage, so model and test it rather than making it a universal farming rule.

**Preferred foundation:** reliable capture and tribute conversion plus assignment/path economics. Add Tavi and geometry-conditioned Varg as likely strong pieces. Keep Marcella as a valuable anti-stun scorer/fighter, not a mandatory courier: stun immunity does not stop altar locks or death, and her opportunity cost may exceed its value. Draft Cassi & Issac conditionally because extra body turns and territory coverage can be disproportionate in small rosters, with safe low-bag separation to limit correlated losses.

## C. Proposed starter strategy

### Drafting

1. Read team size, own prior picks, revealed opponent picks, terrain, altar positions and spawn regions. Verify the conflicting camp-group draft access before using it. Use the 1,024-byte draft memory for a versioned compact opening plan (roster roles/map orientation/objective assignment), with a robust fallback if data is missing or malformed.
2. Select unique own champions by marginal team value, not a hardcoded champion list. Prefer an economic Tavi when not already selected; add Varg only when groups give useful splash coverage; preserve a reliable fighter/scorer and enough distinct bodies for map coverage. Consider Cassi & Issac when an extra unit materially increases reachable camps/capture coverage and the pair can be kept from joint exposure. Adapt remaining picks to enemy stun, melee cluster, ranged threat and roster size.
3. Maintain deterministic tie-breaking and legal-pick validation. Picks are revealed simultaneously each round, so respond only to actually visible prior enemy picks.

### Opening rounds

- Split champions across distinct nearby profitable camp groups using map path cost and each champion's kit. Avoid sending several allies to one reward area unless their combined damage clears it materially sooner or a contest/fight demands numbers.
- Favor quick gem groups/clusters and useful high-value grouped camps based on gem yield per expected action and survival; do not chase gold-only camps unless their upgrades/tiebreak income repay the detour. Early gold is valuable only if it shortens future clearing or lowers deaths.
- Buy only if the purchase is legal and its predicted marginal benefit repays its gold and action/position opportunity cost. Tavi can invest without returning; other champions batch purchases on natural spawn visits rather than recall solely for small purchases.

### Camp farming and capturing

- Maintain a per-turn objective state: approach, clear living group, hold capture tile, leave after payout, score/evade, or recover/reassign. Use full-group rewards/HP, state/cooldown knowledge, actual path length and champion damage/action profile to rank.
- Estimate clear turns from visible current HP and ability readiness/action constraints; model Varg splash against each valid target; model spell cooldown and whether ranged attacks constrain movement. Target group members to reduce overkill and avoid leaving a monster alive when capture is ready.
- Prefer legal attack positions that keep a ranged champion outside range-3 camp retaliation when range-4 spells permit it, but validate target visibility, cast geometry and actual incoming camp damage. For melee/close clears, include camp retaliation and shield/Jungle/Durability value in route economics.
- Once cleared, remain on an available group spawn tile through five uncontested capture phases. Avoid moving to chase a minor opportunity during progress unless expected value justifies losing/restarting it. Confirm visible group state and reward before rotating. If an enemy enters, estimate contest value; fight or hold only when projected denial exceeds farm loss.
- Keep a solo ally on the capture area at payout when possible; do not divide capture rewards among several allies without a clear benefit. After the respawn timer, treat an occupied spawn tile as delaying the whole group; use denial occupancy only if its value beats farming elsewhere.

### Shopping and upgrades

- Score item options from actual marginal combat/utility gains: expected strikes/casts to clear common camps, estimated next target clear time, champion growth, passive value, and survivability. Prefer purchases that cross a breakpoint; avoid overkill and shards that do not change the action count or safety meaningfully.
- Tavi purchases shards in the field when beneficial, prioritizing an upgrade that materially increases spell/basic-attack throughput or survival. Non-Tavi shoppers buy on spawn/death; do not automatically spend all gold before a high-value scoring decision. Keep altar locks as a low-cost emergency tool if a route/interruption role is assigned. Avoid duplicate emblem passives; count stats inside all shards/emblems correctly.
- Build toward team-wide camp-clear/capture throughput first, then shift purchases toward survival/contest near a decisive score. Use Vesper Treasure only when projected future gold earnings can repay it; its 20% bonus is separate from the documented Vesper 20% passive. Don’t use health as self-heal away from spawn.

### Combat

- Basic target priority: interrupt a genuine imminent opponent win/channel if action order allows; then threaten a visible enemy carrying a large, stealable bag when a kill is plausible; protect a rich allied carrier or an active capture; otherwise prioritize profitable camp damage. Do not chase a low-value kill across the map.
- Compare attacks and abilities using available damage/heal estimates, effective HP, expected counter-damage, cooldown cost and action constraints. Use stuns to prevent escape/tribute or reduce incoming focus, not just on cooldown. Use shields before expected damage; heals only on allies as supported by the kit/API. Don’t assume a cast allows a walk or an extra attack.
- Prefer safe disengagement when a rich bag is exposed and a camp route/alternate altar is better than a likely lost fight. Focus fire only where allied turns can finish the target before it escapes or banks. Account for Cassi & Issac linked death as a shared risk.

### Retreating and healing

- Estimate lethal threats from visible enemies’ positions, ranges, ready spells/stuns, allies’ turn order and camp range; unknown enemies increase uncertainty instead of being treated as absent. Ward key approach/courier routes when useful.
- Recall when expected healing/saved death risk and useful shopping repay five (or three with Home) owner-turn ends plus round-trip/tempo; stay on spawn through end of arrival turn to heal. Low HP is not by itself sufficient if recall channel is unsafe or score is imminent.
- Recall preserves bags, but channel damage/stun/death cancels it. Escape toward a safe route or use defensive abilities if recall is interruptible. Never deliberately feed a rich carrier to enemies; camp-death gem denial is last-resort only.

### Gem tributing

- Score comparison is route-aware and probability-aware: current bag, travel time to each altar, channel ticks, current health, visible threat and ready interrupt tools, altar lock/alternate altar status, and the value of the next camp. Increase urgency as opponent nears 1,000 and as own carrier risk rises.
- Use the shortest safe altar approach. Start only with legal range and unlocked altar; account for capture-before-channel-completion and next-turn-start resolution. Once channeling, avoid planning conflicting actions; monitor remaining channel and cancellation risk.
- Preserve safer scorers for high-value channels when their opportunity cost is justified. Marcella resists stun only. If all altars are locked, select a lock-clear or alternate-altar plan; value the 3 successful attacks and danger against immediate retreat/farming. An owned lock does not block friendly tributes.
- Test small-start-bag/capture-payout snapshotting in fixture matches and map survey. Enable it only if legal geometry is common enough and the engine pays the channeling capturer before completion as hypothesized.

### Enemy interference and endgame

- Record confirmed sightings (position/round/uncertainty) and visible channel/lock state only; share compactly. Predict likely camp/altar route from sightings without asserting invisible inventory/bags or vision.
- Use altar locks reactively when expected gems denied and channel cancellation probability exceed cost/diversion. Counter enemy locks by scouting, choosing alternate altars, and removing locks only when the removal route beats continuing farm. Contest completed enemy-cleared camps when no allied objective is sacrificed and reward can be secured.
- In endgame compare next secured gems, likely enemy tribute and available interrupts. Take a certain winning tribute immediately; if behind, favor high-yield and denial plays. When ahead, lower carrier risk, avoid unnecessary combat, deny opponent conversion and choose safe repeatable income. Break round-2000 ties through additional tributed gems first, then lifetime earned gold, then kills; don't confuse inventory/refunds with earned gold.

## D. Champion selection and builds

All recommendations are opening hypotheses and should be replaced by benchmark results. Rosters are in draft **selections**; Cassi & Issac produce two bodies.

| Team selections | Starting composition to benchmark | Alternatives and role logic |
|---|---|---|
| 3 | **Tavi + Varg + flexible third** (Marcella when stun/contest risk is high; Stellar on sparse/isolated camps; Cassi & Issac where an extra body is more valuable than a single robust champion) | Test the pair pick early: it may produce four bodies from three picks. Keep its two bags small and routes independent. Do not hardwire “Tavi/Varg/Marcella” as optimal. |
| 4 | **Tavi + Varg + Marcella + Cassi & Issac** as an action-economy baseline on safe maps | Substitute Stellar/Willow/Ren/Vesper based on isolated camps, sustain/fights, mobility, or gold return. Compare pair risk with safer champion productivity. |
| 5 | **Tavi + Varg + Marcella + Stellar + conditional fifth** | Cassi & Issac if board coverage is valuable; Willow for team sustain; Vesper for confirmed gold-rich snowball; Ren/Vendetta for adversarial combat. |

Role assignments follow the draft: (1) high-throughput farmer for dense groups (Varg), (2) flexible field investor/range-4 controller (Tavi), (3) independent mobile/utility farmer or extra-body pair, (4) scorer/anti-stun frontliner if matchup needs it. No champion is permanently reserved to courier at the cost of starting the farm loop. Carriers should emerge from who owns the bag and reaches a safe altar, not from assuming a teammate can transfer gems.

Equipment starting policies to compare:

- Varg: Strength when splash hits multiple valid camps; durability/Jungle or Focus shield investment only when it avoids deaths/retreats better than another clear breakpoint.
- Tavi: Strength shard if basic attacks save more clear actions; Focus shard if high-value range-4 damage/stun uptime repays the 8-turn cooldown; avoid remote Health as a heal. Buy while moving only when budget and API permit.
- Marcella: enough damage to farm; add defensive HP/Durability for actual contest or channel duty. Stun immunity has value only against stun-bearing opposition.
- Stellar/Cassi: Focus growth has strong nominal spell damage, but spells exclude walking and cooldowns cap cadence; buy only after action-economy comparison.
- Vesper: compare early Treasure against faster damage/survival; do not treat nominal 750g break-even as a universal choice.
- Vendetta: farm last-hit sequences only when reliable; one successful cast per turn remains the cap.
- Ryth: Health shard grants HP and passive +1 Strength per +100 bonus HP in addition to the chosen shard's own growth; compare against direct strength.
- Willow: support only if heals prevent enough downtime/deaths; heal is an ally-targeted action, not self-healing per published kit.
- Prism: do not deliberately hoard for Focus until carried-gem risk demonstrates positive value.

## E. Decision-making architecture

### Per-turn hierarchy

1. Parse state and validate draft/dead/channel modes. Honor locked-in channels and action availability. Bound optional computation by fuel.
2. Handle immediate match win/loss opportunities and high-confidence threats; avoid a single false alarm overruling economy.
3. Evaluate carrier survival, tribute/lock/stun interruption and capture that would pay this phase.
4. Preserve or contest a nearly complete valuable capture; defend/escape if expected lost resources exceed interruption value.
5. Evaluate profitable combat and camp clear actions, including ability cooldown/action legality.
6. Choose/reassign objective and take legal movement; buy, ward, or adjust priority when it has expected value.
7. Fall back safely on invalid/unreachable goals, hidden obstructions, missing memory, malformed draft bytes, and no visible targets.

### Modules and algorithm

- `state`: read authoritative self, visible units/groups/locks, scores, round, active channels, abilities, item inventory; distinguish unknown from absent.
- `draft`: calculate team role marginal values from own/revealed enemy picks and map geometry; encode versioned deterministic assignment in draft memory. Draft camp visibility remains feature-gated until verified.
- `objectives`: rank camp groups, capture hold, bank, support/defence and denial using expected team secured gems and estimated full-cycle time. Recompute when target becomes contested, respawning, unreachable or no longer profitable.
- `navigation`: cache terrain masks/static map distances; use SDK `DistanceField` / bitboard reachability for legal shortest paths to attack tiles, empty capture tiles, safe altars and retreats. Penalize visible enemy/camp threat and known congestion; do not assume teammate vision. Attempt only API-valid steps and retry on `False` hidden-obstruction result.
- `combat`: choose legal target/ability with expected effective damage (including camp AoE), kill chance, threat reduction, camp retaliation, cooldown/action costs and bag value. Prioritize verified effects and explicit champion-specific rules.
- `economy`: compare purchase marginal actions saved, earned-gold snowball, and survival against cost; separate own team’s resource value from tiebreak gold.
- `coordination`: define stable champion identity from runtime-visible roster/draft order as allowed by API; assign distinct goals deterministically. Use 8 bytes for protocol version, primary objective/owner and freshness/alert state, with conservative fallback. Avoid multiwriter counter races; bots run independently and there is no documented atomic transaction. Use draft memory for static plan, not live position updates.
- `instrumentation`: debug overlay marks objective, route, threat and reason codes; keep output low and deterministic. Record decisions in replays for diagnosis.

Pathfinding must not route onto impassable walls/holes/altars/enemy spawn or visible occupied cells; target attack positions, not camp-occupied tiles where appropriate. Unknown bush blockers are a recoverable failed move, not proof of enemy identity. Revalidate navigation after each action/state change.

## F. Anti-counter strategy

| Opponent response | Planned response |
|---|---|
| Mirrors our high-efficiency camp circuit | Assign separate routes, compare race timing, steal only completed/unheld captures, and rotate to better marginal yield rather than contesting every camp. |
| Contests spawn tiles / captures | Decide whether to fight, retake after withdrawal, or abandon based on remaining capture time/reward; do not split a group between multiple unproductive defenders. |
| Uses Varg or clustered AoE | Spread bodies and select approach tiles; focus Varg while shield is down only if kill odds and bag value beat our own objectives. |
| Hunts Tavi/fragile high-bag carrier | Bank earlier as threat probability rises, use wards/routes/escorts, buy defenses when they prevent deaths; keep Cassi & Issac bags controlled. |
| Stun-heavy draft | Select Marcella/defensive tools if their opportunity cost is acceptable; channel behind vision/control or use alternate altar. Marcella still needs protection from locks and lethal damage. |
| Locks the preferred altar | Detect visible lock and route to another altar; clear only when strategically better than detour; keep a lock for a pivotal interrupt when value supports it. |
| Greedy large-bag hoarder | Pursue only when target visibility, reachable damage, likely kill and carried value justify lost farm; otherwise outscore and defend bank routes. |
| Aggressive dive / spawn pressure | Kite toward teammates/spawn/warded routes; trade if it secures bag or objective; don't chase into fog or give free enemy kill gold/gems. |
| Focuses Cassi or Issac | Keep them on independent, low-risk objectives and limit joint exposure/combined lost bag value; if linked death proves too costly, stop drafting the pair. |
| Denies camp respawns by occupancy | Re-route and compare alternate groups; contest the occupant only when its removal recovers enough yield. Avoid mirror denial trapping our own farmer. |
| Adapts to fixed assignments/builds | Deterministic assignments are per opening only; reassign from observed occupancy/threat and shift item/roster preferences from measured evidence. |

Safeguards: do not encode opponent hidden stats/bags/channels as known; use stale sightings with decay; no eternal camp camping; never leave a high-value channel/capture purely because an unconfirmed threat is possible; avoid unverified AoE/dash/channel interactions in production.

## G. Implementation architecture

No source changes are authorized yet. If this plan is approved, implementation should remain in Python and preserve the starter entry contract.

| File | Planned responsibility |
|---|---|
| `bots/starter-python/src/main.py` | Keep safe exception-to-yield loop; only adjust if instrumentation/error boundaries need it. |
| `bots/starter-python/src/bot.py` | Thin `Bot` state owner, observe → decide → execute orchestration and safety fallback. |
| `bots/starter-python/src/draft.py` | Adaptive champion choice, map analysis, encoded opening-role plan. |
| `bots/starter-python/src/randomness.py` | Keep deterministic tie-breaking or replace with a small deterministic helper if useful; no global nondeterminism assumption. |
| New `src/strategy/` modules (or a few top-level modules if Python/WASI packaging discourages packages) | Separate state snapshots, camp/objective scoring, navigation, combat, shopping, coordination, constants/protocol. Keep interfaces small and API-backed. |
| `docs/cambc/strategy/EXPERIMENTS.md` | Later record actual runner/engine version, exact match fixture, reproduction, outcome and benchmark data; correct stale tool/access claims after verification. |
| Root `plan.md` | This design and approval record; no implementation added during planning. |

Avoid new dependencies unless the installed WASI Python runtime proves them necessary. Use native SDK bitboards/distance fields and keep loops bounded by map size/fuel. Any changes to `cambc.toml`, build pipeline, dependencies or non-gameplay strategy docs require a later implementation scope decision; they are unchanged now.

## H. Implementation phases

1. **API/runner smoke and contracts:** build starter, run short matches on at least two contrasting maps, inspect replay/stats, confirm visibility/draft access, group state, action allowances, channels and actual bot-side IDs. This establishes command reproducibility and catches documentation conflicts before strategy code.
2. **Reliable economic loop:** implement explicit group selection, shortest legal approach, clear all camps, hold capture, recover from contest/death, and tribute. Use simple deterministic priorities and robust fallbacks. Compile and short-match immediately.
3. **Multi-body assignment:** allocate distinct camp/capture roles from team size and estimated route values; use draft memory/static protocol plus safe 8-byte sharing. Compare against independent nearest-camp bots and detect collisions/stalls.
4. **Combat survival and scoring:** add target ranking, threat/retreat estimates, survival-aware tribute thresholds, healing/recall value and lock responses. Stress with combat and lock-denial baselines.
5. **Economy/champion specialists:** marginal shard policy; Tavi field shopping; Varg splash selection; champion-specific ability logic. Land each as isolated ablation-tested feature.
6. **Draft adaptation/endgame:** score map geometry/opponent roster, roles and team-size options; add endgame win/deny choices and lifetime-gold tiebreak policy.
7. **Experimental mechanics:** individually reproduce snapshot tribute, dash/action stacking, lock reset, hidden AoE, attack reset, respawn denial, priority windows and any other plausible high-leverage interaction. Promote only after proof and competitive improvement.
8. **Tournament hardening:** matrix across maps/sides/rosters, reliability/fuel audit, regression and ablation runs. Remove complexity without positive measured value.

Each phase yields a runnable bot and preserves a known-good revision; do not wait for all strategic features before getting a functioning camp→capture→bank loop.

## I. Testing and benchmarking

### Correctness checks

- **Movement:** open map and obstacle/holes, unreachable objectives, target attack-tile reachability, occupied legal destination, hidden bush occupant returning `False`, and recovery without consuming/throwing away turn. Compare planner intent with `can_move`/actual replay movement.
- **Combat:** attack ranges, target visibility, per-turn attack/move rules by melee/ranged champion, ability target masks/ranges, cooldown and one-cast cap, damage/threat estimates, AoE valid targets, shield/heal/stun timing, camp retaliation.
- **Capture:** each group member must be dead; capture begins/advances/resets correctly; five phases and completion-time reward split; leave/contest/death during capture; payout/reward and respawn timers; no accidental departure during hold.
- **Tribute:** 1, 10, 11 and large gem bags; starting-turn tick and next-turn-start finish; capture reward ordering; damage versus stun/death/lock cancellation; channeling, alternate altars, exact winning score, enemy interruption turn order.
- **Economy/draft/team:** legal unique pick and changing 3–5 roster sizes; Cassi & Issac linked death; item costs/growth/emblem passives; Tavi purchase/sell/heal distinction; dead shopping; shared/draft memory roundtrip, malformed/stale memory fallback; priority applies next round.
- **Reliability:** complete-match/no-opponent-action smoke, dead champions, hidden-state API exceptions, bad or stale targets, all altars locked, no reachable camp, round limit, replay and statistics generation, and per-turn fuel headroom.

### Exploit verification

Use deterministic fixtures where runner control permits; if runner provides no seed/fixture tooling, create minimal test bots or maps only in a later approved implementation phase, and record that limitation. Prioritize `EXPERIMENTS.md` E01–E15: channel capture payout; altar lock cancellation at 1/0 ticks; capture theft/resets/reward split; respawn occupancy; Varg splash geometry/scaling; Tavi field purchases and gold accounting; dash/attack/reset action combinations; ground spell visibility/range; Marcella stun interruption; linked deaths/bags; Vendetta kill reset; Vesper gold and Ryth HP passive; priority/channel phase timing; ward visibility/hidden obstruction; kill attribution and camp-death loss. Add separate probe for draft `game_map.camp_groups()` contradiction and range-4 spell pressure against range-3 camps.

For each: reproduce exact map/rosters/positions/round/turn order, record replay and stats/log, use controls, label PASS/FAIL/INCONCLUSIVE/NOT TESTED, and distinguish rule proof from map frequency and win-rate value. No speculative effect becomes default because the API merely accepts a call.

### Match matrix and metrics

- Use local starter as an initial weak baseline and author controlled fixture opponents for random-valid, nearest-camp, gold-rush, early-bank, hoarder, lock-denial, combat-hunter, capture-thief and mirror roles. Once available, add saved prior bot versions. The map pool includes all nine checked-in maps; run both team sides, varied roster sizes (where maps support them), multiple maps, and repeated seeds if seed control exists. `run-batch` supports independent matches, but its current CLI help does not expose a seed option. Use a 10-pair pilot to catch gross failures, then at least 30 matched games per important matchup/regression comparison where budget allows; report sample counts and confidence intervals rather than treating small win-rate changes as conclusive.
- Track win rate and interval/sample count, median win round, secured gems per team-round, carried gems lost, group cycle time (arrival→clear→capture→bank), value and purchase spend, idle/failed action counts, duplicate objectives, combat damage/kills, deaths, lock cancellations, contested capture/respawn-denial turns, and fuel/exceptions.
- Compare changes on matched map/seed/side/draft sets. Use ablations for Tavi field buys, Varg AoE, assignment, banking, hunting, locks, capture contest, draft adaptation and scheduling. Promote a feature from hypothesis → reproduced → repeatable → competitive → default only with a positive primary outcome (win rate/secured gems per round) and no unacceptable reliability or matchup regression. A benefit on one map alone stays conditional.
- Regression suite has deterministic unit/fixture checks for movement, combat, capture, tribute, purchase arithmetic, memory decode and no-target fallbacks; then compact runner smoke set after each milestone and full matrix before defaulting changes.

## J. Risks, assumptions and open questions

1. **Draft camp data is contradictory:** handbook/API Markdown says map camp groups are empty in draft; checked-in SDK wrapper docstring says the groups are also available. Probe actual runtime. Draft design must work with terrain/altars/spawns and no camp metadata.
2. **Runner seeds and fixture control:** installed CLI has `run`, `run-batch`, `build`, replay/view/stats, but help exposes no seed or direct state-fixture option. Need establish whether maps/bundled runner provide reproducibility; use mirror sides and repeated maps if not.
3. **No source engine:** rules/API docs and installed runner are evidence sources; resolve discrepancies with observed tests, not assumed internals.
4. **Team memory concurrency:** each champion instance may write the same eight bytes on its turn. No transaction/atomic primitive is documented; avoid fragile multiwriter coordination and include freshness/version/fallback.
5. **Camp visibility vs metadata:** static group geometry, dynamic state, alive monster stats and unseen regions have different access restrictions. Never infer current state from static map data alone.
6. **Pathfinding and threat uncertainty:** nearest geometric target can be unreachable or unsafe; opponent bush movement is hidden; local shortest path does not capture ambush risk. Begin with robust legal shortest routes and conservative risk bands.
7. **Damage math and action economy:** nominal spell/Strength ratios ignore cooldowns, overkill, move/attack restrictions, damage modifiers, sleep/aggro and response attacks. Evaluate measured clear time, not paper DPS.
8. **Capture contest semantics and allocation:** handbook defines reset/reward timing; exact multi-tile occupancy/remainder edge cases merit replay fixtures before tactical automation.
9. **Draft composition uncertainty:** current champion rankings are speculative. Cassi & Issac add a body but correlated deaths; Marcella's stun immunity is matchup value, not universal superiority; Varg depends on target geometry; gold builds depend on game length and gold supply.
10. **Unverified exploits:** snapshot tribute depends on adjacency and channeling payout eligibility; lock at pending-zero depends on order; dash/attack-reset action stacking and hidden ground AoE are expressly unresolved. No default policy may require them.
11. **Fuel and Python reliability:** Python receives more fuel than C++/Rust per rules, but worst-case bounded group/path loops still need runtime headroom. Broad exception catching in `main.py` may conceal repeated strategy/API errors; instrumentation must expose them in replay/logging without causing turn failure loops.
12. **Deadline/opponent drift:** early beginner-beating performance cannot be assumed to generalize; keep baselines and adaptation tests and avoid tuning only against starter or a single seed/map.

## K. Final recommendation

Build a deterministic, map-aware multi-champion **camp → uncontested capture → safe tribute** system first. Assign independent profitable routes and optimize for expected secure gems per full cycle; retain a score-aware banking/escape policy because a large carried bag is a liability until deposited. Use Tavi as a likely field-investing farmer and Varg only where measured group geometry rewards splash. Draft Marcella when stun resistance has real value, while testing whether Cassi & Issac's extra body outproduces its linked-death risk. Convert gold into clear/survival breakpoints, not automatic purchases.

This should beat incomplete bots by actually collecting and banking resources, and remain resilient as opponents improve because it values full-cycle economics, adaptation, redundancy, legal information and selective denial instead of relying on one trick. The largest trade-off is implementation/benchmark complexity: threat and shared objective estimates can cost fuel and produce false decisions. Keep the first version simple and reliable, make risk thresholds conservative, and promote specialist tactics only after matched results. The tribute snapshot interaction and other surprising mechanics are experiments, not foundations.

---

**Review note:** This plan was checked against `docs/cambc/GameRules.md`, `docs/cambc/api/BotAPIPython.md`, all five files in `docs/cambc/strategy/`, the Python starter and SDK wrapper/stubs, map inventory, project config, C++ test inventory, and installed `cambc` CLI help. No source code, dependencies, configuration, docs, or tests were modified or run as part of this plan. Implementation remains gated on explicit approval.
