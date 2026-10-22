# Objective tempo and altar denial: implementation brief

This is the proposed bot strategy for the current CAMBC rules. It is written as an implementation handoff. Its goal is to beat strong ladder teams by **turning camp rewards into tributed gems reliably**, while denying opponents' long tribute channels. It cannot guarantee a win against a particular bot. The [champion analysis](analysis.md) contains the ratings and the 21 October 2026 ladder snapshot on which this draft choice is based; [GameRules.md](../cambc/GameRules.md) and the [Python API](../cambc/api/BotAPIPython.md) define the actions.

**Earlier strategy:** The routing and shared-memory proposals here have been superseded by the [leader-party strategy](leader_party/README.md), including its [state machine](leader_party/state_machine.md) and [communication contract](leader_party/communciation.md). Retain this document for its earlier draft, equipment, combat, and SDK notes; it does not define the current communication layout.

The ladder's top 20 showed Heart of Ruin among 17 teams' three most-picked champions. Marcella and Vesper Vale were common partners. The #1 team's displayed trio was Heart of Ruin, Ren, and Stellar. This specification therefore plans for both **Heart–Marcella–Vesper** mirrors and **Heart–Ren–Stellar** control teams. The ladder provides picks and ratings, not their private code or confirmed replay tactics. The counterplay below is inferred from the champion kits.

## 0. First implementation gate: update the SDK

The repository currently declares `cambc==2.1.6` in `pyproject.toml` and `sdk_version = "2.1.6"` in `cambc.toml`. Its checked-in `sdk/python/cambc/__init__.py` has no `ChampionDraft.HEART_OF_RUIN`, `ChampionType.HEART_OF_RUIN`, or `CampType.GOLEM`. `sdk/python/cambc/constants.py` still says Prism gains 0.2 Focus per gem and Vesper gains 20% gold, while the new rules say 1.5 and 33%. The current starter draft uses `range(11)`, which excludes draft ID 11 even if the rest of the SDK is fixed. **A Heart draft cannot be implemented safely against this local SDK as it stands.**

Luna must do these steps before bot logic:

1. Use the event's official current SDK and CLI installation instructions; update both dependency declarations and checked-in SDK files consistently. Do not guess an SDK version or hand-edit an enum while leaving its engine binding old.
2. Confirm at runtime that `cambc.ChampionDraft.HEART_OF_RUIN`, `cambc.ChampionType.HEART_OF_RUIN`, and `cambc.CampType.GOLEM` exist. The current API document lists draft ID 11 and champion type ID 12, but code must use the named enum members.
3. Read the current runtime's rules/constants and champion designs. In particular confirm the 10-turn ward recharge, five-hit altar locks, 100-gold kill reward, Heart dash properties, Vesper bonus, and Marcella tribute bonus. If the installed runtime disagrees with the current rules, stop and report the exact mismatch before tuning strategy.
4. Replace the starter's random `range(11)` draft with the named-pick policy below. Do not treat stale `passive_abilities` constants in the old source tree as authoritative.

The rest of this brief assumes that gate is passed. The workspace is Python-only (`cambc.toml`), so implement in `bots/starter-python/src/draft.py`, `bot.py`, and small helper modules beside them. Keep `main.py` as the draft/gameplay dispatcher.

## 1. Win condition and governing policy

The first team to tribute 1,000 gems wins. Carried gems score nothing, can be stolen on death, and are locked in a cancellable channel at an altar. At the round limit, tributed gems decide first, lifetime gold second, and kills third. Thus the priority order is:

1. **Complete a safe tribute that reaches 1,000.** Do not detour for a kill or another camp.
2. **Prevent an enemy tribute that reaches 1,000**, by placing an altar lock, killing the courier, or stunning a non-immune courier. A lock works against stun-immune Marcella; stun does not.
3. **Preserve and bank our carried gems.** Avoid fights whose expected reward is smaller than the bag at risk.
4. **Capture high-value camps and buy enough power to keep doing so.** Gold is a means to improve gem throughput and survival.
5. **Contest enemy carries or captures only when the objective value exceeds lost farming time and death risk.** A champion death removes its actions for 60 owner turns.

