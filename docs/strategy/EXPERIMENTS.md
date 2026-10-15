# Exploit Verification and Benchmark Plan

> Do not treat the rankings in the other documents as tournament results. As of this document's creation, **no engine tests have been run by this documentation effort**. Test the provided rule interactions with the actual `cambc2026a` runner, and keep this file updated with outcomes.

## Test protocol

Every experiment should record:

- Game build/version, Python SDK version and date.
- Map seed or full fixture, dimensions, camp group positions, altar/spawn positions.
- Team A/Team B rosters and which team acts first in the tested round.
- Relevant champions' `(x,y)`, health, Strength, Focus, items, gems, gold and cooldowns.
- Exact action sequence by **round number** and **champion turn order**, including who acts before channel completion.
- Log excerpts showing actions, channel counters, capture phases and final resource values.
- Result: **PASS**, **FAIL**, **INCONCLUSIVE** or **NOT TESTED**, plus a reproducible runner invocation where available.

No local-runner command has been invented here because the uploaded SDK reference does not specify one. Integrate tests into the repo's existing local match runner when available.

## Reproduction suite

### EXP-01 — One-tick tribute of a larger capture payout (E01)

**Hypothesis:** A tribute started with ≤10 gems completes the next owner-turn start, including newly captured camp rewards paid at round start.

**Fixture:** Find/build an altar at tile `A` and a cleared camp-group spawn tile `C` such that `Chebyshev(A,C) = 1`. Place a champion on `C` with exactly 1 carried gem. Arrange for this champion's team to capture the camp on the *next* round-start capture phase. Use a camp that pays a known positive gem total.

**Steps:**

1. Record score `S`, carried gems `1`, capture timer, current turn number.
2. On the final pre-payout turn, call `submit_gems(A)` from `C`.
3. Check that the channel has a one-tick countdown and reaches zero at its starting turn end.
4. Advance to the next round start; confirm capture payout happens before champion channel resolution.
5. At champion turn start, record `score_after - S` and whether the channel completed.

**Pass:** The score increases by `1 + capture_gems` and bag empties, while the one-tick timer was computed from 1 gem. **Fail:** The action is illegal, the champion is ineligible for payout while channeling, or the channel only deposits the starting 1 gem. **Inconclusive:** No valid adjacent geometry exists or test fixture cannot be constructed.

**Controls:** Repeat with 10, 11 and 201 starting gems; no payout; payout one round earlier/later; enemy lock or stun in the intervening phase. Separate *rule validity* from *map availability*.

### EXP-02 — Altar locks cancel channels and cost only three hits (E02)

**Fixture:** Two champions, one altar, victim carrying 200 gems with an active 20-tick tribute, attacker with a purchased lock within deployment range.

**Steps:** Place lock when victim has (a) 15 ticks left, (b) 1 tick left, (c) zero countdown but before its next turn start. Observe whether the channel is cancelled in each ordering and whether score changes.

**Pass:** Lock prevents enemy tribute, interrupts eligible ongoing channel, is removable by exactly three successful basic attacks (not necessarily three *turns*), and doesn't block the lock owner's team.

**Controls:** Try tribute against lock to verify implicit attack. Test attack-reset champion using two strikes in one turn against the lock. Repeat when the victim acts first and when the attacker acts first.

### EXP-03 — Capture theft, resets and shared payout (E03)

**Fixture:** A cleared single camp and a cleared connected multi-camp group, each with at least one accessible spawn tile.

**Tests:**

1. Team A kills all monsters, Team B alone holds the empty region for five capture phases. Does B get all rewards?
2. Team A starts capture; Team B enters a **different** spawn tile of a multi-camp group. Does progress reset?
3. After contest ends, does the timer restart from zero?
4. Two allies occupy spawn tiles when completion occurs. Do rewards split, and does the lower ID get integer remainder?
5. One ally leaves before completion; is reward allocation based on **completion-time** occupancy?

**Pass:** Behaviour matches the handbook's capture/contest/reward rules. Log timer transitions to identify off-by-one mistakes.

### EXP-04 — Respawn denied by an occupied spawn tile (E04)

**Fixture:** Capture a camp, then station a champion on one of its original spawn tiles through the expected respawn deadline.

**Pass:** The entire camp group remains absent while any of its spawn tiles is occupied, and it reappears when legal and timer conditions permit. Test occupants of either team and multiple-member groups.

### EXP-05 — Varg splash geometry and reset timing (E05)

**Fixture:** Varg adjacent to a target surrounded by 1–4 other *valid* camp targets and/or enemies at known offsets. Set target HP high enough to record nonlethal splash damage.

