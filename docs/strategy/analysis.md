# Champion analysis and draft guide

Based on the updated [GameRules.md](../cambc/GameRules.md), including Heart of Ruin and the current stat tables, plus the live ladder snapshot below. These are **judgment ratings**, not measured per-character win rates. A 10/10 would be a near-universal first pick; a 6/10 can still be excellent on the right map or in the right team. Scores weigh camp clearing, getting gems safely to an altar, fights over captures and tributes, survivability, mobility, and gold use. They assume sensible equipment and coordinated bots.

**Important source detail:** The rules' example says Stellar starts with 85 Focus, but her current stat table says 70. This analysis uses **70 Focus**, so her starting 2× Focus spell is 140 damage before modifiers.

## Overall rankings

| Character | Score | Main value | Main limitation |
| --- | ---: | --- | --- |
| Heart of Ruin | **9/10** | Dash landing stuns groups; shield supports low-health damage | Damage peaks when death risk is greatest |
| Vesper Vale | **9/10** | Strong ranged attacks, dash, and 33% extra gold | Wants a share of camp rewards to benefit from the gold passive |
| Vendetta | **9/10** | High basic damage and cooldown refreshes on kills | Needs last hits to realize her best turns |
| Marcella | **8/10** | Stun immunity, tribute income, and flexible control/damage | Gold passive requires her to be the one tributing gems |
| Tavi | **8/10** | Buys shards in the field; strong ranged stats and stun | Field Health purchases raise maximum health without healing |
| Ryth | **8/10** | Durable area control and Health-based Strength | Area spell prevents walking that turn; limited mobility |
| Varg | **8/10** | Splash attacks clear grouped camps; shield helps hold ground | Needs nearby targets for splash value; no dash |
| Willow | **7/10** | Large ranged ally heal and good starting basic attack | Cannot heal herself; no damaging or mobility spell |
| Prism | **7/10** | Carried gems power a damaging stun and area spell | Holding gems delays scoring and risks losing them on death |
| Cassi | **7/10** | Long-range stun and 2× Focus burst | Only 600 starting Health; Issac dies if she dies |
| Ren | **7/10** | Dash, ranged stun, and retaliation | Low starting Strength and spell damage for sustained camp clearing |
| Stellar | **7/10** | Direct and area spell damage at range four | Low Health, no control or mobility, and spells prevent walking |
| Issac | **6/10** | Dash and attack reset on an extra body from one pick | Modest basic damage; Cassi dies if he dies |

**Draft value of Cassi & Issac together: 8/10.** They are one selection but create two separately acting champions, two bags, and two sets of abilities. The linked death means one exposed body can lose both turns and both bags for 60 rounds. Their individual scores describe each body; use the pair score when comparing draft picks.

## Live ladder snapshot — 21 October 2026

