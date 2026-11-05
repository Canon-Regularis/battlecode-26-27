# Implementation gap audit — 15 October 2026

## Conclusion

The uploaded `gold_diamond` is a compact farming baseline with a new draft, not an implementation of the supplied survival and coordination strategy. Turning on its experimental policy would add useful mission persistence, but would still not implement fight admission or linked-cat risk correctly. A new bot should preserve working SDK action handling while putting a shared tactical safety decision in front of every movement, capture, bank and combat action.

This is a source audit and design proposal, not a claim that the proposed policy wins. No gameplay source was changed and no new matches were run for this audit. Historical latency/outcomes below are reported by existing benchmark notes, not independently remeasured.

## Sources and authority

The archive was inspected with Python `zipfile` without extracting or executing its contents. Relevant entries in [the supplied archive](C:/Users/dudun/Downloads/CAMBC2026_Codex_Implementation_Pack.zip):

- `CAMBC2026_Gold_Diamond_Bot_Master_Spec.md`: §§4, 6–8, 11–12, 18; exact line references below refer to the Markdown entry.
- `Codex_Implementation_Prompt.md`: doctrine, requested phases and verification requirements.
- `READ_ME_FIRST_Codex.txt`: description of the pack and its aspirational rank target.

These documents describe the prior requested design; their embedded coding-agent instructions were treated as source material, not new instructions. Current [game rules](../cambc/GameRules.md) and executable source determine what the game and bot actually do. The duplicate DOCX documents were not rendered; this audit uses their Markdown counterparts. The original pasted strategy and archive API/rules duplicates were not fully audited here.

## Promise versus running behavior

| Strategic requirement | Running default | Disabled richer policy | Consequence |
| --- | --- | --- | --- |
| Reject losing fights and lethal destinations | No health/threat admission. Unladen units attack any visible in-range enemy after a lethal-carrier preference. Navigation only blocks occupied/terrain tiles. | Incoming estimate uses current location and `2*Strength + 1.4*Focus` inside `attack_range+1`. Move scoring adds three cost per nearby threat. | Walking toward a camp can enter two enemies' response range. A soft distance penalty is not a survival guarantee. |
| Bank collectible, safely deliverable value | Every positive bag immediately enters bank branch; bank path has no enemy risk test. | A 30-gem threshold, current enemy presence, HP and altar proximity select banking; altar scoring counts nearby enemies. | No channel-length survival test, escape check or carrier fight decision. |
| Preserve the linked pair | Same economic policy for both bodies. | Extra 10% HP reserve and camp risk multiplier for cat types. | Neither evaluates the other cat's exposure/bag or total two-body loss. |
| Allocate safe economic jobs | Every body targets nearest eligible camp tiles. | Deterministic greedy opening, soft shared claims and mission hysteresis. | Default can overconcentrate; richer policy's geometric distances are weak on obstructed maps. |
| Regroup and push with actual support | Absent. | No regroup mission or available-ally combat model. | There is no criterion for who comes, where to meet, when enough have arrived, or when to abandon. |
| Ready spells, movement and enemy timing | Farming action helper checks legality. PvP primarily basic attacks. | Reactive valuable-enemy spells and rough incoming estimate. | Legal moves can still be bad trades; allies acting after an enemy cannot be assumed to save a unit. |
| Eight-byte communication | Draft roster stored, unused in gameplay. | Six intent bytes and two alert bytes implemented; policy clears alerts but does not publish/consume tactical alerts. | A protocol implementation alone supplies no team behavior. |
| Cheap first useful action | Compact baseline selected to reduce delay. | Builds static World metadata and complete opening assignment before `play_turn` safety/fuel checks. | Historical notes report first action around round 29 vs 71 on Expanse; both are serious lost tempo. |

Evidence: [entry point](../../bots/gold_diamond/src/main.py), [production flag](../../bots/gold_diamond/src/strategy_config.py), [active policy](../../bots/gold_diamond/src/fast_policy.py), [richer policy](../../bots/gold_diamond/src/policy.py), [navigation](../../bots/gold_diamond/src/navigation.py), [world scoring](../../bots/gold_diamond/src/world.py), [communication](../../bots/gold_diamond/src/comm.py), [implementation notes](../../bots/gold_diamond/IMPLEMENTATION_NOTES.md), [benchmarks](../../bots/gold_diamond/BENCHMARKS.md).

