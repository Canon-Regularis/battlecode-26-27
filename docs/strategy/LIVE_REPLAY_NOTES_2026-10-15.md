# Live replay observations — 15 October 2026

Read-only research for the new strategy plan. No submissions, activation changes or challenges were made during this research. The live ladder snapshot showed Intercontinental Fish #1 (1,865), Mite #2 (1,850), Univardisty of Shingtonwash #3 (1,825), Shawn #4 (1,816), procless #5 (1,800), PTN Hyperion #6 (1,786), and hello #7 (1,786). These are changing ranks, not permanent identities. [Ladder](https://2026a.battlecode.co.uk/game/ladder).

## A current top-team comparison

[Intercontinental Fish versus PTN Hyperion](https://2026a.battlecode.co.uk/game/match-groups/65aceb48-f978-4b08-a8cc-0d7af6577fa0) finished 3–2:

| Map | Fish gems | Hyperion gems | Rounds |
| --- | ---: | ---: | ---: |
| Interlock | 762 | 1,066 | 532 |
| Lanes | 1,016 | 856 | 411 |
| Elkring | 1,008 | 684 | 471 |
| Expanse | 1,006 | 900 | 383 |
| Rows | 924 | 1,056 | 385 |

### Interlock: resource access alone does not decide the game

The [replay](https://2026a.battlecode.co.uk/game/visualiser/a455f31c-c43d-4006-bc10-580153d02dd4) was inspected at rounds 50, 58 and 532, including the round-50 map screenshot.

| Moment | Fish | Hyperion |
| --- | --- | --- |
| Round 50 | 270 gold, 0 banked gems, 0 kills, 4 camps | 180 gold, 72 banked gems, 0 kills, 3 camps |
| Round 58 | First champion kill credited; 320 gold; still 0 banked | Cassi/Issac killed; 116 banked gems |
| Final round 532 | 1,720 gold, 762 gems, 2 kills, 26 camps | 1,910 gold, 1,066 gems, 4 kills, 27 camps |

The visualiser labels Fish's rounds 57–60 highlight as a three-round fight with a disable followed up and one champion eliminated. Hyperion's rounds 266–291 highlight reports three eliminated during a 14-round fight; another round-400 highlight reports a disable followed up and one eliminated. These are automatic replay annotations, not a complete reconstruction of the bots' decision rules.

Fish fielded Ren, Stellar, Cassi/Issac and Ryth; Hyperion fielded Cassi/Issac, Stellar, Varg and Ryth. Both sides had separated bodies and clusters around the central area at round 50. One screenshot cannot establish a deliberate regroup algorithm. Both cats appeared on opposite parts of that engagement; the subsequent pair death is a reminder that a strong team's pair management is not infallible.

**Interpretation:** early kills or slightly more camps do not guarantee a win. Near-equal final camp counts coexist with a 304-gem difference and different kill counts. Fight selection, bag conversion and recovery deserve separate metrics. Do not claim that Fish's opening kill caused its eventual loss or that these teams use our proposed coordination scheme.

### Expanse: a productive economy can win without a single kill

The [replay](https://2026a.battlecode.co.uk/game/visualiser/7eb82f52-9e0a-4861-9391-3b5b4e4b97d9) was inspected at its final round 383:

| Metric | Fish | Hyperion |
| --- | ---: | ---: |
| Gems banked | 1,006 | 900 |
| Gold earned | 1,170 | 540 |
| Champion kills | 0 | 0 |
| Camps captured | 28 | 24 |

Both used Cassi/Issac, Stellar and Varg. The final scoreboard showed all eight bodies at 0 deaths as well as 0 kills. Fish's Issac had two Power Strength emblems, three further Power Strength shards and one Durability Health emblem; Fish's Varg had one Power Strength emblem, two further shards and one Durability Health emblem. Hyperion's displayed builds differed, including Jungle Strength on its melee farmers and Focus purchases on Stellar. These are observed end-state inventories, not proof of which build was optimal or how purchase routes were chosen.

**Interpretation:** this game supports keeping safe economic throughput as a first-class goal. A policy that groups everyone permanently could lose without ever dying. The same roster producing different gold and camp totals also shows that copying popular picks is insufficient. The build differences motivate role-specific purchase experiments; they do not justify copying all items without controlling the rest of the strategy.

## Relationship to our losses

The previous [gold_diamond online report](../../bots/gold_diamond/ONLINE_LADDER_RESULTS.md) established 0/20 maps against ranks 34, 96, 186 and 283. The older [D1 live report](../../bots/D1/D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md) describes both combat collapse and an Expanse economic loss with no enemy kills. Today's top-team comparison independently supports that two-part diagnosis.

These observations motivate safe farming, coordinated local combat and reliable banking. They do not establish the exact algorithms used by top teams, a universal best roster, or a guaranteed rank for a new bot.
