> **TEMPORARY MVP PLACEHOLDER. Use this baseline for today's MVP; replace and tune it after observing working matches. This is an implementation specification, not installed bot code.**

# MVP pathfinding

Goal: walk legally around terrain/visible units to a useful tile, with minimal code. Use the SDK's native DistanceField and Bitboard operations. The existing leader route planner still chooses the next **objective**; this helper supplies tile routes and distances for any state.

Sources: [movement rules](../../../cambc/GameRules.md#ways-to-move), [DistanceField API](../../../cambc/api/BotAPIPython.md#cambcdistancefield), [SDK move_towards implementation](../../../../sdk/python/cambc/__init__.py). Configuration is in [config.md](../config.md).

## 1. Input/output

Input: a goal-tile mask, current task identity, optional current camp, and TRAVEL, CAPTURE, COMMITTED, or ESCAPE movement policy. SENSE is a distance-only option for safety/support checks; never execute a move from that option. These are helper options, not champion states.

| Result | Meaning |
| --- | --- |
| AT_GOAL | Self already occupies an allowed goal tile; do not move. |
| MOVED | A legal move succeeded. Caller must refresh vision/action availability. |
| WAIT | No movement allowance, channel active, or temporary obstruction; keep task. |
| DEFER | Fuel/call quota is insufficient; no reachability conclusion. |
| NO_ROUTE_NOW | A completed search found no route under the current terrain, visible occupancy, and risk mask. This does not prove permanent disconnection. |
| STATIC_UNREACHABLE | Only a completed search on static terrain alone failed; no ordinary walking route exists under that model. |
| INVALID_GOALS | No static legal goals were supplied. Caller must fix/reselect the objective. |

Do not add a separate navigation state. RUN_AWAY still determines escape; BANK_GEMS still channels; PROTECT_POINT still commits.

## 2. Build legal goal sets

| Task | Goals |
| --- | --- |
| Follow visible leader | Free walkable tiles within FOLLOW_DISTANCE_TILES of its actual position. Exclude the leader tile. If already in formation, stay. |
| Hidden leader | The legal inspection position returned by chunking, not blindly the geometric centre. |
| Living camp / enemy | Free tiles within own basic attack range of the identified target, with target visibility required before an actual attack. Do not seed the occupied monster/champion tile. |
| Cleared camp collector | Legal unoccupied spawn tiles of the exact saved group. Self's current tile may remain a goal. |
| Camp guard | Free tiles close to the observed collector/saved reward region, outside all its spawn tiles. Quiet guards choose an adjacent patrol step within PROTECT_PATROL_RADIUS_TILES and CAMP_GUARD_DISTANCE_TILES; the collector remains on its capture tile. |
| Altar carrier | Free walkable tiles at Chebyshev distance one of the exact selected altar. Never the altar tile. |
| Bank guard | Free guard tiles within BANK_GUARD_DISTANCE_TILES of saved altar/carrier; quiet guards patrol within PROTECT_PATROL_RADIUS_TILES of the exact altar. Preserve the carrier's legal approach/channel tile. |
| Retreat / spawn | Reachable safe friendly approach tiles, otherwise legal allied spawn tiles. |
| DEFEND_SPAWN | Current spawn or other legal allied spawn tiles only; do not chase out of spawn. |

Build only the current target's goals. A large union of all camps can accidentally collect a different task. If self is already a legal formation/holding goal, prefer AT_GOAL over shuffling. Quiet PROTECT_POINT guards instead select one different legal adjacent patrol tile under the close-patrol rule in state_machine.md; never route outside the patrol area to reach it. A collecting body or active channel stays still.

## 3. Blocked mask

    static_blocked =
        walls | holes | altars | enemy_spawn

    dynamic_blocked =
        visible_champion_tiles | visible_camp_tiles | visible_teleport_tiles

    blocked = static_blocked | dynamic_blocked | caller_risk_mask
    blocked[self.position] = false
    goals = supplied_goals & ~blocked

Copy SDK-owned terrain masks before mutation. Clear only self's current tile. Do not clear another body, monster, or altar merely because it is the desired target.

If all statically legal goals are only dynamically blocked, return WAIT/NO_ROUTE_NOW rather than INVALID_GOALS. Hidden camps/units remain unknown and can cause a failed move.

### Simple risk policy

| Policy | Added blocked tiles |
| --- | --- |
| TRAVEL: lead/follow, banking approach, BANK rally travel | Visible enemy basic-attack radii plus PATH_ENEMY_MARGIN; visible awake camps' current attack radii. |
| CAPTURE | Block other visible awake camps' attack areas, excluding the **current objective** group. Do not add enemy-radius exclusion when deliberately approaching a camp/contester for permitted combat; local Danger controls whether this fight may continue. |
| COMMITTED: protect / ATTACK rally | No extra threat-radius exclusion; terrain/occupancy remain blocked. Do not make a mandatory defense impossible solely because it is dangerous. |
| ESCAPE | First try enemy/camp attack-radius exclusions; if no safe route, use the immediate retreat fallback below. |
| SENSE, distance query only | No extra risk exclusion, retaining terrain/visible occupancy. A threat must not appear unreachable merely because its own attack area was deliberately blocked in a TRAVEL mask. |

Only include visible living awake camps; do not block sleeping camps' attack areas until they wake. Sleeping monsters' occupied tiles still block movement. Enemy spell/dash ranges are not predicted here, so this is a basic exposure filter, not a guarantee of safety.

Add all visible threat radii, including threats just outside a target chunk. Channels or another unit's safety summary do not remove physical occupancy.

## 4. Native distance fields

For moving toward a goal set:

    field = DistanceField()
    reached = Bitboard()
    self_mask = a one-tile mask of current position

    field.compute_to(blocked, goals, self_mask, reached)

If self is not reached, return NO_ROUTE_NOW. Otherwise choose a legal one-step destination with strictly smaller field distance:

    candidates = blocked.reachable_tiles(origin, 1)
    candidates exclude origin

Among candidates, minimize (field distance, did_visit_last_turn, y, x), using only candidates reached by the field. Move only if distance decreases. Use me.move_absolute(destination) after checking me.can_move().

The SDK reachable_tiles implements eight-direction walking. Use it instead of inventing corner-cutting rules. A route goes through free space around a wall even when its first step increases straight-line distance from the final target.

For distance estimates to several altars/rallies, compute **one forward field from self**, with a full compute(blocked, self_mask, reached). For each goal set, take its smallest reached distance. Do not compute a new full map once per altar. Reuse within the same observation snapshot only.

For the state machine's wall-separated threat/support checks, a shared SENSE field can test legal attack/approach goal tiles within the configured bound. If fuel/quota defers that query, conservatively treat a visible enemy within LOCAL_THREAT_RANGE as nearby; do not infer safety. Count a deferred ally as support only if already visibly able to attack the relevant threat from its current position. This avoids inventing rescue capacity through walls.

Permit at most PATH_MAX_NATIVE_FIELDS_PER_TURN complete native field computations across movement, estimates, retries, and chunking. Use exact same-snapshot cached fields where possible. A changed position, occupancy, risk policy, or reveal invalidates relevant caches. Never reuse fields from the previous round as current truth.

Use full native search within the known map; no hand-written incremental A* or Python BFS is needed for this MVP. The map has at most 10,000 tiles.

The cached enemy-approach field in [ward placement](ward_placing.md) is a separate static direction heuristic. It may survive across rounds while terrain/goals are unchanged because it deliberately excludes dynamic occupancy and danger. Never reuse it as a current movement or safety field; its initial construction still counts against this turn's shared native-call quota.

Expose three small helpers: distances_from_self(policy) returns a reusable same-snapshot field; plan_step(goals, policy) returns FOUND_PATH with distance/next step, AT_GOAL, DEFER, or a no-route result; move_one_step calls plan_step and returns the movement results above. Chunking can consume plan_step without executing the move itself. Expansion counts, if needed for logging, come from the SDK's *_with_expansion_count variants and are reported after completion.

### Important temporary budget override

The chunking document describes a future hard expansion budget and resumable route queries. The native SDK can **report** expansion count after a call but has no argument that stops at a requested node count. max_distance limits path length, not node expansions.

For this MVP, use NAVIGATION_BACKEND = NATIVE_MVP. It replaces CHUNK_PATH_NODE_BUDGET with the global native-call limit plus fuel admission checks. Chunking may evaluate only the candidate paths that fit that remaining quota; return DEFER for the rest. Do not pretend the existing 128-node setting is enforced or implement a new complex pathfinder just to emulate it.

At low fuel, defer new optional distance estimates/inspection. Essential movement can reuse a valid field or wait. Never interpret skipped computation as NO_ROUTE_NOW.

## 5. Failed moves and congestion

- First check alive, no active channel, and can_move. A ranged champion may have lost walking after attacking/casting.
- A False result from move_absolute can reveal a hidden blocker without consuming movement. Refresh vision, blocked masks, and state safety.
- If still permitted to move, try at most one different legal step, with a fresh route only if the global quota/fuel permits. Never retry the same revealed blocker.
- Expected stale/illegal-action errors end the movement attempt and trigger refreshed observations. Do not hide unrelated programming errors.
- Track consecutive own turns with no successful movement toward the current task while movement was available. At PATH_STALL_TURNS, discard cached route/endpoint, rebuild goals, and report NO_ROUTE_NOW if still blocked.
- Changing an endpoint within the same blocked goal set does not reset the stall counter. A genuine new task or successful move does.
- If a legal side-step strictly improves distance, use it. If no such step exists, wait this turn; do not take arbitrary random detours or permanently blacklist an allied tile.

Ordinary travel retains the task during brief congestion. The caller may reselect an altar after persistent blockage; a camp is not permanently invalid merely because an ally stood in the doorway.

## 6. Immediate retreat fallback

Only RUN_AWAY may use this fallback when the safe-path mask leaves no route. Evaluate self plus up to eight currently legal adjacent tiles. Using current visible enemies and awake camps, rank lexicographically:

1. Fewest visible threats that can basic-attack the candidate tile.
2. Greatest distance to the nearest visible threatening enemy champion/camp.
3. Smallest available walking distance toward the selected safe friendly/spawn; otherwise Chebyshev distance to that anchor.
4. Prefer staying over a move with no strict improvement in the above safety/anchor fields; then (y,x).

Move only to a strictly better tuple than staying. Recheck camp attack ranges per candidate; camps cannot chase. If all choices are worse, hold and make a permitted defensive attack. At spawn the state becomes DEFEND_SPAWN; do not retreat beyond it.

This is a local fallback, so it can still be trapped. It does not promise survival or let a protector abandon its objective.

## 7. MVP integration limits

User revision (22 October 2026): use legal available dashes during normal pathfinding and RUN_AWAY, refreshing observations and routes after landing. State/channel/protection restrictions still apply. Safe landing/progress criteria and priority against other casts remain to be settled in combat.md. Teleport crystals are still outside this baseline. A failed walking route is not proof that no dash route exists.

Only state_machine.md defines transitions. Dynamic camp observations and rally distance rules remain authoritative; there are no side-runner or collector allocations. This document implements movement between already chosen objectives; it does not replace the existing leader's node-selection algorithm.

After every successful move, refresh observation and evaluate safety/completion before attacking, locking an altar, warding, or making another decision. Draw chosen goal/next step only if debug fuel permits.

