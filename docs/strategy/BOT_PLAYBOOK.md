# Bot Playbook — From Rules to Winning Decisions

> Architecture/algorithm sketch for `cambc2026a`. This is **not executable SDK bot code**; verify exact enums, method signatures, exceptions and legal action order against `BotAPIPython(1).md` before implementation.

## North-star metric

**Expected secured team gems per round until win**, after accounting for wasted turns, deaths, locks and opponents. Raw camp damage, champion kills or lifetime gold are subordinate to securing 1,000 tributed gems; gold and kills matter as strategic resources and eventual tiebreaks.

The strongest practical early bot is one that **always finishes** the fundamental loop:

`select group → travel → clear all members → occupy a spawn tile → hold 5-round uncontested capture → collect reward → bank safely → repeat`.

Do not accidentally walk off a capture tile while a timer is advancing. Do not target only one member of a group, then expect a payout. Do not forget that the starting turn counts toward channels but completion happens at the *next owner turn start* after zero.

## 1. Recommended decision state machine

| State | Exit trigger | Important decisions |
|---|---|---|
| `DEAD_SHOP` | Respawn | Buy best affordable legal items if beneficial; dead champions still act |
| `CHANNEL` | Completion/cancellation | Take no conflicting actions; monitor remaining channel time and state |
| `EMERGENCY_DEFENCE` | Threat gone / safe | Survive when carrying gems, lock interrupt, use defensives, stun, retreat |
| `SCORE` | Gems tributed / route invalid | Select safe altar, clear locks or use alternate altar; assess channel risk |
| `CAMP_CLEAR` | All group members dead | Attack visible monsters with high-impact target/spell selection |
| `CAMP_CAPTURE` | Capture reward issued / camp reset | Occupy valid spawn tile uncontested; preserve it during capture |
| `OBJECTIVE_DENIAL` | Attack no longer profitable | Contest capture, lock enemy altar, attack rich carrier, block valuable respawn |
| `TRAVEL` | Destination reached / invalid | Legal shortest-path movement, fog handling, safety-aware routing |
| `SHOP_OR_HEAL` | Ready to farm | Tavi field buys; others consider return/recall only if expected value warrants |
| `RECOVER` | Resource/target updates | Recompute assignments; reset from stale or obstructed objectives |

Recommended **priority order**, with some actions possible before moving or attacking depending on champion class: (1) resolve death/channel restrictions; (2) prevent imminent enemy win or lethal gem loss; (3) bank an immediately winning amount; (4) secure nearly finished captures; (5) collect high-value isolated combat opportunities; (6) farm/upgrade; (7) ward or reposition. Prefer utility comparisons over unconditional emergency overrides that constantly interrupt farming.

### Pseudocode decision skeleton

```text
turn():
  observe self, allied snapshots, visible enemy/camps, map, camp-group states
  if dead:
      buy_legal_high_value_items(); end_turn
  if channeling:
      end_turn  # do not inject conflicting actions

  update_compact_team_objective_and_sightings()
  evaluate_imminent_win_threat_and_survival()
  if safe_score_or_immediate_win_available:
      clear_lock_or_start_tribute(); end_turn
  if lethal_threat_while_rich:
      escape_or_defend(); end_turn
  if high_value_enemy_tribute_can_be_interrupted:
      deploy_lock_if_legal(); end_turn_if_needed

  if active_capture:
      preserve_uncontested_tile(); use_legal_defensive_actions_if_needed
  elif group_not_yet_cleared:
      prioritize_valid_damage_or_stun(); move_legally_if_allowed
  elif lucrative_enemy_carrier_or_capture_opportunity:
      pressure_or_denial_action()
  else:
      choose_best_available_camp_or_reposition()

  buy_when_legal_and_worthwhile()
  place_ward_if_profitable_and_legal()
  end_turn
```

The ordering is illustrative. A channel can be interrupted by a lock or stun at another bot's turn, and champion priorities make exact timing important.

## 2. Camp selection: optimise the full cycle

Camp base values, before bonuses:

| Camp | HP | Gold | Gems | Respawn |
|---|---:|---:|---:|---:|
| Wolf | 1,350 | 90 | 22 | 40 |
| Elk | 2,400 | 160 | 36 | 60 |
| Gem cluster | 500 | 0 | 24 | 50 |
| Gold cluster | 500 | 35 | 0 | 50 |
| Monolith | 20,000 | 300 | 200 | 150 |