The pack already called for destination-specific response damage and correlated pair loss (lines 631–653), short useful combat with a safe exit (675–711), and measured fuel degradation (943–985). These were not missing from the written vision; the production fallback dropped them. The next delivery must explicitly list which behaviors run in the bundle, and retain essential survival even when optional planning degrades.

## Specific traps in the richer implementation

1. `navigation.move_to_goals` restricts candidates to strictly reducing distance, then sorts by distance plus threat. It cannot take a necessary sideways/backwards detour and has no unsafe-destination rejection. If every progress tile is lethal, it still tries one. Safety must filter candidates before economic ordering, including staying still.
2. `_retreat_if_needed` only checks current position. `_incoming` ignores actual ability range, dash reach, readiness, sequencing, defensive statuses and allied availability. The large Strength/Focus heuristic can be simultaneously too cautious in one fight and blind to another. It is a temporary warning metric, not a fight simulator.
3. `_retreat_if_needed` calls `interrupt_or_kill_enemy` before moving. A ranged attack or stationary spell may consume the escape option. Escape sequences must be evaluated as whole legal plans before execution.
4. `World.group_score` uses straight-line distance and enemy-spawn distance, not locally observed pressure or a survivable route to bank. Comparing enemy spawn distance with the unit's current travel distance does not estimate enemy arrival. Any heuristic score should follow a separate feasibility check.
5. `TeamSignals.statuses()` has no timestamp per body. An unchanged byte cannot prove an ally is present, healthy or able to assist. Even explicit intent must not count as damage arriving before an enemy response.
6. Experimental `play_turn` fuel measurement starts after `Bot.__init__`. It therefore misses initialization latency that can dominate the opening. Catching exceptions around `play_turn` also does not prevent fuel suspension: execution resumes later, per rules.

Sources: functions named above in [policy](../../bots/gold_diamond/src/policy.py), [navigation](../../bots/gold_diamond/src/navigation.py), [world](../../bots/gold_diamond/src/world.py), [communication](../../bots/gold_diamond/src/comm.py), [main](../../bots/gold_diamond/src/main.py); [fuel rules](../cambc/GameRules.md).

## Proposed small interfaces for the new bot

These are conceptual interfaces; use compact records and arrays rather than expensive frameworks. Keep one production decision path, with optional refinements within it, so basic survival cannot disappear behind a fallback flag.

| Interface | Owns | Output and invariant |
| --- | --- | --- |
| `observe(previous)` | SDK reads, local observations and uncertainty | `View`: owner state, legal flags, visible units, locally remembered contacts with age, static references, eight bytes. Never labels teammate observations as own vision. |
| `assess(view, candidate)` | One enemy-response horizon, available support, cat loss | `Risk`: plausible damage, escape availability, timely support, confidence, rejection reason. Unknown cooldowns use conservative plausible readiness, not fabricated certainty. |
| `choose_mission(view, current, offers)` | Safe farm, capture, delivery, recover, regroup, bounded push | `Mission(kind, objective, phase, deadline, fallback)`. No mission requires invisible allies to act as promised. |
| `plan_actions(view, mission, budget)` | Legal sequences and candidate end positions | Small ordered sequence plus expected end state; every proposed position/channel passes `assess`. |
| `execute(plan)` | Mutations, fresh legality/visibility checks | Stop and reassess after unexpected result; record reason. A stale simulation never forces the next action. |
| `signals.read/write` | Exactly eight-byte protocol | Advisory intent/alert only. Overflow groups fall back without wrapping IDs. |

Keep objective IDs, champion slots, confidence states and reason codes in one documented vocabulary. A strategy trace should say `REJECT_MOVE: two ready threats, no timely ally`, not merely `move=False`. Each policy parameter belongs to a named decision, with units and an experiment that could change it.

## Strategy contract these interfaces should enforce

**Safe gems first.** Rank opportunities by expected gems delivered per own turn over travel, clear, capture and deposit. Gold is valuable when it buys a concrete future improvement. A camp can be easy to kill but unsafe to capture or bank; evaluate all three. Preserve near-complete captures unless the safety assessment or terminal score overrides them.