Do not write a bot that attacks the first visible enemy every turn or returns to an altar for every single gem. Both lose too much objective tempo.

## 2. Draft policy and jobs

### Picks

The opponent can pick the same champion, so an enemy pick is **not** a denial. A team cannot duplicate its own pick. Draft in this exact order, taking the first pick not already in `draft.current_draft(Team.ALLY)`:

1. **Heart of Ruin**: central contest, area stun, emergency peel, and camp assistance.
2. **Marcella**: primary gem carrier and tributer; her stun immunity directly counters Heart/Ren control and each gem she tributes earns 2 gold.
3. **Vesper Vale**: gold and ordinary camp economy, ranged damage, mobile pressure.
4. **Vendetta**, if the map drafts a fourth choice: sustained basic damage and camp last hits.
5. **Ryth**, if it drafts a fifth choice: second area stun and durable defender. Substitute **Varg** when at least 35% of `game_map.camp_groups()` contain two or more camps; Varg's splash is more valuable on densely grouped camps. This 35% threshold is an initial heuristic, not a known optimum.

If a map has only three picks, stop after the first three. Use `cambc.draft.team_size()` to determine this; do not hardcode team size. If the SDK gate fails, report the blocker rather than silently selecting an unrelated three-pick team.

### Jobs, not rigid lane assignments

| Champion | Default job | Capture preference | Fight preference |
| --- | --- | --- | --- |
| Marcella | Secure gem captures, route to a safe altar, and tribute | Gem cluster, Elk/Golem or other high-gem group | Defend her bag; attack a nearby courier or threat only if it does not endanger the deposit |
| Vesper Vale | Clear nearby gold-bearing camps and fund fast item growth | Gold cluster, Wolf, and safe gold-rich groups | Kite or finish fragile enemy ranged units; protect Marcella on the way to altar |
| Heart of Ruin | Farm contested central groups, scout approaches, and interrupt enemy channels | Contested groups when he can hold the region | Dash-stun multiple enemies/camps or peel an enemy off Marcella |
| Vendetta, when drafted | Clear large-health camps and take last hits | A separate profitable route | Finish weakened targets so her abilities refresh |
| Ryth/Varg, when drafted | Help on grouped camps and guard a capture or altar | Shared only if speed or safety warrants reward splitting | Ryth stuns a cluster; Varg splashes nearby targets and shields |

These are preferences. If Marcella is across the map and a gem cluster is next to Vesper, Vesper takes it. Losing five to ten rounds waiting for ideal ownership is worse than giving up a passive bonus. Gold is personal, and capture rewards split among allied occupants of a camp region. Never assume Vesper's extra gold is shared with Marcella.

## 3. Round phases and default routes

### Opening, while all gem bags are small

- Precompute camp groups, their gem/gold values, spawn tiles, nearby legal attack tiles, and nearest reachable altar from the **fully visible draft map**. Reuse that static data in each champion bot. The 1,024-byte draft memory can carry a compact route plan; it need not hold the whole map, since the static map API remains available.
- Send Marcella toward the best **safe gem-producing group** on our half, Vesper toward a **different gold-producing group**, and Heart toward a **central group or approach that the opponent can contest**. `Our half` means a camp with path distance from our spawn no greater than from the enemy spawn; compute this from terrain, not from x-coordinate alone.
- Make the opening assignment deterministic in every bot instance: score all groups from our spawn, give Marcella the highest-scoring group with at least seven gems, give Vesper the highest-scoring group with at least 20 gold **excluding Marcella's group**, and give Heart the highest-scoring remaining group nearest the map's contested middle. If no group meets a role condition, take the highest-scoring unassigned group. Store these three group indices in draft memory or recompute exactly the same sorted order; break equal scores by stable group index. Later turns may reassign when a group is captured, respawning, unsafe, or a much better group becomes available.
- Attack neutral clusters early when they are close: gem and gold clusters have only 120 Health and do not attack. However, the five-round capture wait and walk to altar still count. A 7-gem cluster far from an altar is not automatically better than a 15-gem Elk near one.
- Place a ward on a legal tile two steps toward a contested camp/altar when the charge is ready and doing so does not interfere with a higher-priority action. Each champion sees only its own vision and ward, so a ward helps its owner first; share compact sightings through team memory.