A group sums its members' rewards and uses its **longest** cooldown. Capture is five rounds, regardless of group size. Multiple allies do not accelerate capture and split rewards if simultaneously occupying the region at completion.

### Cost model

For each champion `c` and group `g`, approximate:

```
cycle_turns(c,g) = shortest_legal_travel(c, nearest_attack_tile(g))
                 + predicted_clear_turns(c,g)
                 + predicted_wait_to_capture(c,g)
                 + probable_bank_detour(c,g)
                 + expected_risk_delay(c,g)

utility(c,g) = [gem_weight * expected_gems_secured(c,g)
              + gold_weight * expected_gold(c,g)
              + deny_weight * opponent_value_denied(c,g)]
              / max(1, cycle_turns(c,g))
```

Notes:

- **Do not use camp HP alone**. Varg's splash makes grouped targets very different from isolated targets; Stellar has periodic spells; Vendetta can refresh on killing blows.
- Use **actual path cost** with walls, holes, altars, enemy spawn and known occupancy excluded; straight-line Chebyshev distance is only a heuristic.
- Use camp `state()` and spawn-tile occupancy information where exposed; don't plan to farm a group that is already waiting for respawn unless the travel and delay make sense.
- Avoid normal farming logic when the opponent is within one tribute of victory and can be stopped.
- Track whether the reward belongs to a specific capturing champion; allies cannot move gems between bags.
- A Monolith's 200 gems are attractive but its 20,000 HP can make it poor early-game value.

### Phase-aware weights

- **Early:** gold matters when the next shard creates faster clear breakpoints; still bank convenient gems.
- **Mid:** target fast gem flow, protect strong farm loops and interfere with enemy captures selectively.
- **Late:** secured gems dominate, and a single lock/kill may prevent the enemy reaching 1,000.

Define phases from **scores, actual power and tactical opportunities**, not fixed round thresholds.

## 3. Banking and carrier risk

Scoring requires a champion within Chebyshev distance 1 of an altar, with gems in its bag and a tribute channel whose owner turn-end count is `max(1, ceil(gems/10))`.

A useful heuristic estimates the probability that the carrier survives the entire **travel + channel + next-turn-start** window. Compare expected score-now with score-after-another-camp. Do not always bank at an arbitrary bag threshold.

```
score_now = P(survive_to_and_through_tribute) * carried_gems
score_later = P(survive_additional_route_and_tribute) * (carried_gems + new_gems)
              - missed_farming_and_denial_value
```

Use maximum threat range, enemy visibility, possible dash/stun, likely altar locks and own health. **Marcella** reduces stun risk but not death/lock risk. Camp payout may be included in an existing channel if the `E01` location/timing prerequisites really hold.

A risky death can swing access to carried gems to the killer. Camp death destroys gems; avoid both unless denial is truly decisive and survival is impossible.

## 4. Counter-opponent policy (especially early bot submissions)

Early bots may fail at pathfinding, capturing whole groups, banking, or responding to locks. **Treat these as hypotheses, not observed population statistics.** Robust base farming is the best starting exploit of immature bots.

- **Greedy nearest-camp farmer:** track predictable route, steal vacated group captures, guard profitable respawn tiles only when economical.
- **Greedy gem hoarder:** ambush only if expected kill probability outweighs lost farming tempo.
- **One-altar banker:** use 10g locks at profitable channel windows; scout with wards and retain legal approach positions.
- **Aggressive diver:** fight while they have little to gain, then resume safe farming; don't feed carried gems.
- **Stun-heavy comp:** bank with Marcella where possible and protect her from enemy lock placement.
- **Linked Cassi & Issac:** focus the weaker isolated member, but avoid chasing through bad terrain indefinitely.
- **Monolith rush:** compare whether to contest their five-round capture, deny the spawn, or farm several cheap gem clusters while they spend turns clearing 20,000 HP.

## 5. Draft and shared memory architecture

### During draft

The draft bot sees terrain/map layout and revealed earlier enemy picks. Each round's picks are revealed only after both teams choose. Valid own selections cannot repeat; both teams may pick the same champion. `bc.draft.team_size()` reports picks per team and `bc.draft.current_draft(team)` reports previous choices.

`bc.game_map.camp_groups()` **returns empty during draft**. Precompute only what is actually visible: map width/height, walls, holes, bushes, altars, spawn regions, legal altar approach positions, likely routes and chokepoints. Store a compressed orientation/role-plan in the **1,024-byte draft memory** via the documented draft-memory interface. Determine actual camp-group assignments once gameplay begins.