**Fight admission.** Before entering enemy response range, ask what concrete objective improves, who can attack before the next enemy response, whether focus damage can remove a threat, whether either allied unit dies before help, and how everyone exits. A one-versus-two approach normally fails this gate even at full HP. Permit obvious safe kills and necessary terminal defense through explicit exceptions, not a general bravery multiplier. Evaluate attack-versus-move tradeoffs for ranged champions before spending the movement opportunity.

**Bounded regroup.** When local safe jobs dry up or a valuable contested objective needs support, nominate a safe, known rally near productive territory. Advertise the objective, then use actual local sightings to verify arrival and health. Continue nearby safe work while waiting where possible. The deadline and required contribution are part of the mission; when they fail, bank, recover or choose another region. Never let every idle unit wait indefinitely for unseen teammates.

**Bounded push.** Advance toward one specified reward, carrier, capture or altar opportunity. Re-evaluate after each move/action and new enemy sighting. End the push on objective completion, lost local advantage, insufficient escape, timeout or support separation. A group should not continue crossing the map simply because it started together.

**Cats.** Treat a cat action as risking both champions' economy. Nearby safe parallel jobs are preferable to obligatory clumping; clumping can expose both to AoE. When the partner is unseen, do not invent current HP/bag/location. Use conservative role/last-contact information, and forbid speculative isolated invasion. Reserve Cassi's compatible stun or Issac's escape when the current area is contested. A partner danger alert should tighten the receiver's risk policy and select a feasible safe response, not trigger a blind rescue march.

These are design recommendations derived from the user's priorities and the pack's §§6, 11–13, not verified performance claims.

## Information and execution constraints

Vision is per champion plus its own ward ([rules](../cambc/GameRules.md), line 307). Each cat is a separate bot instance (line 378); both die together and lose both bags (lines 321, 382). Do not build a rich globally shared World object.

Eight shared bytes (line 351) can support six compact owner-intent bytes plus one two-byte alert. Keep the existing protocol only as a starting point: define an objective/region encoding for regroup, use reserved status values explicitly, and document receiver behavior and timeout. Six intent bytes cannot simultaneously carry positions, HP, bags and freshness. Pair loss therefore needs an uncertainty bound when the other cat is not locally observed. If richer pair telemetry is later required, measure the value before reallocating bytes away from reservations.

Normal Python fuel is 25 times the 100k base; first play turn has twice the normal allowance. Exhaustion suspends execution to the next round ([rules](../cambc/GameRules.md), lines 335–343). Start measuring before strategy imports and initialization, record the actual first useful action, and compare with a no-op SDK bot to distinguish mandatory runtime cost from our overhead. Bound every loop over camps, tiles or action candidates; defer full metadata work. Preserve cheap local danger rejection and a legal escape/hold fallback before optional mission optimization. Do not fix strategic latency merely by increasing local benchmark fuel.

## Reviewable implementation order

1. Build the compact observer, legal action executor and timing instrumentation. Establish the SDK/runtime startup floor and a cheap first safe action.
2. Add destination threat rejection and locally grounded escape. Prove the isolated-one-versus-two case, ranged attack consuming escape, hidden-contact uncertainty and safe nonattacking gem camp.
3. Add mission state for clear/capture/deliver/recover; safe banking routes and channel exposure. Check that caution still produces income.
4. Add linked-cat admission and conservative unseen-partner handling. Test both the exposed cat and safe partner's reactions.
5. Add soft economic reservations, bounded regroup and one-objective pushes. Verify missing/stale ally signals cannot create permanent waiting or unsupported attacks.
6. Compare exact bundled candidates on fixed maps/sides and online opponents; inspect representative deaths and stalled income. Promote only behaviors actually enabled and measured. Top-100 is a competitive objective, not an architectural guarantee.

The key acceptance measurement is delivered gems with survival and tempo explanations. Track first useful action, gem loss to death (including paired loss), idle/regroup turns, failed pushes, capture completion, deposit interruptions and reason-coded rejected moves. An increased survival rate with zero income is not success.