### Middle game

- Keep two productive routes active rather than sending all champions to one camp. Marcella handles a gem-rich route, Vesper a gold/low-risk route, and Heart contests whichever central resource or altar creates the largest swing.
- On a high-health Golem or Monolith, combine damage **only if the travel saved exceeds the lost rewards from splitting and travel**. Have the desired carrier alone on a camp spawn tile at the capture completion when safe. The group is not captured merely by killing the monsters.
- Buy before long travel. Vesper and Marcella need to return to spawn to buy; do not recall for a single 30-gold shard if a nearby capture is available. Tavi is not in the default draft.
- Increase altar defense once a bag reaches the banking threshold in section 5. A defender's job is to remove threats or place a lock; it should not stand on Marcella's capture region and split rewards without purpose.

### End game and score race

- Read `cambc.global_submitted_gems(Team.ALLY)` and `(...Team.ENEMY)` every turn. If our score plus any one carried bag reaches 1,000, bank that bag immediately at the safest accessible altar and escort it. Stop starting slow optional camps.
- If the enemy is one plausible capture or bag away from 1,000, give a lock carrier or stunner an enemy-altar interception job. A new enemy lock cancels a tribute channel and takes five basic attacks to remove.
- If neither team reaches 1,000 near the round limit, prefer **tributed** gems over more unbanked camps. Only use lifetime gold as a deliberate tie-break target when both teams' reachable gem scores truly appear equal.

## 4. Target selection: an explicit first-pass formula

Implement one group scorer and recompute it when the target disappears, a bag needs banking, or every four owner turns. Keep the current target unless a new candidate scores at least **25% higher**; this prevents oscillation.

For each camp group `g` with nonzero reward:

1. Read `g.gem_value()`, `g.gold_value()`, `g.spawn_tiles()`, and `g.max_respawn_timer()`. If its spawn region is visible, use `g.state()` to reject a respawning group. The SDK says `state()` raises when out of vision; never call it blindly on hidden groups.
2. Estimate `travel` as the shortest legal walking path to **a free attack tile** for a live camp, or to a group spawn tile if the reward is already available. Do not path onto a living camp or an altar. Use `DistanceField` or `move_towards` with an actual free tile, not straight-line distance through walls.
3. Estimate `clear_turns = ceil(remaining_group_health / max(1, expected_damage_per_turn))`. Use visible current Health when known; otherwise use design Health. Start with the acting champion's Strength plus ready-spell damage divided by eight; include another champion only when already nearby and assigned to the same group. Apply known splash only when more than one camp can be hit. Avoid spending a full path search per camp on every turn: cache static distances or consider the best few groups.
4. Estimate `capture_cost = 5`. If the resulting bag would contain gems, estimate `bank_cost = 0.5 * path_distance_from_group_to_nearest_usable_altar + max(1, ceil((current_bag + group_gems)/10))`; otherwise set `bank_cost = 0`. The half-distance discounts future travel when several camps fit one bag; use full distance when this capture would force an immediate bank.
5. Define `value = group_gems + gold_weight * group_gold`. Start `gold_weight = 0.05` before round 800, `0.025` after round 800, and `0.01` after round 1,400. For Vesper only, multiply his gold term by 1.33. For Marcella only, add `0.05 * group_gems` to reflect later tribute gold. The numerical weights are tuning seeds, not proven economic exchange rates.
6. Define `risk_multiplier = 1.0` on a safe home-side camp; `0.7` if an enemy is seen within six tiles of a spawn tile; `0.45` if the enemy is closer to the camp than we are or controls the approach. Use the lowest applicable multiplier. If a group is contested and we are carrying at least 20 gems, reject it unless it is required to prevent an immediate enemy win.
7. Compute `score = risk_multiplier * value / max(1, travel + clear_turns + capture_cost + bank_cost)`. Select the highest score among groups appropriate to the champion's role. If the role-preferred group is much worse than another (`score < 0.7 * best_any_group_score`), take the better group.

