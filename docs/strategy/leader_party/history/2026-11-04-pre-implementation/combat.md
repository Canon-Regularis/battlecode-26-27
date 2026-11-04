# Combat

Historical pre-implementation strategy; superseded by the [current bot documentation](../../README.md).

Status: user-approved principles recorded on 22 October 2026; unresolved tactical choices are listed below. Bot implementation is pending the design interview.

Only [state_machine.md](state_machine.md) defines state transitions and commitment. Combat chooses legal actions inside the selected state. Re-read observations and action allowances after each action; channeling, death, stun, and the current state's movement limits remain authoritative.

## Dynamic participation

There are no assigned combat roles, runners, collectors, or escorts. Leadership is the only allocated role. Each body acts from its current state and personal observations. Remembering the camp, carrier, or altar currently being protected is private task context, not a team allocation.

## Targets and attacks

- Prefer a threatening enemy champion over the current camp. Do not attack unrelated camps deliberately.
- Among currently reachable permitted targets, prefer the lowest current Health. Re-evaluate after every action rather than retaining an obsolete target solely because it was previously selected.
- Use the strongest available legal attack, including damaging abilities. Exact damage-versus-kill and ability-order comparisons are not yet agreed.
- Area attacks should maximize the number of permitted targets hit. The precedence between target count, lowest-Health focus, and strongest damage remains to be settled.
- Ranged bodies prioritize attacking when an attack is available. The state machine decides whether danger instead requires RUN_AWAY. An active channel still forbids ordinary combat.

## Shields, healing, and mobility

- Use an available shield after a Health drop caused by damage that the shield protects against. How to observe damage between own turns, and when that evidence expires, remain to be settled against the updated engine API.
- Use an available dash during RUN_AWAY and normal pathfinding, including travel to the leader, rallies, camps, and other movement goals. A dash does not authorize departure from a committed protection region, movement during a channel, or a destination forbidden by the current state.
- Exact landing safety/progress requirements, dash-versus-damage ability priority, and ally-heal selection remain to be settled.
- Ground effects must respect the engine's actual area and target rules; target positions and affected units must be refreshed before use.

## ATTACK rally creation

Only a body in a state permitting initiation may create an ATTACK rally. Never create one during protection, banking, or while another live rally occupies the shared slot.

Creation requires a clearly favorable close fight, based on numerical and Health advantage. The user's example is an enemy within two tiles at half Health with no other enemies visible. Exact inequalities, supporting-ally eligibility, and the generalization to multiple enemies remain to be settled. Visibility alone never proves that no hidden enemy exists.

Existing cancellation, contact-loss, commitment, and lifetime rules in state_machine.md continue to govern an ATTACK rally once created.

## Remaining interview decisions

1. Target focus versus area target count versus immediate damage; deterministic ties.
2. Shield damage observation window and heal policy.
3. Safe useful dash criteria and priority against other casts.
4. Numeric ATTACK initiation test and eligible initiating states.