**Test:** One attack; record HP deltas of primary and splash targets. Use different offsets including diagonals and targets outside radius one. Buy one Strength shard and repeat. Use attack reset, repeat while shield ability is available.

**Pass:** Primary receives one basic hit, each *eligible* nearby extra target receives a Strength-equivalent splash hit, primary is not hit twice, damage scaling and action counts follow documented rules.

**Benchmark:** Compare Varg versus Stellar and Tavi on isolated, 2-target, 3-target, 4-target and noncontiguous groups at equal gold spent. Measure **rounds to complete capture and bank**, not just attacks to kill.

### EXP-06 — Tavi field shopping and item accounting (E06)

**Tests:**

- Purchase one Strength and one Focus shard away from spawn; verify stat increase and gold reduction.
- Purchase Health shard away from spawn; verify maximum HP rises but current HP does **not** heal as if on spawn.
- Try to buy an altar lock away from spawn; verify rejection/precondition.
- Sell equipment at spawn; verify full purchase-value refund and no lifetime-earned-gold inflation.
- Compare farming throughput of Tavi who buys immediately versus an otherwise identical upgrade route that returns to spawn.

**Pass:** Results match shop/location rules; no mistaken positive-gold loop exists.

### EXP-07 — Dash + movement + ranged attack + attack reset (E11)

**Fixture:** Use Vesper (ranged dash/reset), Issac or Vendetta (melee dash/reset), and Tavi (ranged reset). Place legal targets and open landing positions.

**Tests:**

1. For Vesper: dash first, then inspect `can_attack()` / `can_move()`; attempt legal basic attack and walk.
2. Move first, then attempt dash; compare against dash-first ordering.
3. Attack first, reset attack, attempt second basic attack, inspect movement allowance.
4. Repeat melee variants; ensure valid targets, cooldown and per-turn cast are respected.
5. Attack altar lock, reset, then attack lock again.

**Pass:** Record exact legal action sequences and final tile/damage, rather than assuming a general combo.

### EXP-08 — Ground spell visibility, hidden targets and extended splash (E10)

**Fixture:** Stellar, Ryth or Prism using a ground spell, an enemy in a bush outside current vision, and tiles near ability-range boundary.

**Tests:** Legal cast at visible tile with hidden adjacent enemy; at an unseen tile; with the centre at maximum cast range and victim one tile beyond centre; with ward revealing the area. Record whether hidden champion loses health or becomes stunned.

**Pass:** A matrix of **cast legal?** and **affected targets?** by visibility/range. Don't assume AoE penetrates bushes or ignores line of sight until confirmed.

### EXP-09 — Marcella tribute resistance (E07)

**Fixture:** Marcella and a normal champion (control) separately perform identical tributes while enemies can apply stun, basic damage or altar lock.

**Pass:** Stun does not interrupt Marcella's channel, while lock/death do; basic damage alone doesn't cancel either tribute. Account for her survival difference with equalised HP where practical.

### EXP-10 — Cassi & Issac linked deaths and bags (E08)

**Fixture:** Both carry known gem balances. Kill only Cassi, then on reset kill only Issac.

**Pass:** Both are eliminated in each test, both bags are lost, and the killer receives a *single* champion kill reward plus both gem bags per the documented rules. Track respawn timing and units acting individually.

### EXP-11 — Vendetta kill-reset with cast cap (E09)

**Fixture:** Vendetta can finish off several low-HP camps across turns; an attack-reset and dash are initially on cooldown.

**Pass:** Each killing blow resets both cooldowns, but only one successful spell cast is possible within a single champion turn. Verify that assists without the killing blow do not reset.

### EXP-12 — Vesper gold stacking and Ryth growth (build claims)

**Tests:**

- Vesper captures a known-gold camp with no Treasure, then with Treasure: verify documented +20% versus +40% total gold bonus and rounding.
- Ryth purchases a Health shard: verify +100 maximum HP and passive +1 Strength, separate from base +5 Strength/shard growth for Strength purchases.
- Buy duplicate emblem families: confirm stats stack and passives do **not**.

### EXP-13 — Team priority, turn starts and channel completion (E12)

**Fixture:** An allied support and courier with adjustable priorities, enemy interrupter, and a nearly completed channel. Test alternating first-team rounds.

**Pass:** `set_priority` changes **next-round** ordering only, and tribute completes at the courier's turn start after zero, allowing interruption only when opponent action actually occurs first.

### EXP-14 — Hidden obstruction and ward propagation (E14)

**Tests:** Try a movement, dash or teleport destination that is legal except for an unseen occupant. Observe `False`, reveal and preserved allowance; then try an alternate legal destination. Test known-invalid occupied tile raises error. Ensure allied wards don't automatically grant another ally vision, and new own wards replace prior ones.