Do not overfit the constants before the rest of the state machine works. The important properties are path-aware travel, the five-round capture cost, bag safety, and bank travel. Add role diversity through deterministic preferences and by rejecting a group where an ally is already visibly committed unless cooperation will materially reduce clear time.

For a first threat estimate, sum each **visible** enemy's current Strength if it can reach basic-attack range after one ordinary step, plus that enemy's largest ready damaging ability if its range can reach us after one step; add attacks from visible awake camps whose current attack range covers our tile. Multiply by 1.2 for uncertainty. This deliberately overestimates some action combinations; use it only for retreat/tribute safety, not as a damage prediction for a kill. If an enemy's ability cooldown or reach cannot be read, assume its most threatening known spell is ready. Recompute after moving. A recent shared enemy sighting is a warning, not enough to calculate exact damage.

**Monolith exception:** It has 20,000 Health and a 200-gem reward. Do not select it merely because its gem count makes `value` large. Require at least two available attackers, a projected clear plus capture plus safe-bank time under **250 rounds**, and an altar that can support a **20-tick** tribute with a defender or lock. If these conditions fail, score smaller camps instead. Recompute if the enemy is already damaging the Monolith; a partially cleared objective may become worth contesting.

## 5. Bank policy: when, where, and how

### When to stop farming and bank

Recompute after each capture and whenever a threat appears. Bank if **any** condition is true:

- Our submitted score plus this bag is at least 1,000.
- Bag is at least **20 gems**. A Golem's 36 or Monolith's 200 therefore causes an immediate bank plan.
- Bag is at least **10 gems** and a usable altar is within **10 legal walking steps**.
- Bag is at least **1 gem** and either current Health is under **45%** or a visible enemy capable of reaching us soon is within **six tiles**.
- Bag is at least **1 gem** and either it is after round **1,500** with at least **7 gems**, or fewer than 100 rounds remain.

If none is true, take another nearby safe camp when its projected clear-and-capture time is less than the round trip to an altar. Do not stack a large bag merely to make Prism-style damage; this draft has no Prism and carried gems are a liability.

### Pick an altar

For each altar, find legal approach tiles at Chebyshev distance one. Exclude an altar with a visible **enemy** lock unless clearing it is cheaper than walking to another altar. An allied lock permits our tribute. Rank remaining altars by:

`path_steps + 4 * visible_enemy_count_within_6 + 8 * enemy_can_place_lock_within_2 + 3 * predicted_channel_ticks`.

Use current visibility plus recent shared sightings. For Marcella, reduce the stun-threat penalty but **not** the enemy-lock or lethal-damage penalty. A safe altar two steps farther away is better than one that will waste a four-turn channel. When carrying 200 Monolith gems, seek the safest altar and coordinate at least one defender; its base tribute timer is 20 owner turn ends.

At Chebyshev distance one, call `me.submit_gems(altar)` only when the altar is not blocked by a known enemy lock and the courier is unlikely to die before completion. Channel length is `max(1, ceil(starting_bag/10))` owner turn ends, including the starting turn, with completion at the following owner turn start. Damage does not interrupt; stun, death, and a new enemy lock do. Marcella ignores stuns, but must still survive and avoid a lock.

