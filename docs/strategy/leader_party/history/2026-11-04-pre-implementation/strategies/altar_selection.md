> **TEMPORARY MVP PLACEHOLDER. Use this baseline for today's MVP; replace and tune it after observing working matches. This is an implementation specification, not installed bot code.**

# MVP altar selection and banking approach

Goal: take a carried bag to a reasonably safe reachable altar, remove a blocking lock when worthwhile, and confirm an actual tribute channel. All configurable values are in [config.md](../config.md). PREPARE_GEM_BANKING owns this work; BANK_GEMS owns an active channel.

Sources: [tribute and lock rules](../../../cambc/GameRules.md#tribute-at-an-altar), [Python SDK](../../../../sdk/python/cambc/__init__.py), [pathfinding baseline](pathfinding.md). Static altar positions come from game_map.altars(); locks and enemies require current personal vision.

## 1. Select from exact altar tiles

Index altars once in (y,x) order. For each altar build legal adjacent walking goals, excluding the altar tile itself. Obtain distances using one shared forward distance field from self, with TRAVEL risk policy from pathfinding.md.

- Exclude candidates with no currently reachable allowed approach tile.
- Do not infer reachability from chunk/straight-line distance.
- Do not mark an altar permanently invalid because another body occupies one approach.
- A currently enemy-locked altar remains a candidate: clearing a lock takes time, not a different state.
- Keep hidden lock status UNKNOWN. The absence of a lock in a remote visible-lock list does not prove an unseen altar is unlocked.

For a candidate with walking distance D:

    score =
        D
        + ALTAR_LOCK_HIT_COST * enemy_lock.hits_remaining() if visible there
        + ALTAR_UNKNOWN_LOCK_COST if the altar tile is not currently visible
        + ALTAR_ENEMY_COST * visible enemies within ALTAR_DANGER_RADIUS
        + ALTAR_CAMP_COST * visible awake damaging camps threatening an approach tile

Count distinct currently visible enemy champions. For the camp term count each camp once if it can attack any otherwise usable adjacent approach tile. Sleeping/nonattacking camps do not contribute.

These penalties are approximate travel-step costs. Use only current observations for the MVP; shared enemy records can be integrated after their freshness protocol is finalized. Do not add overlapping reporter counts.

Choose smallest score, then D, then altar (y,x). An allied lock has zero lock-clear cost. If both teams can have locks represented at one location, inspect enemy and allied lists independently: the SDK's generic altar_lock_at returns allied first, which is insufficient for detecting an opposing lock. Build position lookups from vision.altar_locks(Team.ENEMY) and (Team.ALLY).

Example: clear altar eight steps away scores 8; altar two steps away with a fresh five-hit lock scores 2 + 5 = 7, so clearing the nearer altar is acceptable. With one hit remaining it scores 3. Two nearby visible enemies add the configured risk penalty and can make a longer clear route preferable.

## 2. Retain a stable choice

Save exact selected altar, chosen approach, last selection round, and temporary blocked-until rounds privately.

Re-evaluate when:

- No altar selected.
- ALTAR_RECHECK_ROUNDS elapsed.
- Selected approach becomes blocked/unsafe, a lock appears, or the path helper reports persistent NO_ROUTE_NOW.
- Current altar is definitively inaccessible under the supported walking model.
- The unit has resumed banking after escape/recall.

Keep the existing usable altar unless another candidate's score plus ALTAR_SWITCH_MARGIN is **strictly less** than its score. New danger/inaccessibility overrides this margin. Reaching an altar or discovering its enemy lock does not alone require switching.

If a completed route attempt proves current occupancy/risk prevents approach, temporarily exclude that altar for ALTAR_BLOCK_RETRY_ROUNDS and consider another. Do not blacklist on DEFER, a single failed hidden-obstruction step, or lack of remaining movement. Clear the temporary exclusion early when a relevant obstruction is observed to disappear.

Do not reselect during BANK_GEMS. An active channel stays governed by the state table.

## 3. Act while preparing

Read these rows in order after the state machine has allowed preparation:

| Condition | Action |
| --- | --- |
| Bag zero, self dead, Danger, low Health, or spawn recovery applies | Let the state transition table handle it. Retain a positive-bag banking task across recovery. |
| No reachable candidate | Hold safely, keep banking pending, and retry selection after ALTAR_RECHECK_ROUNDS or a material observation change. Never pick arbitrary coordinates or walk into a known threat because all options are blocked. |
| Enemy lock visible at selected altar, not in basic range | Path toward a free adjacent approach tile. Guards may reach a different legal attack tile. |
| Enemy lock visible and basic attack legal | Attack the AltarLock object once, then refresh lock observations. The unit stays PREPARE_GEM_BANKING. |
| No enemy lock; adjacent; own lock absent; carried lock available | Attempt the optional own-lock placement below, refresh state, then try tribute if still legal. |
| No enemy lock; adjacent; bag positive; no active channel/action restriction | Attempt tribute once and confirm actual channel. |
| Otherwise | Approach the selected altar using TRAVEL policy, refresh vision after moving, then repeat relevant local checks within state/action limits. |

Ordinary combat targeting still handles an immediate hostile target before an optional lock attack when that is required by the current state. Never start unrelated camp combat to clear a walking path. A protector may fight even outnumbered; the carrier preparation state can escape according to its own table.

### Clear an opposing lock explicitly

Use the visible enemy AltarLock at this exact altar, me.can_attack(), and current attack-range membership before me.attack(lock). It takes five basic hits from fresh, regardless of Strength. Do not cast unit spells at the lock or assume an attack reset is available. Re-read after each attack; another ally may already have removed it.

Use the fresh lock snapshot's hits_remaining() for the selection estimate. It assumes one hit per own turn and ignores extra help/reset attacks, keeping the estimate simple. Stay at the selected altar while clearing unless real danger or a materially better route arises.

### Place our carried lock

When BANK_PLACE_OWN_LOCK is enabled, a carrier or a local protector of this observed bank attempt may place one:

1. Self alive, not recalling/tributing/teleporting or stunned.
2. Exact selected altar currently visible, within lock placement radius two.
3. No enemy lock remains, and no allied lock already exists there.
4. Own ALTAR_LOCK consumable count > 0.
5. This is the unit's saved current banking objective, not a detour to a random altar.

Use me.consumables()[int(ConsumableType.ALTAR_LOCK)].use(altar). Try at most once per own turn. Refresh inventory, locks, channel flags, and action availability after success/failure. Multiple escorts re-read before placement so they do not deliberately replace an allied lock.

Our lock blocks enemies, permits our own tribute, and can interrupt an enemy attempt. Do not delay a legal tribute simply because no lock is carried.

### Confirm a channel rather than guessing

At a visible unlocked altar within Chebyshev distance one, attempt me.submit_gems(altar) at most once per own turn when bag > 0 and no incompatible channel is active.

This method returns no boolean. Enter BANK_GEMS **only if the fresh engine state reports me.is_submitting_gems()**. Record starting bag, life identifier, team submitted score, and exact altar when the channel actually begins.

An attempt against an opposing lock may become an attack on it. A normal function return therefore does not prove banking started. If no channel is active, refresh facts and stay in preparation; do not issue an unbounded repeat call.

If lock placement or movement consumed another action, respect the refreshed flags. Do not cancel an active channel to shop, ward, attack, change altars, or chase an enemy. Interrupted channels return to preparation under the existing state table.

## 4. Requests and escorts

If this carrier can own/request the BANK rally slot, publish the **selected altar's chunk**, with the saved exact altar privately. Do not overwrite a different live BANK request. A missing shared request does not prevent travelling/tributing.

Within a chunk containing multiple altars, responders need exact carrier/altar identification from a saved personal observation or current vision. Do not make them independently select the nearest altar and assume it matches. Ambiguous remote responders wait for resolution under the communication contract.

Once escorts enter PROTECT_POINT — BANK, they use the saved carrier/altar and direct observation. Rally expiry alone does not stop their protection. A hidden carrier uses the existing bounded reacquisition rule; successful banking is confirmed from channel/bag/score facts, not from the rally disappearing.

## 5. Limits worth keeping visible

This baseline uses current visible threats and basic attack areas; it does not predict enemy reinforcements or exact spell combos. No route is guaranteed safe. A terrain-disconnected altar or ambiguous task may remain unusable until another objective or communication update is available.

The planner does not require an unlocked altar and never treats a lock as permanent terrain. Special-mobility routes, bag-size-specific risk scoring, enemy lock interception, and coordinated attack-reset clearing can be improved after the MVP banks reliably.


## User revision: dynamic bank patrol and turns

Recorded 22 October 2026. There are no allocated escorts. A body entering bank protection from local observations or a rally patrols the current exact altar. Retain its saved carrier under state_machine.md; for a new ambiguous choice prefer a matching live BANK owner, then stable roster slot. Units should take turns banking at one altar. Engine concurrency is being checked; queue admission, waiting protection, and interrupted-channel precedence remain interview decisions.