### EXP-15 — Death and objective-denial edge cases (E13)

**Fixture:** Champion carrying gems, alternately killed by enemy champion, camp, and combined damage. Record killer attribution, gem transfer/destruction and 60-turn respawn timer.

**Pass:** Enemy champion kill transfers carried gems plus 50 base gold; camp kill destroys carried gems; no additional undocumented transfer is assumed. Do **not** deploy deliberate camp death as a production tactic solely because the mechanics work.

---

## Full-bot benchmark matrix

Start with at least these opponents. These bots are **test fixtures**, not assertions about real submitted competitor bots.

| Baseline | Behaviour | Main question |
|---|---|---|
| `B0-random-valid` | Select any legal action / farm opportunistically | Are we fundamentally functional? |
| `B1-nearest-camp` | Closest available camp, full capture, tribute at basic threshold | Does routing improve on simplest competence? |
| `B2-gold-rush` | Maximise early gold and damage shards | Does our economy start fast enough? |
| `B3-bank-early` | Tribute small bags frequently | Are we better at gem-risk optimisation? |
| `B4-hoarder` | Delay tributes, hold large gem bags | Does carrier interception work? |
| `B5-lock-spam` | Guard popular altar with lock whenever possible | Can our scoring recover? |
| `B6-combat-hunter` | Prioritise kills of visible champions | Do our retreat and courier safeguards work? |
| `B7-capture-thief` | Intrude on nearly cleared camps | Can we protect captures and reassign? |
| `B8-mirror` | Same code/roster with sides reversed | Detect map-side biases and timing issues |

For every change, run same seed set and both team sides if possible. Include different roster sizes (3, 4, 5), map dimensions and camp distributions. Do not optimise only for a single favourable map.

### Suggested metrics

1. **Win rate** and median win round, with counts and uncertainty intervals across seeds.
2. **Secured gems per team round** and **lost carried gems per death**.
3. **Camp yield:** time from selection to kill, to capture, to bank; gold and gem payout.
4. **Efficiency:** idle turns, failed legal actions, pathfinding re-routes, duplicate ally assignments.
5. **Combat:** useful damage, enemy gem theft, kills, preventable champion deaths.
6. **Disruption:** locks purchased/placed, enemy tribute cancellations, opponent captures reset, resource-spawn occupancy delays.
7. **Bot reliability:** uncaught exceptions, out-of-fuel events, illegal-target attempts, stuck channels.

### Ablation testing

After establishing a stable full bot, disable **one component at a time** on the same maps/seeds: Tavi field buying; Varg AoE selection; team camp assignment; risk-aware banking; enemy-carrier hunting; lock deployment; capture contest; draft adaptation; champion priority planning.

The impact is **full-bot score/win-rate difference**, not whether the isolated mechanic theoretically saves time.

### Practical promotion gate

| Stage | Evidence required |
|---|---|
| `IDEA` | Documented mechanical opportunity and explicit preconditions |
| `RULE-ALIGNED` | Source rules/API support the actions; no contradicted assumption |
| `REPRODUCED` | Exact local fixture/log shows intended interaction at least once |
| `REPEATABLE` | Repeated across relevant turn-order variants and map conditions |
| `COMPETITIVE` | Meaningful outperformance against multiple baselines under matched seeds |
| `DEFAULT` | No major regression in mirrored/opponent-counter stress tests |

Don't promote an exploit from `IDEA` to `DEFAULT` merely because an API call succeeded.

## Experiment results log (fill in during development)

| Date | ID | Engine / seed | Outcome | Notes / evidence link | Decision |
|---|---|---|---|---|---|
| 2026-10-13 | EXP-01..15 | Not run | NOT TESTED | Initial documented hypotheses | Keep provisional |

## Open questions to resolve first

1. How often do real generated maps contain camp capture tiles adjacent to an altar? This determines whether tribute snapshotting is exploitable in practice.
2. Does capture reward allocation still work when the occupant is already channeling tribute?
3. What exactly can a ranged champion do after a dash, and how many lock hits can an attack-reset supply per turn?
4. How valuable is Varg splash on actual group geometries relative to Stellar/Tavi damage and clearing speed?
5. Can an altar lock safely interrupt an enemy with countdown zero but pending start-of-turn completion? This is *turn-order sensitive*.
6. Are profitable camp groups/positions discoverable during gameplay even when outside personal vision, and what portions of their state are legitimately observable?
7. What does actual opponent behaviour look like after the first sprint? Replace speculative anti-novice heuristics with observed game logs as they become available.