If an enemy lock blocks the best altar, compare **five basic attacks** (less if teammates can help, and an attack reset may supply an extra basic attack) against the extra travel to a clear altar. If walking is faster, switch altars. If clearing is faster, attack the `AltarLock` object explicitly when visible and in range. Do not spam `submit_gems` on a known enemy lock as though the channel has started.

### Protect the channel

- A defender positions to see paths into lock-placement distance two and spell range four. Put a ward near the approach, not on a spot that reveals no new path.
- If a visible enemy starts a tribute that would win, the defender buys or uses an altar lock if in range and carrying one. Against enemy Marcella, prefer the lock or a kill; she is stun-immune.
- A courier already channeling normally does **nothing** until completion. Cancel only when a visible enemy can kill it before completion and an escape square is available, or when the altar becomes unusable. Blind cancellation throws away progress.
- After completion, re-evaluate score and route. The bag may include gems added by a capture before completion.

## 6. Combat policy against the current top cores

### General target order

Only start a fight if it protects or steals a meaningful gem bag, prevents a tribute/capture, gives a likely kill, or clears the path to a chosen camp. Apply this target order:

1. Enemy champion currently tributing and about to win, unless an altar lock is a safer interruption.
2. Visible enemy carrier with **at least 20 gems** that we can kill or force away without sacrificing a larger allied bag.
3. Enemy about to kill Marcella or remove our only capture occupant.
4. A finishable target that yields 100 gold and, if it carries gems, its bag.
5. Enemy Stellar, then other fragile ranged damage dealers, when they can be reached safely.

Do not make Heart stronger and then leave him alive: his damage rises as Health falls. Against an enemy Heart, either keep distance/route around him or commit enough combined damage and control to kill him. Track visible shield before choosing a burst target. Stuns can stop a normal champion's tribute, recall, or teleport and limit its actions; Marcella's stun immunity is a special case.

### Against Heart + Ren + Stellar

- **Marcella is the preferred courier.** Heart's area stun and Ren's targeted stun should not interrupt her, though damage, death, and locks remain threats. Invest in durability before she carries a large bag.
- **Target Stellar when the objective fight permits.** She has 650 base Health and both damaging spells exclude walking. Vesper can pressure her from range; Heart can dash-stun a clustered Stellar/Ren pair. Do not chase her across the map while a safe gem capture is open.
- **Keep Vesper outside Heart's dash landing radius** when possible; do not clump all three champions next to Marcella. A grouped team is vulnerable to Heart's area stun and Stellar's area damage.
- **Use locks proactively near their courier's altar.** Ren and Stellar can interrupt our ordinary champion's channels, but Marcella forces the opponent to kill or lock her instead.

### Against Heart + Marcella + Vesper

- Assume the opponent may send Marcella to tribute. Save an altar lock for a visible Marcella channel; stun alone will fail. If no lock is available, intercept before she reaches the altar or focus enough damage to kill her.
- Do not fight their Heart in a tight group unless our Heart dash can hit multiple targets and our follow-up is ready. Split the farming routes so one skirmish cannot halt all income.
- Pressure Vesper's gold-bearing captures when this is low risk. Denying a capture delays both immediate gold and his growth, but do not trade a guaranteed gem deposit for a speculative denial.
- In a mirror, the main edge is **better route choice, deliberate capture ownership, earlier safe deposits, and a held lock**. Champion selection by itself does not supply an advantage.

### Ability rules for our core