### During play

The API exposes `bc.game_map.camp_groups()` and group `.gem_value()`, `.gold_value()`, `.max_respawn_timer()`, `.spawn_tiles()` and `.state()`. Champion turns run separate program instances. **Only 8 bytes of team shared memory** remain writable match-long.

Example compact memory scheme (ours, not SDK-defined):

| Offset(s) | Proposed meaning |
|---|---|
| 0 | Protocol version + global mode |
| 1 | Priority objective group ID (0–255, with sentinel) |
| 2–3 | Target tile x,y if map fits byte coords, otherwise packed/higher-precision strategy |
| 4 | Assigned primary champion ID or role code |
| 5 | Last confirmed enemy sighting region |
| 6 | Round modulo 256 / freshness marker |
| 7 | Status flags (alarm, lock seen, contested, etc.) |

**Caution:** 8 bytes are very constrained; values larger than 255 need packing, champion IDs/objective IDs need stable mapping, and turn-by-turn writes may overwrite one another. Start with a trivial, deterministic convention where one elected champion publishes a team objective and others read it. Do not assume the SDK provides atomic compare-and-swap transactions.

### Scheduling within a team

`Champion.set_priority()` changes next-round order (not current-round order). Set a support/control champion earlier when enabling a particular ally's action makes sense; in other circumstances the carrier might act first to escape or score. Team-first ordering alternates each round.

## 6. Practical Python SDK hooks

Use these real documented API entry points, subject to visible-state and legality checks:

| Use | Relevant calls |
|---|---|
| Current score/time | `bc.global_submitted_gems(team)`, `bc.round_number()` |
| Self stats/state | `bc.me().health()`, `.max_health()`, `.gem_count()`, `.gold_count()`, `.state()` |
| Cast/attack/move | `.abilities()`, `ability.is_ready()`, `.damage_amount(target)`, `.heal_amount(target)`, `.use(...)`, `me.attack(target)`, `.can_attack()`, `.can_cast()`, `.can_move()` |
| Legal movement | `me.move_towards(tile)`, `.move_absolute(tile)`, map `.walls()`, `.holes()`, `.altars()`, bitboards |
| Captures | `bc.game_map.camp_groups()`, group `.camps()`, `.spawn_tiles()`, `.state()`, `.gem_value()` |
| Vision | `bc.vision.camps()`, `.champions()`, `.altar_locks()`, `me.place_ward(tile)` |
| Shopping | `me.can_buy(item,count)`, `.buy(item,count)`, `.sell(item,count)` where legal |
| Channels | `me.submit_gems(altar_tile)`, `.is_submitting_gems()`, `.remaining_channel_time()`, `.recall()` |
| Coordination | `bc.shared_memory.read(...)`, `.write(...)`, `me.set_priority(...)` |
| Draft | `bc.is_draft()`, `bc.draft.current_draft(team)`, `.team_size()`, `.pick(...)` |

**Fuel safety:** Python bots have a higher fuel allowance than C++/Rust per the handbook, but fuel is finite. Stop heavy optional planning when `bc.fuel_remaining()` is low and yield with `bc.end_turn()`. A bot that exhausts fuel can suspend mid-computation, which is dangerous for multi-step action plans.

## 7. Anti-stall / reliability requirements

- Check dead/channel restrictions before any offensive decision.
- Use legal targets and masks where possible; an unseen blocker can make a legal-looking move return `False` without consuming allowance, while known-invalid moves raise errors.
- Distinguish **unseen** from **absent** enemy positions; teammates do not automatically share vision.
- Plan to attack **all** monsters in a camp group before capturing; do not stand idle on a live monster spawn.
- Reassign when current target becomes impossible, unavailable, or strategically inferior.
- Cache static terrain and reuse bitboards where beneficial, but cap search effort by fuel.
- Handle no reachable camp, no safe altar, dead teammates, blocked spawn and lost/contested capture.
- Prioritise banking the winning gems over unnecessary fights.
- Never voluntarily resign or assume a timeout is equivalent to successful play.

## 8. Performance measurements

Every match should report team win/loss, win round, tributed gems, gems lost on death, gold earned, gem secured per champion-round, camp completions, contested/lost captures, time spent walking, idle turns, effective damage versus camps, lock cancellations, and fuel use. Tag tests with map seed, enemy bot version and draft. See [EXPERIMENTS.md](EXPERIMENTS.md).
