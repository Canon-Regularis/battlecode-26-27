> **TEMPORARY MVP PLACEHOLDER. Use this baseline for today's MVP; replace and tune it after observing working matches. This is an implementation specification, not installed bot code.**

# MVP ward placement

Goal: place the free ward as far from the champion as legally possible toward the likely enemy approach, using the terrain-aware route toward the enemy side of the map. Configuration is in [config.md](../config.md).

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

## 2. Find the direction enemies could approach from

Use one cached **reverse multi-source distance field** toward the enemy side:

1. From the static map, collect legal walkable tiles adjacent to the enemy spawn region. The enemy spawn tiles themselves are forbidden walking destinations and must not be goals.
2. Seed the SDK native distance field with all these approach tiles. Block walls, holes, altars, and enemy spawn. This field describes ordinary walking distance toward the enemy side; omit transient units and threat masks so they do not make the strategic direction oscillate.
3. At the champion's current position, inspect at most eight statically legal walking neighbours using SDK movement geometry. Choose the neighbour with the smallest finite field distance, requiring a strict decrease from the current tile. Break shortest-path ties by best angular alignment toward the enemy-spawn centre, then (y,x); the centre is only a tie-break reference, not a walking goal. The displacement to the chosen neighbour is the forward direction d. At a seed tile, use the direction toward an adjacent enemy spawn tile instead.

This follows the route around walls instead of drawing a straight line through them. Enemy spawn is a heuristic for likely enemy arrival, not proof of where hidden enemies currently are.

Build the field once per body when optional fuel and PATH_MAX_NATIVE_FIELDS_PER_TURN permit; it costs O(map tiles) work and storage. Reuse it while the static terrain and enemy spawn goals are unchanged. Each later direction lookup costs at most eight neighbour checks. Do not compute a path separately for each ward candidate. Field construction uses the existing path fuel admission/reserve checks; if deferred or no enemy-side approach is reachable, retain the old ward and skip placement this turn. This field supplies direction only and never moves the champion.

Keep one relevance anchor for coverage tie-breaks:

Use the first matching available anchor:

| Situation | Anchor |
| --- | --- |
| PREPARE_GEM_BANKING / BANK rally / bank protector | Saved exact altar. |
| CAPTURE_POINT / camp protector | Assigned camp's canonical anchor, or current collector position if visible and available. |
| ATTACK rally | Resolved visible target/known fight position. |
| DEFEND_SPAWN | Nearest local visible threat position, otherwise current spawn tile. |
| LEAD_TEAM / FOLLOW_LEADER | Current route waypoint/visible leader position; otherwise a valid chunk inspection waypoint. |

The anchor only defines useful coverage when forward-placement choices tie; it does not determine the placement direction. Do not spend another distance-field call to find it. If a remote chunk request has not resolved to an inspection/target position, skip rather than inventing a coordinate.

Define relevant_region as a map-clipped Chebyshev radius WARD_RELEVANCE_RADIUS around the anchor.

## 3. Generate a few conservative candidates

The checked SDK's ward_placement_tiles() draws a radius-two square; it does **not** filter every placement restriction. Start with that mask and filter:

- In bounds and currently visible to this body.
- Not wall, hole, altar, enemy spawn, visible unit/camp, or visible teleport destination.
- No allied ward already present, including self's current ward.
- Otherwise permitted by current engine action restrictions.

This conservative MVP chooses ordinary visible ground/bush tiles. It does not assume all other terrain is impossible for ward placement; it simply avoids the edge cases. Do not require walking to the candidate.

Scan the at most 25 radius-two tiles. For each candidate let v = candidate - champion.position. Exclude v = (0,0), backwards candidates, and candidates more than 45 degrees from d: require dot(v,d) > 0 and abs(cross(v,d)) <= dot(v,d). Here cross(v,d) = v.x*d.y - v.y*d.x. If none remain, keep the old ward and skip; do not place one behind the champion merely to spend the cooldown.

For replacement eligibility, allow it only if either no own ward exists, the saved objective identity changed, or self moved at least WARD_RELOCATE_DISTANCE from its last successful ward position. Do not reset this movement test on a failed placement. Cooldown still applies in every case.

## 4. Prefer maximum forward reach

Rank the remaining candidates in this order:

1. Greatest Chebyshev distance from the champion: use the full two-tile placement range whenever a legal forward candidate exists there.
2. Closest angular alignment with d. Compare dot(v,d)^2 / (v.x^2 + v.y^2), greatest first; compare fractions by integer cross-multiplication, with no angles, square roots, or floating point.
3. Greatest forward projection dot(v,d).
4. Greatest actual ward coverage in relevant_region, then greatest newly visible coverage; final tie-break (y,x).

Only use optional Ward.visible_tiles_from(candidate) calls to distinguish candidates tied on the first three priorities, at most WARD_MAX_CANDIDATES queries. Use ward radius six, not the champion's radius-eight query. If the remaining optional fuel is insufficient for coverage tie-breaks, choose by the geometric priorities and (y,x). Coverage cannot select a closer or less forward ward over a candidate that already wins those priorities.

For these tie-breaks:

    new_coverage = Ward.visible_tiles_from(candidate) & relevant_region
    immediate_new = (new_coverage & ~vision.visible_tiles()).count()

Keep persistent coverage separate from immediate new sight: a ward may be useful after the champion moves even when currently inside champion vision. The former WARD_MIN_GAIN coverage-gain gate is removed; forward distance and direction now choose placement. Keep the cooldown and replacement-eligibility checks above, and skip replacing a ward already on the selected tile. Read own positions from me.ward_positions() and retain the last successful placement/objective privately.

If the old ward position cannot be queried reliably, skip optional replacement that turn. This policy does not move the champion, teleport, or displace a collector just to gain placement range.

For example, on open terrain with an eastward route, prefer (x+2,y); with a northeastward route, prefer the tile two steps along that diagonal. A wall can turn the route direction toward a corridor even when the enemy spawn lies geometrically east. Illegal tiles are filtered before ranking; do not assume a ward sees through walls or other bush clusters.

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

During travel or close protection patrols, the ward sits at the furthest legal placement toward the terrain-aware enemy approach. Near an altar or camp this aims its persistent vision toward incoming enemies while the champion stays with its task.

One ally's ward does not directly give the other bodies sight. They can receive a valid enemy report, but must use their own vision for live getters and actions. This policy does not promise full chunk visibility and does not require filling the entire map with permanent wards.

Upgrade priorities after the MVP: multiple enemy approach corridors, ally ward coordination, important bush inspection, and preserving a strategically valuable old ward when changing objectives.