- **Heart:** Use dash if its landing hits two valuable targets, interrupts a channel, secures a kill, or escapes a lethal threat. Otherwise reserve it for mobility. Use shield when predicted incoming damage exceeds 25% of current Health or when entering a dangerous capture; shields do not reduce his missing-Health damage bonus. Dash and shield require separate turns because only one ability can be cast per turn. Choose a legal landing tile and verify the actual effect area before use.
- **Marcella:** If a stun is needed *now*, cast enhanced attack reset before her next basic attack, then basic attack the target. If she has already attacked, cast the reset and attack again if legal. Use her 2× Focus spell for a visible priority target in range four when immediate damage is worth more than the enhanced stun. She cannot cast both slots in one turn.
- **Vesper:** Basic attack, then cast attack reset, then basic attack again if legal and useful. Otherwise use dash for positioning or escape. Check action flags after each action; ranged movement and basic attack normally exclude one another.
- **Vendetta:** Arrange last hits on camps or enemy champions so her abilities refresh. A refreshed cooldown does not remove the one-cast-per-turn limit. Do not abandon a profitable camp just to chase an uncertain last hit.
- **Ryth:** Pre-position, then use range-four area stun on a group or a channeling opponent. It excludes walking that turn. His attack reset is for turns when an extra basic hit is more valuable than the spell.
- **Varg:** Basic attacks on a target next to other valid enemies/camps; use attack reset for a second splash. Shield before incoming grouped-camp damage or a contested capture.

## 7. Shopping and consumables

Shards cost 30 gold; five matching shards combine into an emblem. Only the completed emblem gives its passive. These are deterministic initial builds, not an instruction to buy an unaffordable five-pack all at once. Buy available copies when `me.can_buy(item, count)` says yes. Re-evaluate after reaching each five-shard breakpoint.

| Champion | First five matching shards | Next investment | Why |
| --- | --- | --- | --- |
| Vesper | `TREASURE_SHARD_OF_STRENGTH` | `MONSTER_SHARD_OF_STRENGTH`, then Health if threatened | Strength supports every basic attack; completed Treasure adds 20% gold to his 33% bonus. Finish Treasure early enough to earn back the cost. |
| Marcella | `DURABILITY_SHARD_OF_HEALTH` | Strength for camp route or Focus for a burst-heavy matchup | More Health plus the completed 10% damage reduction helps a courier survive long channels. |
| Heart | `DURABILITY_SHARD_OF_FOCUS` | Health if dying; otherwise Strength/Focus according to hit count | Focus raises dash landing and shield; Durability improves survival while injured. |
| Vendetta | `MONSTER_SHARD_OF_STRENGTH` | Health against enemy pressure | Strength is applied on every basic and reset attack; completed Monster helps camp clearing. |
| Ryth | `DURABILITY_SHARD_OF_HEALTH` | Strength if clear speed is slow | Health improves survival and adds a small amount of Strength through his passive. |
| Varg | `MONSTER_SHARD_OF_STRENGTH` | Health/Focus for dangerous camps | Strength applies to primary and splash basic damage. |

At each spawn shop, if at least 10 gold remains after an imminent survival purchase and there is no carried altar lock, buy **one `ConsumableType.ALTAR_LOCK`**. Prioritize a lock on Heart or Vesper when an enemy altar is reachable, and on Marcella when defending the home scoring route. Its five-hit removal cost can buy more time than a small shard. Do not buy a second lock while carrying one. Defer teleport-crystal logic in the first implementation; its three-turn channel complicates safety and reservation handling.

Recall only from a safe tile. Baseline trigger: Health below **35%**, or predicted next-round incoming damage greater than current Health, or at least **150 unspent gold** with no safe nearby camp and an affordable emblem build at spawn. A five-turn recall can be interrupted by damage or stun; it preserves gems. If the courier is adjacent to a safe altar, bank first unless death is imminent. After a recall arrives at turn start, remain on spawn until that turn's end if Health is below maximum; that turn-end heals. At the initial full-Health spawn, shop and depart immediately. Dead champions still get shopping turns: buy affordable build items then.

## 8. Navigation, observation, and team coordination

### Navigation