I inspected the [Cambridge Battlecode ladder](https://2026a.battlecode.co.uk/game/ladder) with **All teams** selected. At that snapshot it showed 725 ranked teams. The sample below is ranks **1–20** (ratings 2,237–1,931). Each row's **Top picks** field reports only that team's three most-picked draft choices in its **last 50 completed games**. A champion absent from this table may still be a team's fourth or fifth pick.

| Draft choice | In top-three picks of top-20 teams | What the displayed counts show |
| --- | ---: | --- |
| Heart of Ruin | **17/20** | Picked in 41–50 of the last 50 games by each of those 17 teams; 15 used it in all 50. |
| Marcella | **10/20** | Frequently paired with Heart and Vesper. |
| Vesper Vale | **8/20** | A common third member of Heart–Marcella teams. |
| Ren | **8/20** | Appears with Heart in every one of those eight displayed triples. |
| Vendetta | **6/20** | Used in several distinct cores, including Heart and Cassi & Issac teams. |
| Ryth | **4/20** | Often appears beside Heart in control-heavy triples. |
| Stellar | **3/20** | Each of those teams used her in 49–50 of its last 50 games. |
| Cassi & Issac | **2/20** | Both teams used the pair in all 50 games. |
| Tavi / Varg | **1/20 each** | Each appears in one team's displayed top three, used in all 50 games. |

**Examples worth testing:** [#1 Intercontinental Fish](https://2026a.battlecode.co.uk/game/team/1890540d-1ffc-4847-adbf-d0d08772f268) lists **Heart of Ruin + Ren + Stellar**, each picked 50/50. The #4 and #5 teams both list **Heart of Ruin + Marcella + Vesper Vale**, each 50/50. The #7 team lists **Marcella + Tavi + Vesper Vale**, each 50/50, and the #8 team lists **Cassi & Issac + Marcella + Vendetta**, each 50/50. Strong teams therefore use several different cores; Heart is prevalent but not required for a high rank.

**How this changes the guide:** Heart of Ruin moves from **8 to 9/10** because it is consistently selected across most of this high-ranked sample. Ren and Stellar move from **6 to 7/10**: the #1 team's repeated Heart–Ren–Stellar choice, along with other high-ranked users, is stronger evidence of practical value than their raw damage numbers suggested. Treat the exact scores as provisional. The ladder shows selection and team rating, not a character's isolated win rate, item build, camp route, or causal contribution. I could not inspect replay behavior from this snapshot, so the following kit synergies remain hypotheses to test.

**Practical draft hypotheses from the repeated cores:** Heart's area stun can create a stationary casting turn for Stellar, while Ren adds another ranged stun and a dash to contest ground. Heart + Marcella + Vesper combines area control with tribute and capture gold bonuses, provided captures are assigned to the intended recipient. Heart + Ren + Ryth stacks separate champions' stuns for altar and capture fights. These are inferences from the kits and picks, not observed replay tactics.

## Strategic rules that change the rankings

- **Tribute, not carried gems, wins.** A champion carrying a large bag is a valuable target. Tribute takes at least one owner turn end and completes at the next turn start after its timer reaches zero. Stuns, death, and a new enemy altar lock interrupt it; damage alone does not.
- **Capture needs one uncontested occupant for five capture phases.** Extra allies do not speed it up and split the reward if present when it finishes. Clear together, then leave the intended gem carrier alone on the region when practical. This matters especially for Marcella's tribute gold, Prism's carried-gem Focus, and Vesper's gold bonus.
- **Camps reward different tools.** Gem and gold clusters have 120 Health and cannot attack; grouped camps favor area damage and Varg's splash. Golem and Monolith have far more Health and hit harder, favoring sustained attacks, shields, healing, and control.
- **One successful ability cast per champion turn.** An attack reset can enable another basic attack, but a champion cannot cast a second ability in that same turn. Vendetta's kill refresh helps on later turns or with an available ability that turn, subject to this limit.
- **Positioning costs ranged attackers damage.** Ranged champions ordinarily cannot walk and basic attack on one turn, and their damaging spells generally exclude walking. Cassi's stun and Willow's heal are exceptions that can accompany walking.
- **Use turn order deliberately.** Within a team, priority and then draft order determine who acts first. `set_priority` takes effect next round. Arrange a stun or camp softening before a finisher, and have a defender ready before a tribute channel starts.

## Character notes

### Vesper Vale — 9/10

**Good for:** Early economy, steady ranged camp damage, moving between camps, and fighting over capture regions. Her 55 starting Strength is unusually high for a ranged champion, and the 33% gold bonus speeds later purchases. A Treasure emblem adds another 20 percentage points, for 53% total.

**Use her:** Give Vesper a share of gold-bearing captures, especially early. Spend the extra gold on stats that let her keep clearing and surviving. Use the dash to cross gaps or leave a threatened position; use the attack reset when another basic hit matters more than movement. The two abilities cannot be cast in the same turn.

**Pairs well with:** **Varg**, who clears grouped camps while Vesper supplies ranged damage; **Willow**, who keeps Vesper on the map to collect more rewards; **Marcella**, who can turn a separately assigned gem capture into extra gold when she tributes. Their gold passives reward different actions, so plan who stands in the capture region.

### Vendetta — 9/10

**Good for:** Camp last hits, rapid follow-up fights, and finishing weakened champions. She starts with 70 Strength, an attack reset, a dash, and a passive that refreshes both ability cooldowns whenever she gets a kill, including a camp monster kill.

**Use her:** Track camp Health so Vendetta gets the killing blow. A kill can make her dash or reset available again for a later turn, allowing her to move between targets more often than the normal eight-turn cooldown suggests. Do not overextend for a last hit when carrying gems: death hands the bag to the killer and costs 60 rounds.

**Pairs well with:** **Stellar** or **Prism** to soften targets for Vendetta to finish; **Ryth** or **Heart of Ruin** to stun a target before she closes; **Willow** to sustain aggressive camp routes. Coordinate turn priority so the softener acts first.

### Marcella — 8/10

**Good for:** Carrying and tributing gems, resisting stun-based disruption, and punishing enemies at an altar. She is stun-immune, starts with 1,200 Health, earns 2 gold per gem she tributes, and has both a stunning enhanced attack and a range-four 2× Focus spell.

**Use her:** Make Marcella the intended recipient of high-gem captures, then route her to a defendable altar. A teammate can help kill the camp and leave its region before capture finishes so Marcella receives the gems. Her stun immunity helps preserve a tribute against stun attempts; death or an enemy altar lock can still stop it. Her enhanced attack requires a basic attack to deliver its stun.

**Pairs well with:** **Ryth** or **Heart of Ruin** for area stuns around an altar; **Willow** for healing during long runs; **Vesper Vale** for a team that builds gold through separate capture and tribute roles. Avoid accidentally splitting every gem reward across the team if Marcella is meant to score it.

### Tavi — 8/10

**Good for:** Long camp routes, flexible item builds, and ranged picks. He can buy shards anywhere, starts with 110 Focus, and has a range-four 1.4× Focus spell that stuns. His attack reset improves his basic-attack turns.

**Use him:** Put Tavi on a route where he can collect gold and convert it into shards without recalling. Buy the stat that addresses the next fight: Strength for repeated basics, Focus for the stun spell, or Health for durability. Health bought away from spawn increases maximum Health but does not restore current Health; use a safe heal or recall when needed. He still needs spawn or death to buy consumables.

**Pairs well with:** **Willow** to heal the Health that field purchases do not restore; **Varg** or **Ryth** to hold grouped camps while Tavi fires from range; **Vendetta** to capitalize on Tavi's stun and damage before a last hit.

### Ryth — 8/10

**Good for:** Holding capture ground, stopping grouped enemies, and durable melee fights. He starts with 1,200 Health and has a range-four area spell that deals 1× Focus and stuns in radius one. Bonus Health also grants Strength equal to 1% of that bonus Health.

**Use him:** Lead approaches to contested camps and interrupt tribute or recall channels with the area stun. Health shards improve both durability and basic damage, though each 100 bonus Health adds only 1 Strength through the passive; choose Strength shards if immediate attack damage is the priority. His area spell excludes walking, so get into position beforehand.

**Pairs well with:** **Stellar** or **Prism**, whose area damage can follow a grouped stun; **Willow** for repeated frontline engagements; **Marcella** to protect a gem carrier and extend a control chain.

### Varg — 8/10

**Good for:** Clearing clustered monsters and holding a capture tile. Basic attacks splash Strength damage onto other valid enemies or camps within one tile of the target, and his self-shield starts at 2.5× Focus.

**Use him:** Choose grouped camps where several monsters can be hit by each basic attack. Attack reset lets him apply another basic attack when available, multiplying the value of splash. Use the shield before taking camp fire or defending a capture. Against an isolated Monolith, his splash passive contributes nothing, so lean on other damage dealers.

**Pairs well with:** **Willow** for sustained group clearing; **Ryth** to stun clustered targets while Varg attacks them; **Vesper Vale** or **Tavi** for ranged damage against a camp Varg keeps occupied.

### Heart of Ruin — 9/10

**Good for:** Diving grouped targets, disrupting a tribute, and fighting while injured. His dash can hit and stun enemies and camps within radius one of the landing tile; its base landing damage is 1.5× Focus. His passive adds up to 50% damage based on missing Health, and his shield lasts five turns.

**Use him:** Approach a clustered fight with enough Health to survive, then use the dash landing to stun multiple targets. Once injured, shield rather than remaining unprotected merely to preserve the damage bonus: shields do not count as Health for the passive. The dash and shield are separate abilities and cannot both be cast on one turn. Do not carry a large gem bag while deliberately staying near death.

**Pairs well with:** **Ryth** for consecutive area control; **Stellar** or **Prism** to damage targets caught near the landing; **Willow** as an emergency heal when survival matters more than the missing-Health bonus. Timing Willow's heal after Heart's attack can preserve a stronger attack without sacrificing the next turn.

### Willow — 7/10

**Good for:** Keeping a valuable ally alive on a long route or through a contested capture. Her ally heal restores up to 3× Focus, or 360 Health at base Focus, at range four and is compatible with walking. She also starts with a respectable 55 Strength for ranged basic attacks.

**Use her:** Follow a frontline clearer rather than sending her to solo a dangerous camp. Move and heal when an ally needs recovery; use attack reset on turns when extra basic damage is more useful. She cannot target herself with the heal, so keep her out of the focus of enemy attacks.

**Pairs well with:** **Varg** or **Ryth** for sustained camp control; **Vendetta** to support repeated last-hit routes; **Cassi & Issac** to protect either member of a vulnerable linked pair. With **Heart of Ruin**, reserve heals for real danger because healing reduces his damage passive.

### Prism — 7/10

**Good for:** Turning a modest gem bag into stronger spells and controlling a valuable target. Prism gains 1.5 Focus per carried gem; her range-four stun deals 1.5× Focus, and her other spell damages an area.

**Use her:** Collect gems from a safe region, use the temporary Focus to win the next camp or altar fight, then tribute before the bag becomes too risky. At 10 gems she has 95 Focus before equipment, so her stun spell rises from 120 to 142.5 damage before other modifiers. Do not hold gems indefinitely for damage: carried gems score nothing and are stolen on death.

**Pairs well with:** **Marcella** or **Ryth** as an escort during risky gem runs; **Willow** to reduce death risk; **Vendetta** to finish targets Prism has stunned and damaged. Coordinate who receives a capture: gems split among allies present.

### Cassi — 7/10

**Good for:** Range-four burst and control from behind a frontline. Her 2× Focus spell deals 140 damage at base Focus, and her separate range-four stun can be cast while walking. Focus shards add 13 each, making spell investment valuable.

**Use her:** Keep distance, stun a dangerous monster or enemy during a repositioning turn, then cast damage once set. She starts with only 600 Health. Since her death also kills Issac and loses both bags, keep her out of exposed capture and altar positions when possible.

**Pairs well with:** **Issac**, whose dash and attack reset can follow her stun; **Ryth** or **Varg** as a durable frontline; **Willow** for emergency healing. Cassi and Issac are one draft pick, so the latter pairing is always available when she is picked.

### Issac — 6/10

**Good for:** Mobile melee pressure and extra map coverage from the Cassi & Issac pick. He has a dash and an attack reset, so he can reach a target or add a basic hit as the situation demands.

**Use him:** Take relatively safe side camps or assist Cassi's stunned targets. Two independent bodies can cover more ground, but avoid using Issac as a disposable scout or gem courier: his death also kills Cassi and loses both bags. His 40 starting Strength and 3 Strength growth per shard make him less efficient as the team's sole sustained damage source.

**Pairs well with:** **Cassi** for stun into melee pressure; **Willow** for sustain; **Vesper Vale** for a second mobile unit that can work another route. Keep the linked pair's combined death risk in mind when splitting them across the map.

### Ren — 7/10

**Good for:** Harassing a target at range four, dashing to contest ground, and punishing attackers. His damage-and-stun spell starts at 0.75× Focus, and retaliation starts at 0.2× Focus when he is damaged.

**Use him:** Interrupt a channel or start a control chain, then dash to contest a capture or escape. Retaliation adds value in a fight where he is already being attacked, but deliberately taking camp hits just for 20 base retaliation damage is usually a poor trade. His 35 starting Strength gives him slow isolated camp clears.

**Pairs well with:** **Vendetta**, who can finish a stunned target; **Ryth** for layered control; **Willow** to recover after Ren absorbs pressure. He is better as a mobile disruptor than as the only camp clearer.

### Stellar — 7/10

**Good for:** Range-four spell damage, especially when multiple enemies are in one radius-one area. At the current 70 base Focus, her single-target spell starts at 140 damage and her area spell at 98 damage per target before modifiers.

**Use her:** Pre-position before a camp or fight, because both spells exclude walking and her 650 starting Health leaves little room for errors. Use the area spell when it hits several valuable targets, and the 2× spell for one priority target. Focus shards add 7 each, so compare that growth with other damage options before making her the team's main scaling carry.

**Pairs well with:** **Ryth** or **Heart of Ruin** to stun groups into an area hit; **Varg** to keep grouped camps under pressure; **Willow** to offset her low Health. She benefits strongly from allies who create safe, stationary casting turns.

## Example draft cores

These are starting points for a three-pick team; maps with four or five picks can add a mobile scout, a second camp clearer, or an altar defender.

| Core | Plan |
| --- | --- |
| **Vesper Vale + Varg + Marcella** | Varg clears grouped camps, Vesper grows from gold-bearing captures, and Marcella takes selected gem captures and tributes them for extra gold. Avoid unintentionally splitting rewards meant for either passive. |
| **Vendetta + Ryth + Willow** | Ryth controls groups, Vendetta takes last hits to refresh abilities, and Willow keeps both on the map. Arrange turn priority so Ryth can set up Vendetta. |
| **Heart of Ruin + Prism + Marcella** | Heart stuns clustered defenders, Prism adds ranged control and damage, and Marcella is a sturdy tributer. Keep Prism's carried-gem gamble separate from the team's main scoring bag. |
| **Cassi & Issac + Varg + Willow** | One draft pick supplies two actors, Varg clears groups and holds ground, and Willow protects the linked pair. Do not put both Cassi and Issac in dangerous fights just because there are two bodies. |
| **Heart of Ruin + Ren + Stellar** | The current #1 team's 50/50 displayed trio. Test Heart's landing stun and Ren's targeted stun as setup for Stellar's stationary area damage; tune turn priority so the intended setup acts first. |
| **Heart of Ruin + Marcella + Vesper Vale** | A 50/50 trio for the current #4 and #5 teams. Test Heart as the contesting frontliner, Marcella as the planned tributer, and Vesper as a gold-earning ranged clearer; keep reward allocation intentional. |

## What would change these scores

Maps dominated by grouped camps raise **Varg**, **Ryth**, **Prism**, **Stellar**, and **Heart of Ruin**. Wide maps and scattered objectives favor **Vesper Vale**, **Vendetta**, **Tavi**, and dash users. Frequent altar contests favor **Marcella** and champions with reliable stuns. Actual bot pathing, focus-fire coordination, capture assignments, and shop choices can change the order more than a one-point difference in this table.
