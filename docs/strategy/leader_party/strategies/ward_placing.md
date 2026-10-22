> **TEMPORARY MVP PLACEHOLDER. Use this baseline for today's MVP; replace and tune it after observing working matches. This is an implementation specification, not installed bot code.**

# MVP ward placement

Goal: use the free ward near the current objective or travel direction to improve personal vision, without adding movement or another state. Configuration is in [config.md](../config.md).

Rules: one active ward per body, replacement removes its old ward, radius six, placement within two tiles, recharge ten owner turn ends. Wards are permanent under current rules. **Ward vision belongs to its owner only.** Source: [rules](../../../cambc/GameRules.md#wards), [SDK](../../../../sdk/python/cambc/__init__.py).

## 1. Run after essential actions

Run once late in the own turn, after state/safety checks and required attacks, movement, lock handling, and channel initiation. Publish mandatory coordination before optional work. A ward must not delay those actions.

Skip when any condition applies:

- Dead, actively recalling/tributing/teleporting, or stunned/action-prohibited.
- In RUN_AWAY, RECALL, HEALING, or DEATH for this MVP.
- Ward cooldown > 0.
- No useful current objective/next waypoint.
- Remaining fuel is below FUEL_WARD_MIN plus FUEL_CRITICAL_RESERVE.

Other living states may ward, including PROTECT_POINT and DEFEND_SPAWN, provided no active channel/action restriction prevents it. Do not leave a capture/guard position or cancel a channel to place a ward.

## 2. Choose one relevance anchor

Use the first matching available anchor:

| Situation | Anchor |
| --- | --- |
| PREPARE_GEM_BANKING / BANK rally / bank protector | Saved exact altar. |
| CAPTURE_POINT / camp protector | Assigned camp's canonical anchor, or current collector position if visible and available. |
| ATTACK rally | Resolved visible target/known fight position. |
| DEFEND_SPAWN | Nearest local visible threat position, otherwise current spawn tile. |
| LEAD_TEAM / FOLLOW_LEADER | Current route waypoint/visible leader position; otherwise a valid chunk inspection waypoint. |

The anchor is a coordinate used to score relevance. Do not spend a distance-field call to find it. If a remote chunk request has not resolved to an inspection/target position, skip rather than inventing a coordinate.

Define relevant_region as a map-clipped Chebyshev radius WARD_RELEVANCE_RADIUS around the anchor.

## 3. Generate a few conservative candidates

The checked SDK's ward_placement_tiles() draws a radius-two square; it does **not** filter every placement restriction. Start with that mask and filter:

- In bounds and currently visible to this body.
- Not wall, hole, altar, enemy spawn, visible unit/camp, or visible teleport destination.
- No allied ward already present, including self's current ward.
- Otherwise permitted by current engine action restrictions.

This conservative MVP chooses ordinary visible ground/bush tiles. It does not assume all other terrain is impossible for ward placement; it simply avoids the edge cases. Do not require walking to the candidate.

Order candidates by distance to the relevance anchor, then (y,x). Evaluate at most WARD_MAX_CANDIDATES with Ward.visible_tiles_from(candidate), using ward radius six, not the champion's radius-eight query.

For replacement eligibility, allow it only if either no own ward exists, the saved objective identity changed, or self moved at least WARD_RELOCATE_DISTANCE from its last successful ward position. Do not reset this movement test on a failed placement. Cooldown still applies in every case.

## 4. Score actual useful coverage

Obtain:

    current_actual_vision = vision.visible_tiles()
    old_ward_mask = Ward.visible_tiles_from(own_ward_position), or empty
    old_coverage = old_ward_mask & relevant_region

For a candidate:

    new_ward_mask = Ward.visible_tiles_from(candidate)
    new_coverage = new_ward_mask & relevant_region
    gain = new_coverage.count() - old_coverage.count()
    immediate_new = (new_coverage & ~current_actual_vision).count()

Score lasting ward coverage independently of the champion's current sight. On clear terrain, radius-six ward vision placed within two tiles can lie entirely inside radius-eight champion vision; requiring immediate new sight would prevent even the first useful persistent ward. immediate_new is only a tie-break. Read own positions from me.ward_positions(); keep a private last-success record for relocation/objective identity.

Choose largest gain; ties prefer greater immediate_new, then smaller distance to anchor, then (y,x). Place only when gain >= WARD_MIN_GAIN. This compares the old/new ward's relevant coverage, so do not drop a useful old ward for a new one covering fewer relevant tiles just because the owner moved.

If old ward position/visibility cannot be queried reliably, skip optional replacement that turn. For first placement use an empty old mask.

This tile-count score is deliberately simple. A candidate behind a wall receives little benefit because the SDK computes actual terrain occlusion. Bush viewpoints may help, but never assume a ward in one bush sees through all other bush clusters.

## 5. Place once and confirm

Call me.place_ward(chosen_position) at most once per own turn. It returns a boolean:

| Result | Response |
| --- | --- |
| True | Refresh own ward position/cooldown and actual vision. Save successful position, objective identity, and round. |
| False | Refresh newly revealed information; retain previous success record. Skip further ward attempts this turn. |
| Expected invalid-action/destination error | Stop optional ward work, refresh relevant facts, and preserve the current state/task. Do not suppress unrelated programming errors. |

A failed call is not a new ward and does not refresh our remembered old ward. Do not move closer, spend a teleport, or attack a blocker just to make ward placement succeed.

After success, new personal vision may reveal an urgent threat or task completion. Recheck the state machine if within its change limit, then update essential safety/leadership information before yielding. Optional enemy concentration reporting remains fuel-gated.

## 6. Practical results

During travel, a ward placed up to two tiles forward can preserve useful sight behind/around the moving party. Near an altar, it watches relevant approaches while a carrier/escort holds position. Near a camp, it helps the owner notice nearby enemies before a capture finishes.

One ally's ward does not directly give the other bodies sight. They can receive a valid enemy report, but must use their own vision for live getters and actions. This policy does not promise full chunk visibility and does not require filling the entire map with permanent wards.

Upgrade priorities after the MVP: entrance/choke scoring, ally ward coordination, important bush inspection, and preserving a strategically valuable old ward when changing objectives.