- Use 8-direction walking and Chebyshev ranges. Build blocked tiles from walls, holes, altars, enemy spawn, visible units, and visible teleport reservations. Own spawn is traversable; enemy spawn is not.
- For a live camp, path to a **free attack tile**, not the occupied monster tile. For a reward-ready camp, path onto one of its spawn tiles and remain until reward arrives. For an altar, path to a free tile at distance one, never onto the altar.
- `me.move_towards(goal)` is a simple fallback only when `goal` is a legal free tile. Use `DistanceField` for choosing among multiple goals. Keep the goal stable until it is unavailable or a higher-level mode changes.
- A hidden enemy in a bush may make a legal-looking step, dash, or crystal return `False`. Treat this as a newly revealed blocked tile; re-read vision and try another legal route **once**. A known illegal target may raise `cambc.Error`; guard targets before acting. Never loop forever on the same blocked tile.
- Recompute vision after movement before selecting a basic attack or spell. A ranged champion that walked may have lost its ordinary attack allowance.

### Camp state and ownership

- `game_map.camp_groups()` and each group's static rewards/spawn tiles are available without vision. `group.state()` requires a visible spawn tile. When hidden, maintain a local last-seen state and estimated respawn time; do not pretend to know the live state.
- A group of cardinally connected monsters must be entirely dead before capture. At a capture phase, an uncontested occupant begins a five-round timer; later capture phases count it down. Continue occupying until the bag/gold changes or the group visibly respawns. Do **not** assume that five calls to `play_turn()` always mean capture has completed.
- More allies do not speed capture. If Marcella is the intended carrier, have helpers leave the region before completion when safe. If an enemy enters, treat the capture as contested and reset the expectation.

### Shared information

Only eight bytes of team shared memory are available and vision is personal. Start with this minimal layout; if a field is not available in the updated SDK, skip it rather than inventing it:

| Byte | Meaning |
| --- | --- |
| 0 | Last reported visible enemy x coordinate, or 255 for none |
| 1 | Last reported visible enemy y coordinate, or 255 |
| 2 | Reporting round modulo 256 |
| 3 | Enemy champion type ID, or 255 |
| 4 | The reported enemy's carried gems, capped at 255 |
| 5 | Altar x for that enemy's likely/observed tribute, or 255 |
| 6 | Altar y, or 255 |
| 7 | Flags: bit 0 enemy currently tributing; bit 1 enemy within two tiles of that altar; other bits reserved |

Report only the highest-priority enemy sighting: a channeling courier, then the carrier with most gems, then a nearby threat to our courier. Interpret an entry only if `((current_round - stored_round) & 255) <= 3`; otherwise ignore it. Use `struct` or explicit byte operations, read before writing, and write the entire eight-byte record in one call when possible. Do not rely on this small memory as a complete world model. Each champion keeps its own persistent `Bot` state for target group, last seen group status, and mode.

Set stable `set_priority` values once, because they take effect **next round**: Heart 80, Marcella 60, Vesper 40, Vendetta 30, Ryth/Varg 20. On a planned ambush, Heart then acts before Marcella/Vesper for stun setup. If an urgent lock or deposit requires another order, change priority one round ahead; never assume a same-round change works. Team turns alternate, so an opponent may act between our champions' turns.

## 9. Exact per-turn decision procedure

Implement the following state machine in this order. `mode` is one of `RECOVER`, `FARM`, `CAPTURE`, `BANK`, `DEFEND`, `RAID`, `RETREAT`. Each champion chooses its own mode from current observation; strategic job only biases choices.

