# Champion Selection, Builds and Composition

> **Working hypotheses, not proven tier rankings.** Builds must be benchmarked on the actual map. Baseline stats/abilities here come from `GameRules(1).md` → **Champion roster** and **Items & gold**.

## Champion matrix

| Champion | Base HP / STR / FOC | Growth HP / STR / FOC per shard | Main edge | Key risk | Best preliminary role |
|---|---|---|---|---|---|
| **Tavi** | 750 / 35 / 100 | 75 / 5 / 10 | Buy shards anywhere; 2.2× Focus stun | Fragile, cannot restock consumables away from base | Economic carry, isolated camps |
| **Varg** | 1,000 / 50 / 100 | 100 / 5 / 10 | Strength-based splash; attack reset; 2.5× Focus shield for 5 turns | Melee, clustering-dependent | Multi-camp farming / bruiser |
| **Marcella** | 1,200 / 45 / 50 | 100 / 5 / 10 | Stun immune; enhanced attack reset; 2× Focus ranged spell | Vulnerable to locks/lethal damage | Protected bank / frontline |
| **Stellar** | 750 / 35 / 100 | 75 / 3.5 / 10 | 2× Focus single damage; 1.4× area | Fragile; damage spells exclude walking | Isolated and grouped camp burst |
| **Cassi** | 700 / 30 / 70 | 71.25 / 3.5 / 15 | 2× Focus damage; ranged stun | Linked death with Issac | Ranged utility / safe farming |
| **Issac** | 900 / 40 / 100 | 95 / 4.75 / 10 | Attack reset; dash | Linked death with Cassi | Second-body farming / skirmish |
| **Vesper Vale** | 900 / 45 / 100 | 100 / 5 / 10 | +20% gold (40% with Treasure); reset, dash | Ranged move/attack tradeoff | Early gold snowball |
| **Vendetta** | 800 / 70 / 100 | 100 / 5 / 10 | Kills refresh both ability cooldowns | Need last hits; melee fragility | Last-hit farming / assassinations |
| **Ryth** | 1,200 / 50 / 100 | 100 / 5 / 10 | AoE stun, attack reset, STR +1% bonus HP | Stun spell excludes walking | Control tank / brawler |
| **Willow** | 700 / 45 / 105 | 50 / 3 / 5 | Ally heal up to 3× Focus; attack reset | Low growth; support consumes champion opportunity | Sustain in grouped fights |
| **Ren** | 900 / 40 / 100 | 100 / 5 / 10 | Damage/stun; dash; 0.2× Focus retaliation when damaged | Melee; retaliation may not offset focus fire | Anti-aggression bruiser |
| **Prism** | 700 / 35 / 80 | 75 / 3.5 / 10 | +0.2 Focus per carried gem; damage/stun, AoE | Incentivises risky unbanked gems | Risky scaling spellcaster |

**Note:** Cassi & Issac are **one draft choice but two acting bodies**, separate bags and bots. If either dies, both die.

## Build logic: purchase for time saved, not abstract DPS

