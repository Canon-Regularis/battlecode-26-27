# Mechanics audit for a safe farming and coordinated fighting bot

Date: 15 October 2026. Scope: the checked-in official CAMBC handbook, Python API and Python SDK. This is a mechanics-backed design input, not evidence that a particular strategy reaches rank 100.

## Evidence and limits

The primary rules source is [GameRules.md](../cambc/GameRules.md); the SDK implementation is [cambc/__init__.py](../../sdk/python/cambc/__init__.py), [game_map.py](../../sdk/python/cambc/game_map.py), and [constants.py](../../sdk/python/cambc/constants.py). The [Python API export](../cambc/api/BotAPIPython.md) repeats many of those SDK contracts. No game-engine implementation was found in the checked-in SDK; Python calls into a native `_cambc` ABI. Therefore “documented” below means supported by this local official snapshot, not experimentally verified against today's ladder engine. Recommendations are explicitly marked as inferences. No bot implementation changed and no matches or tests ran for this audit.

## 1. The objective is safe conversion of time into banked gems

**Documented.** The first team to tribute 1,000 gems wins. At round 2,000, the order is tributed gems, lifetime earned gold, kills, then Team B. Carried gems do not score and transfer to the killer on death; camp deaths destroy them. Champion death also removes the unit for 60 owner turn ends and pays 50 gold to its killer. [Rules: How to win](../cambc/GameRules.md#how-to-win), [Death](../cambc/GameRules.md#when-a-champion-dies).

**Design inference.** Fight value should include bag loss, enemy bag gain, lost farming during respawn, return travel and the objective unlocked by winning. Raw damage dealt and kill count are poor main objectives. A bag worth 100 gems has both a friendly loss and an enemy gain when stolen; this is a larger score swing than simply losing 100 progress. A low-health empty unit can still be valuable because 60 rounds of production and map presence disappear when it dies.

Use a resource loop with an explicit end: select a productive reachable camp, clear, finish capture, leave its spawn region, then bank when the travel/channel/risk tradeoff warrants it. A camp destination alone is not a complete strategic task.

## 2. “Easy gems” require clearing, capturing and a safe exit

**Documented.** Cardinally connected monsters form one camp group. Every monster must die before capture can start. At a capture phase, an uncontested occupant starts a five-round capture timer; later phases reduce it. Empty or contested occupancy resets progress. Extra allies do not speed capture. Rewards split among allied occupants when capture completes. The group's respawn begins after collection, uses the longest monster cooldown, and is delayed while any spawn tile is occupied. [Rules: Camps and capture](../cambc/GameRules.md#camps--capture).

| Monster | HP | Attack | Gold | Gems | Respawn |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gem cluster | 500 | 0 | 0 | 24 | 50 |
| Gold cluster | 500 | 0 | 35 | 0 | 50 |
| Wolf | 1,350 | 20 | 90 | 22 | 40 |
| Elk | 2,400 | 60 | 160 | 36 | 60 |
| Monolith | 20,000 | 200 | 300 | 200 | 150 |

These are per-monster base values. All monsters attack at range 3, see through bushes, have vision 8 and do not chase. Damage wakes the group; two rounds without an in-range champion allow it to sleep. [Rules: Pick your target](../cambc/GameRules.md#pick-your-target), [Capture details](../cambc/GameRules.md#capture-and-monster-details).

**Design inference.** Rank camps by expected bankable gems per total round, including travel, clear time, capture delay, banking travel, channel duration, health cost and hostile arrival time. A gem cluster is attractive because it has no incoming damage and low HP, but a cluster joined to harder monsters is not a free standalone reward. Gold camps can be worthwhile early when they unlock a concrete damage or survival purchase; they should not dominate when the game is near the gem finish line. Monoliths need a deliberate group commitment and exit plan, not nearest-target selection.

One unit should normally capture while others scout, defend its exits or begin another safe clear. Do not assume splitting capture shares between two champions increases team total. Leave the region promptly after collection so repeat farming can start on schedule. A group state is observable only when at least one spawn tile is visible; `CampGroup.state()` explicitly rejects unseen groups. Maintain timestamps and uncertain predictions rather than treating an old camp record as current truth. [SDK: CampGroup.state and spawn_tiles](../../sdk/python/cambc/game_map.py).

## 3. The response window matters more than a distance threshold

**Documented.** At round start, camp respawns, spell/ward updates, captures and camp actions occur before champion turns. Teams alternate champion turns; which team starts swaps each round. Within a team, priority then draft order determines sequencing. `set_priority` applies next round; `prev_priority()` reports this round's value, and `has_completed_turn()` exposes the completed-turn flag. [Rules: Rounds and turn order](../cambc/GameRules.md#rounds--turn-order), [SDK: Champion scheduling](../../sdk/python/cambc/__init__.py).

Basic melee attacks have range 1 and can share a turn with walking. Basic ranged attacks have range 3 and ordinarily share an allowance with walking. All distances are Chebyshev. Only one successful ability cast is allowed per turn across both slots; cooldown is 8 owner turn ends. Some spells exclude walking. [Rules: Turn actions](../cambc/GameRules.md#everything-you-can-do), [Combat](../cambc/GameRules.md#combat--abilities).

**Design inference.** Evaluate damage that can arrive *before this unit next acts*, including camp damage at the next round start. Enemies that already acted in the current round are different from enemies still to act. A naive check of “one enemy within attack range” misses a second enemy stepping into range, a dash-and-hit, a range-4 spell, or two enemy actions around the round boundary. A nearby ally should count as support only if it can reach and act before the vulnerable unit dies.

For each candidate end tile, build a conservative enemy response set from movement, attack range, ready spell shapes, legal dash paths and likely focus fire. Check a short horizon as well as immediate damage: a move can be nonlethal this turn yet strand the unit without a survivable retreat next turn. Include available shields, stuns and heals, and explicitly account for which ability choice prevents another ability that turn. Do not count both Cassi damage and Cassi stun in the same turn.

An arbitrary “never fight 1v2” rule is a useful initial veto but not a sufficient fight evaluator: two nearly dead enemies can be trivial while one highly upgraded enemy can be lethal. Evaluate concentrated effective damage, HP, control, escape access, bag exposure and actual arrival times.

## 4. Cassi and Issac must be one strategic asset

**Documented.** One draft pick produces two independently controlled bodies. They have separate positions, health, bags, abilities and bot instances, but either death kills both and transfers both bags for a single kill reward. Cassi has 700 base HP, range-3 basic attacks, range-4 damage of 2× Focus that excludes walking, and a range-4 one-round stun compatible with walking. Issac has 900 base HP, a basic attack reset and a two-step dash compatible with walking. [Rules: Cassi and Issac](../cambc/GameRules.md#cassi--issac).

**Design inference.** Pair safety is determined by the weaker *projected survivor*, not summed HP. A safe Issac cannot compensate for lethal damage to Cassi. Do not let Issac dash ahead because his own local fight looks good; require a safe final position for both, continued support and a return route. Do not let Cassi remain stationary casting while Issac retreats out of support range. Their combined bags belong in the pair's risk calculation, even if the acting cat personally carries nothing.

The cats should share a mission and retreat state. A pair plan should specify a safe staging region, target, formation separation and escape direction. “Together” should mean able to protect each other soon, rather than occupying adjacent squares: adjacent clumping exposes both to Ryth/Prism/Stellar area spells or Varg splash. If either cat's location/health report is stale, disable aggressive commitment and regroup toward an agreed safe rendezvous. Never interpret an unseen partner as dead or healthy.

Cassi's walking-compatible stun is valuable for disengagement; spending it on camp throughput has an opportunity cost when enemies are near. Issac's dash should generally be reserved while the pair lacks a verified safe fight. The linked pair offers extra production for one draft slot, but its safety and communication requirements make it a separate feature with acceptance gates, not a free default upgrade.

## 5. Information is local; coordination must be designed around that

**Documented.** Each champion normally sees radius 8 through symmetric shadowcasting. Walls and bushes block sight; its current connected bush is transparent to itself. Holes do not block vision. Only the champion's own ward adds vision. Teammate vision is not shared. One free ward can be placed within 2 tiles, sees radius 6, recharges after one round, persists indefinitely and replaces the previous ward. [Rules: Vision and wards](../cambc/GameRules.md#vision--wards).

There are only 8 mutable shared bytes for the whole team, plus 1,024 draft bytes that become read-only during play. Draft has the entire terrain layout and revealed earlier picks. `bc.champions()` is documented as visible champions; hidden `health()` and `position()` queries raise errors. `gold_count()` is self-only. [Rules: Shared memory](../cambc/GameRules.md#shared-memory), [Shared draft memory](../cambc/GameRules.md#shared-draft-memory), [SDK: Champion and champions](../../sdk/python/cambc/__init__.py).

**Design inference.** Do not design a coordinator around free global live positions, ally HP and enemy cooldowns. Use deterministic draft assignments for camp sectors, default rendezvous points and roster roles; reserve the 64 mutable bits for a compact, explicitly owned protocol. Cat status and an emergency retreat/target message deserve priority over rich telemetry. Specify writer ownership, round-age tags, wraparound behavior and how stale messages decay. Exact allocation depends on map dimensions and the final roster; measure required coordinate bits before promising a layout.

Each bot maintains private recent sightings. Enemy disappearance should expand a reachable uncertainty region over time, not erase danger. Reposition wards before entering a bush corridor or committing to a channel, using `Ward.visible_tiles_from()` to choose useful coverage. A ward is personal: one scout cannot give the entire team its view without communicating a compressed warning. There is no need to reconstruct full-map world state to be useful; local facts plus a clear rendezvous convention can support disciplined small groups.

## 6. Banking is a defended operation, not a binary bag trigger

**Documented.** Tribute starts adjacent to an altar with gems. Channel length is `max(1, ceil(starting_bag / 10))` owner turn ends, including the start turn; completion occurs at the next owner turn start after zero. Completion banks the entire current bag, including intervening capture rewards. Damage does not cancel tribute; stun, death or an altar lock does. A lock costs 10 gold, can be placed within 2 tiles, permits friendly tribute and takes three basic hits to remove. Tribute attempts against an enemy lock become attacks on it. [Rules: Gems and altars](../cambc/GameRules.md#gems--altars).

**Design inference.** Banking one gem immediately can waste travel; hoarding large bags creates long immobilization and loss risk. Choose based on route, interception probability, channel exposure, current HP, win threshold and whether an escort can hold the approach. A 100-gem bag means ten countdown ticks and completion on the subsequent owner turn start, not an instant safe score at the altar. Re-evaluate whether continuing a channel survives the remaining exposure. Nonlethal damage alone is not a reason to cancel a winning safe tribute, whereas an imminent stun or lethal burst can justify cancelling and moving.

“Controlling an altar” is controlling its reachable channel tiles and hostile approach routes, not simply walking toward the altar coordinate. An escort should occupy an intercept/support position while preserving the carrier's exit. Locks can interrupt an enemy investment and cost three enemy attacks to clear, but are not automatic safety: they do not prevent enemy damage.

## 7. Recovery and purchases should buy the next useful action

**Documented.** Recall lasts five owner turn ends (three with Home), is cancelled by any damage or stun, preserves gems, and arrives at turn start. The unit must remain on spawn through that turn's end to heal fully. Dead champions can shop and respawn after 60 owner turn ends when a spawn tile is available, with full HP and reset abilities. [Rules: Death, recall and recovery](../cambc/GameRules.md#death-recall--recovery).

Shards cost 30 gold; five matching shards make an emblem. Stat bonuses stack; duplicate family passives do not. Monster gives 10% more camp damage, Jungle 30% less camp damage, Durability 10% less incoming damage, Treasure 20% more earned gold. Tavi buys shards anywhere, but field health purchases do not heal; his consumables still require spawn/death. [Rules: Items](../cambc/GameRules.md#items--gold), [Tavi](../cambc/GameRules.md#tavi).

**Design inference.** Recall while a safe five-tick window still exists, not after becoming killable. A retreat planner must first find safety; recall is not an instant escape. Stay on spawn for healing instead of immediately walking away on arrival. Choose purchases against an identified need: reaching a safer clear threshold, surviving one additional enemy burst, or improving a specific spell. Avoid repeated passive purchases sold as stacked bonuses. Tavi can avoid shopping travel but cannot solve current low health by buying health in the field.

## 8. Implementation contracts and focused mechanics checks

SDK masks are legality tools, not safety proofs. Ability range masks explicitly do not check visibility or occupancy. Ordinary movement masks account for visible occupants; a hidden blocking enemy returns false, reveals its tile and preserves the movement allowance. Known illegal targets throw. [Rules: Movement](../cambc/GameRules.md#maps--movement), [SDK: Ability.valid_tiles and Champion.move](../../sdk/python/cambc/__init__.py).

Recommended contracts:

1. Every action sequence has a predicted final tile, next-response damage estimate, escape option and rejection reason. Evaluate after each state-changing action rather than executing a stale full turn blindly.
2. Visible facts, remembered facts and inferred threats remain distinct. Do not let stale partner or enemy state silently become a fact.
3. Camp tasks finish only after confirmed reward collection; banking tasks finish only after confirmed tribute; regroup tasks require support arrival, not a nominal shared target.
4. Safe fallback exists when planning time expires: preserve survival, avoid contested travel and explicitly end the turn. Fuel exhaustion suspends execution into the next round, so continuing old planning after an involuntary yield can execute decisions from an obsolete world. [Rules: Fuel](../cambc/GameRules.md#fuel).

Before relying on exact combat simulation, verify these unresolved details against a controlled local engine scenario: stun duration across alternating team order; ranged attack-reset interaction with walking; dash-plus-walk reach; mitigation/shield order across several hits; exact availability of enemy action flags/cooldowns under visibility; cat simultaneous death/respawn/shop behavior; capture start versus countdown boundary; hidden-occupant retry; tribute cancellation and last-tick survival. These are proposed checks, not completed experiments. The SDK exposes `Ability.damage_amount(target)` including mitigation/shields, which helps single-hit estimation; summing it independently for multiple hits could wrongly subtract the same shield repeatedly. [SDK: Ability.damage_amount](../../sdk/python/cambc/__init__.py).

The strategic foundation should be safe production first, then coordinated objective pressure. These rules support that direction; they do not prove the best roster, build order, numerical safety margin or rank achievable. Those require measured games and replay diagnosis.