```text
1. Observe self, score, visible allies/enemies/camps/locks, channel state, carried gems,
   static terrain, current target, and fresh shared sighting. Update local observations.
2. If dead: shop if allowed; keep or reset non-static target state; end turn.
3. If recalling or teleporting: do not issue ordinary actions; end turn.
4. If tributing: continue unless current Health <= the visible-threat estimate from
   section 4, the channel has not already completed, and a legal escape tile would
   lower that estimate below current Health. Only then cancel and escape. Do not
   restart the same tribute blindly.
5. At spawn: buy planned shards and one affordable altar lock; check whether spawn
   healing has happened before leaving.
6. If an enemy tribute will imminently reach 1,000 and we can interrupt it this turn:
   use a carried lock within range two; otherwise use a valid stun on a non-immune
   target; otherwise attack for a kill. Re-read state after the action.
7. If we have a winning bag, choose BANK. Otherwise choose RETREAT if death is likely;
   otherwise BANK if section 5's condition holds; otherwise CAPTURE if our chosen
   group is reward-ready; otherwise FARM; choose DEFEND/RAID only for an objective
   swing larger than our current farm value.
8. Choose the concrete destination and target for the selected mode. Place a useful
   ward or lock if legal and higher-value actions remain possible afterward.
9. Execute ability, attack, and movement in an order appropriate to the champion and
   current action flags. Re-read can_move/can_attack/can_cast and visibility after
   every successful action. Never assume an attack reset grants a second ability.
10. If movement/ability returns False due to a hidden obstruction, re-observe and
    try one different legal tile. If still blocked, end safely.
11. Persist target and recent observations; end turn.
```

Do **not** return from `play_turn()` immediately after the first basic attack or move as the starter does: melee can often move and attack in one turn, and attack resets can enable a second basic. Conversely, do not attempt actions after a channel starts or after the engine marks them unavailable. The current `main.py` catches exceptions and ends the turn, so a bad speculative action silently loses tempo; validate range, visibility, inventory, cooldown, and tile legality first.

## 10. Implementation order and evaluation

Luna should implement one complete loop at a time:

1. **SDK gate and deterministic draft.** Verify Heart exists and is actually selected. No random picks.
2. **Static map preprocessing and safe pathing.** Correct free attack/capture/altar goals, hidden obstruction recovery, and stable target selection.
3. **Camp clear → five-phase capture → bag ownership → altar tribute.** A match should show repeated actual gem-score increases before adding PvP.
4. **Per-champion abilities and equipment.** Use the action flags and one-cast limit. Add shop and recall without trapping the bot at spawn.
5. **Threat response and locks.** Give enemy couriers priority only when a capture/tribute swing is real.
6. **Shared sightings and draft-size extensions.** Three-pick core must work before four/five-pick optimizations.
7. **Match evaluation.** Compare against the starter, then across every available map, both starting sides, and a few current high-ranked public bots if challenge access is available. Record gem score, round of first tribute, score at death, capture-to-tribute conversion, idle/channel time, and win/loss. Keep a fixed map/seed set when changing thresholds. Adjust one policy at a time; prioritize changes that improve gem conversion and reduce courier deaths.

Acceptance criteria for the first serious version:

- Drafts Heart, Marcella, Vesper on every three-pick map with an updated SDK; adds the specified fourth/fifth picks when available.
- Moves to free attack tiles, kills camps, waits for **actual** capture, and repeatedly tributes gems. Does not orbit living camps or attempt to walk onto an altar.
- Keeps gems off exposed champions when a safe altar is reachable and never starts a tribute at a known enemy-locked altar.
- Uses Marcella rather than another champion as the courier when reward assignment has similar travel cost and risk.
- Uses a lock to interrupt a visible enemy Marcella tribute when possible; does not try to stun her.
- Does not make illegal calls in normal play, hang on a hidden obstruction, or spend repeated turns targeting a known respawning camp.
- Reports matchup and map results rather than claiming the draft alone beats top teams. If it loses, inspect the recorded objective metrics before altering champion ratings.

## 11. Parameters to tune after the complete bot works

Keep these values in one configuration module, with names and comments: 35% grouped-camp draft cutoff, 25% target-switch margin, 20-gem normal bank threshold, 10-gem/10-step early bank rule, 45% threatened-carrier Health threshold, 35% recall threshold, six-tile enemy warning range, round 800/1,400 gold weights, and the altar risk penalties. They are explicit starting values, **not facts in the rules**. The likely biggest practical improvements are better path distances, avoiding capture splits, timing deposits, and saving locks for real enemy channels; tune those before micro-optimizing damage formulas.