Shards cost **30 gold** each. Five matching shards form an emblem costing **150 gold total**. The **stats stack**, including across duplicate completed emblems. Duplicate emblem-family passives **do not** stack. Families: Monster (+10% damage to camps), Power (six shards' worth of chosen stat), Durability (−10% damage taken), Treasure (+20% earned gold), Jungle (−30% incoming camp damage), Home (recall 5→3 turn ends), Bruiser (5 chosen stat +1 of each other stat, no passive).

Use a marginal-value model:

```
value(item) = expected_turns_saved_clearing_and_surviving
            + expected_future_gold/gems_from_saved_turns
            - travel_to_shop_cost
            - opponent_pressure_cost
```

This is a conceptual expression, **not** a literal SDK method or guaranteed linear payoff. Breakpoints matter: a shard that reduces a camp from eight to seven attacks may be more useful than one providing higher theoretical aggregate damage but no reduction in actions. Add movement, channel, shield and enemy threat to the model.

### Tavi — field-purchase powerhouse

- **Opening:** Prefer damage stat purchases as soon as affordable when they reduce likely camp clear time.
- **Strength:** Each Strength shard adds 5 basic attack damage. His attack reset improves its utility, but ranged champions generally cannot freely move and basic-attack in one turn.
- **Focus:** Each Focus shard adds 10 Focus; his 2.2× spell therefore gains a nominal +22 damage per cast before mitigation. Useful if 8-turn cooldown availability and tactical stunning matter.
- **Defence:** Health shards bought **in the field don't heal**, unlike Health bought on spawn. Don't confuse increased maximum with restored current health.
- **Consumables:** Purchase before leaving spawn if altar-lock tactics are planned; no general field purchases of consumables.
- **Counter to expect:** Opponents target his 750 base HP before scaling.

### Varg — strongest grouped-camp hypothesis

- **Opening:** Prioritise clustered camp groups and Strength breakpoints.
- **Strength-first:** +5 STR per shard multiplies across the number of valid units in splash range; one normal strike damages the primary and other valid targets within radius one of it.
- **Monster Strength emblem:** Five shard stats plus +10% camp damage. Particularly high value if it reduces total strikes across several monsters.
- **Defence:** A 2.5× Focus shield lasting five turns can allow sustained tanking of dangerous groups. Jungle emblem may outperform direct damage in high incoming camp DPS.
- **Attack reset:** Use when it meaningfully accelerates a kill or breaks a scoring/lock threat; it competes with shield under one successful cast per turn.
- **Counter to expect:** Unclustered camps and ranged kiting shrink splash advantage.

### Marcella — scorer and frontline

- **Opening:** Still farm her own resources; allies cannot hand over gems directly.
- **Courier build:** HP/Durability when protecting a valuable bag is the primary objective. Her stun immunity prevents ordinary stun-based tribute interruption, but **not** altar locks or death.
- **Damage options:** Her 2× Focus spell and enhanced attack reset allow pressure on ranged targets or enemies trying to contest captures.
- **Counter to expect:** Lock the target altar, exploit her melee positioning, or kill her outright during a long channel.

### Stellar — rapid spells, especially against isolated camps

- At base Focus 100, nominal slot damage is **200 single-target** and **140 per valid AoE victim**. Both slots have 8-turn-end cooldowns and share a one-cast-per-turn limit.
- One Focus shard (+10 FOC) adds +20 damage to slot 0 and +14 per target to slot 1. If both slots strike *one* target once each across a comparable cycle, that's +34 spell damage per Focus shard.
- One Strength shard (+3.5 STR) adds +28 if eight successful basic attacks land over eight turns. **These are simplified marginal damage comparisons, not proven overall build superiority**: action restrictions, downtime, target overkill and AoE geometry change the result.
- Focus and area-damage play look best when range and positioning let him cast regularly without losing movement-critical turns.

### Vesper Vale — gold engine

- Base passive yields **+20% gold earned**. One Treasure emblem contributes an **additional 20 percentage points**, yielding **+40% total**.
- A pure 150-gold emblem with +20% extra future earned gold has a **nominal 750-gold future income break-even** (`150 / 0.2`), *ignoring the stats purchased, alternative investments, rounding and opportunity costs*. Since shards also grant permanent stats, the actual decision is more nuanced.
- Choose Vesper when the opening offers reliable gold-rich camps and escape lanes. Dash can reduce reposition costs if action interaction tests validate the route.

### Cassi & Issac — extra action economy

- Run parallel camps when safe; help Cassi avoid lethal focus fire.
- Cassi has +15 Focus per shard (unusually high); her 2× spell gains nominal +30 damage per Focus shard.
- Issac uses attack reset/dash for efficient melee clears or to defend Cassi.
- Minimise **combined** carried gems in the pair until their survivability is proven. One death loses both bags.

### Vendetta — kill-based cooldown uptime

- High starting Strength 70; resets cooldowns on every **killing blow**, including camps.
- Seek efficient finishers, not damage races where an ally consistently gets the last hit.
- Cannot chain unlimited spells within one turn: the global one-cast-per-turn cap still applies.

### Situational substitutes

- **Ryth:** AoE stun and attack reset; every +100 bonus HP gives +1 passive STR. A Health shard (+100 HP) thus provides +1 passive STR alongside survivability; don't confuse this with a better raw damage purchase than a +5 STR shard.
- **Willow:** Grouped sustain and a ranged attack reset; her ally heal is **not self-healing** according to the provided kit wording. Focus gains only +5/shard, so compare healing value to raw combat productivity.
- **Ren:** Stun/dash plus retaliation when hit, even on fatal damage; test whether repeat camp hits create reliable passive value.
- **Prism:** Every 100 carried gems yield +20 Focus. This trades away safe scoring for combat power; use only with a risk-aware banking policy.

## Drafting policy

Draft choice depends on actual map terrain, available altars/spawns, enemy composition and team size. **Do not call `bc.game_map.camp_groups()` during draft** expecting camp groups; the Python API explicitly returns empty then. Draft-memory storage is 1,024 bytes and may encode terrain-derived plans; calculate camp-group routing and assignment during gameplay.

### Three picks

| Map / threat conditions | First composition to test | Why |
|---|---|---|
| Many grouped camps | **Tavi / Varg / Marcella** | Economy + splash farming + durable tribute |
| Mostly isolated 500-HP camps | **Tavi / Stellar / Marcella** | More direct burst where splash matters less |
| Gold-rich open map | **Vesper / Tavi / Marcella** | Two economic snowball tools |
| Strong expected ally sustain value | **Tavi / Marcella / Willow** | Anti-stun courier with healing protection |
| Opponents repeatedly misuse capture | **Tavi / Vendetta / Marcella** | Fast kill-follow-up + map interference |

### Four or five picks

- **4-pick aggressive:** Tavi / Varg / Marcella / Cassi & Issac (five bodies). Use only when pair survivability is acceptable.
- **4-pick safer:** Tavi / Varg / Marcella / Stellar or Willow, based on camp density and fighting.
- **5-pick aggressive:** Tavi / Varg / Marcella / Stellar / Cassi & Issac (six bodies).
- **5-pick defensive:** Tavi / Varg / Marcella / Stellar / Willow, prioritising sustain and fewer linked-death liabilities.

### Anti-draft responses

| Opponent pattern | Prefer / do |
|---|---|
| Heavy stun control | Marcella; ward/counter-lock score routes |
| Cassi & Issac | Focus whichever linked body is most vulnerable; their bags die together |
| Clumped melee team | Varg splash, Ryth area stun, Stellar AoE |
| Slow wealthy farmers | Vendetta/Ren intrusion + altar denial, while maintaining our farming rate |
| Aggressive carrier hunters | Marcella/Willow protection, shorter tribute cycles, safer camp routing |
| Long-range fragile mages | Dash-capable melee pressure and vision-aware approach |

**Important:** These are counter concepts, not matchup win-rate claims. Test all major compositions against mirrored and adversarial drafts before locking a preferred roster.
