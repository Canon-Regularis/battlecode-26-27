> **TEMPORARY MVP PLACEHOLDER. Use this baseline for today's MVP; replace and tune it after observing working matches. This is an implementation specification, not installed bot code.**

Historical pre-implementation strategy; superseded by the [current bot documentation](../../../README.md).

# MVP shopping

Goal: spend gold on a predictable useful build, keep one affordable altar lock, and leave spawn promptly. Use [config.md](../config.md) as the single configuration source. The state machine decides when to recall/heal; shopping does not create another recall trigger.

Sources: [item and consumable rules](../../../../../cambc/GameRules.md#items--gold), [Python SDK](../../../../../../sdk/python/cambc/__init__.py). Shards cost 30 gold, five matching shards in the baseline families below combine automatically (Greed requires 25), and consumables cost 10. Read actual costs/combine metadata from the SDK.

## When to shop

| Situation | Behaviour |
| --- | --- |
| DEATH | Run shopping every own turn. Do not ask for position/Health while dead. Purchases apply to the permanent build. |
| Alive on allied spawn | Shop once before departure/healing/defense actions; refresh Health and action state afterward. |
| Tavi alive away from spawn | Shards only, when no active channel and no urgent safety action. can_buy is authoritative. Health purchases here increase maximum Health without healing. |
| Other champion away from spawn | Return without buying. |
| Recall/tribute/teleport currently active | Preserve channel; skip shopping while alive. |
| Full-Health spawn with insufficient gold | Continue normal state logic. Do not wait for income to afford the next item. |

Use the own champion handle and SDK shopping checks. Consumables may be bought on spawn or while dead, including by Tavi; do not treat his field-shard exception as field-consumable permission.

## Fixed builds

Each entry below means **five purchased shards** of that exact item. Complete phase 1, then phase 2, then repeat the listed two batches indefinitely. Do not alternate individual shards between incomplete phases.

All names in this table are ItemType members.

| Champion | Phase 1 | Phase 2 | Repeating batches |
| --- | --- | --- | --- |
| Vesper Vale | TREASURE_SHARD_OF_STRENGTH | DURABILITY_SHARD_OF_HEALTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Marcella | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_STRENGTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Heart of Ruin | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Vendetta | MONSTER_SHARD_OF_STRENGTH | DURABILITY_SHARD_OF_HEALTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Ren | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Willow | DURABILITY_SHARD_OF_HEALTH | POWER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Ryth | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_STRENGTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Varg | MONSTER_SHARD_OF_STRENGTH | DURABILITY_SHARD_OF_HEALTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Tavi | TREASURE_SHARD_OF_STRENGTH | DURABILITY_SHARD_OF_HEALTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Prism | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Cassi | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Issac | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_STRENGTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |
| Stellar | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_FOCUS | POWER_SHARD_OF_FOCUS, then POWER_SHARD_OF_HEALTH |
| Unknown/future champion | DURABILITY_SHARD_OF_HEALTH | MONSTER_SHARD_OF_STRENGTH | POWER_SHARD_OF_STRENGTH, then POWER_SHARD_OF_HEALTH |

The first Durability emblem provides one damage-reduction passive; Monster supports camp clearing; Vesper's early Treasure improves income. Repeating Power emblems provide stats without relying on stacking another passive. These are simple starting builds, not optimized matchup choices. Cassi and Issac shop independently using their own inventories/gold.

## Correct phase bookkeeping

Automatic combination removes loose shards from the inventory. Do not use loose shard count alone to decide a phase has not been completed.

For shard item s and result emblem e = s.result():

    purchased_equivalent(s) =
        item_counts[s] + s.combine_count() * item_counts[e]

Use me.item_count(), indexed by the ItemType objects. For a Power emblem, multiply by the **combine count five**, not its six-shard stat value.

Retain a private phase index and target purchased-equivalent total. At entry to a new phase set its target to current equivalent for that item plus SHOP_BATCH_SHARDS. At match startup inventory is normally empty; persist the phase across death, recall, and state changes. If reconstructing after loss of private phase data, reconstruct the initial two phases from inventory and begin a repeating batch from the current equivalent total; do not reset ownership or sell items.

Advance a phase only when its target is actually reached. A failed/unaffordable purchase does not advance it. Different phases may buy the same Power item, so each phase needs its own cumulative target.

## Purchase order and bounded loop

Run at most SHOP_MAX_SHARDS_PER_TURN successful shard purchases:

1. Read gold and current inventory.
2. If the current phase's target is reached, advance to the next phase and calculate its target. Phase-advance logic must also be bounded by the number of batches completed this call plus one.
3. Let s be its shard. If gold < s.cost() or not me.can_buy(s, 1), stop the shard loop.
4. Call me.buy(s, 1). It returns no purchase boolean: verify gold/inventory changed or stop on an expected action error; never loop after a failed call.
5. Refresh inventory, gold, and alive Health as appropriate. Repeat until unaffordable or capped.

After the shard loop, buy one ConsumableType.ALTAR_LOCK if all are true:

- SHOP_BUY_ALTAR_LOCK is enabled.
- Current carried count is zero.
- Enough gold remains.
- me.can_buy(ConsumableType.ALTAR_LOCK) is true.

For consumables, **do not pass a count to can_buy**. The checked SDK rejects that signature. Use me.consumables()[int(ConsumableType.ALTAR_LOCK)].count(), then me.buy(ConsumableType.ALTAR_LOCK).

Use remaining gold for the lock; do not reserve money and delay every emblem. Examples: at 40 gold, buy one 30-gold shard and a 10-gold lock; at 150 gold, buy five shards and finish the emblem even if no gold remains for a lock.

No manual emblem purchase or combination is required. Do not sell items or buy teleport crystals in this baseline. No extra Health panic build is added: the configured fixed phases already include durability, and the state system handles recovery.

## Return contract and recovery

Return purchases made and whether alive Health/max-Health changed. The caller refreshes Low Health/leader eligibility after purchases, especially Tavi's field Health purchase. Buying Health at spawn heals its added amount, but the HEALING state still waits for actual full Health if needed.

If can_buy rejects an item despite enough gold, stop that shopping call and retain the phase. Do not try every other item or wait at spawn forever. Unsupported champion types must use the default build; missing enum/API support is a compatibility issue to report before running.

All costs, five-shard combination rules, and passive behaviour come from rules/metadata. Build sequences, purchase limits, and whether to buy locks are configurable MVP choices.

