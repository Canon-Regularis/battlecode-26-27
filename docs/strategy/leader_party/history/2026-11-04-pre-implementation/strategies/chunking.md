# Global chunking and target inspection

Historical pre-implementation strategy; superseded by the [current bot documentation](../../../README.md).

Status: selected design for the leader-party strategy; not implemented. This document defines the shared map partition and a bounded inspection helper. It does not replace the leader's route planner, select which altar to bank at, or change the state machine's safety priorities.

Read with [configuration](../config.md), [communication](../communciation.md), and [state transitions](../state_machine.md).

**Temporary MVP navigation override:** [pathfinding.md](pathfinding.md) now specifies NAVIGATION_BACKEND = NATIVE_MVP. In that mode, use the SDK's complete native DistanceField search with global per-turn call/fuel limits. The hard CHUNK_PATH_NODE_BUDGET and resumable-route contract below are future targets, not enforced by this native backend; expansion-count methods report work after completion. Return DEFER when the shared native-call/fuel quota is exhausted. Chunk mapping and the other local inspection/viewpoint limits remain unchanged.

## Decision at a glance

| Part | Decision |
| --- | --- |
| Partition | Balanced rectangular grid, at most 15 tiles per side. |
| Supported game dimensions | Rules specify 30×30 through 100×100. Width and height are handled independently; no square-map assumption. |
| Smallest map | 30×30 -> 2×2 chunks, each 15×15. |
| Largest map | 100×100 -> 7×7 chunks, each 14 or 15 tiles per side. |
| Chunk count | At most 49; six bits per location on every map. |
| Invalid ID | 63. Valid IDs are 0 through chunk_count - 1. |
| Centre guarantee | Every chunk tile is within seven Chebyshev steps of its nominal centre. With unobstructed sight, a champion's radius eight covers the entire chunk. |
| Obstructed sight | Choose legal viewpoints using SDK hypothetical vision; inspect a bounded sequence if necessary. |
| Static objectives | Use known altar/camp positions directly once identity is unambiguous. Do not walk to a centre just to discover static map data. |
| Dynamic targets | Use current visible identity first; otherwise inspect the fresh reported chunk and recheck its report. |
| Failure result | Return a specific unknown/ambiguous/blocked/expired result. Never turn failed search into proof of death, safety, or completion. |

The chunk ID is a compact **area address**. It is not an exact coordinate, a path, a promise of safe terrain, or a unique camp/altar identifier.

## 1. Rules and SDK evidence

| Fact | Design consequence | Source |
| --- | --- | --- |
| Map dimensions range from 30×30 to 100×100. | Bound grid count using 100, but calculate using actual width/height. | [Rules: map features](../../../../../cambc/GameRules.md#map-features) |
| Champions see up to eight tiles in every direction, including diagonally. Walls and bushes block sight. | Chebyshev range gives an open-terrain guarantee; geometry alone cannot prove actual visibility. | [Rules: vision](../../../../../cambc/GameRules.md#what-you-can-see) |
| Standing in a connected bush makes that bush transparent to the observer; other bushes still occlude. | A viewpoint inside a bush can expose targets an outside centre cannot see. Evaluate using the engine. | [Rules: vision](../../../../../cambc/GameRules.md#what-you-can-see) |
| Holes do not block sight; they cannot be ordinary walking destinations. Altars and enemy spawn tiles also cannot be ordinary destinations. | Visibility and standability are separate filters. | [Rules: movement](../../../../../cambc/GameRules.md#ways-to-move) |
| Own ward contributes vision, but teammates' vision/wards are not shared. Ward radius is six. | Inspect using this body's actual visible mask; do not assume a ward alone covers a 15×15 chunk. | [Rules: wards](../../../../../cambc/GameRules.md#wards) |
| Static terrain, altar positions, camp groups, and spawn positions are available through map queries. | Pre-index static objectives; hidden current camp state still needs a legal live query. | [game_map.py](../../../../../../sdk/python/cambc/game_map.py) |
| Champion.visible_tiles_from(position) / visible_tiles_from_into provide hypothetical champion vision. | Use these for candidate visibility; do not substitute Ward.visible_tiles_from or implement an approximate line-of-sight algorithm. | [Python API](../../../../../cambc/api/BotAPIPython.md#visible_tiles_from), [SDK implementation](../../../../../../sdk/python/cambc/__init__.py) |
| Group.state() requires at least one spawn tile in current vision and returns a group-level state. | A valid engine group-state result can confirm a cleared group without manually seeing every monster. Merely seeing one dead monster cannot. | [game_map.py](../../../../../../sdk/python/cambc/game_map.py) |

The SDK visibility query predicts which tiles would be visible; it does not reveal unseen occupants or make a destination walkable. Confirm observations after arriving.

## 2. Why balanced chunks of at most 15×15

Radius eight could cover a 17×17 open square from its exact centre. That leaves no range margin for an alternative centre tile. A maximum side of 15 keeps the farthest edge at distance seven and still uses the same six-bit location field as a 17-tile grid.

| Maximum side considered | Grid at 100×100 | Maximum chunk count | Bits including an invalid value | Trade-off |
| --- | --- | ---: | ---: | --- |
| 10 | 10×10 | 100 | 7 | Smaller search regions, one more bit per location. |
| **15 — selected** | **7×7** | **49** | **6** | One tile of range margin at the nominal centre; compact location. |
| 17 | 6×6 | 36 | 6 | No further bit saving; larger search regions and no worst-case centre margin. |

With 15×15 chunks, any adjacent tile to the nominal centre is also within radius eight of every chunk tile, **if nothing occludes sight**. This gives at least a 3×3 set of range-valid centre alternatives before terrain filtering. It does not guarantee any of them is legal or sees through a wall.

Balanced division avoids a one-tile strip when a map dimension is just over a multiple of 15. For example, dimension 31 becomes 11 + 10 + 10, rather than 15 + 15 + 1. No terrain-based splitting/merging changes the shared IDs; terrain only changes private inspection choices.

## 3. Exact coordinate mapping

Use SDK coordinates, not screen orientation or distance from allied spawn. All bodies use the same origin, width, height, and increasing x/y directions. Never mirror IDs for the other team.

Let W and H be actual map dimensions; S = CHUNK_MAX_SIDE = 15.

    columns = (W + S - 1) // S
    rows    = (H + S - 1) // S
    chunk_count = columns * rows

For a valid tile (x, y):

    column = (x * columns) // W
    row    = (y * rows) // H
    chunk_id = row * columns + column

All arithmetic is integer arithmetic. Validate 0 <= x < W and 0 <= y < H **before** calculating. Do not clamp an invalid target onto the map.

To decode a valid ID:

    row    = chunk_id // columns
    column = chunk_id % columns

    x0 = (column * W + columns - 1) // columns
    x1 = ((column + 1) * W + columns - 1) // columns - 1
    y0 = (row * H + rows - 1) // rows
    y1 = ((row + 1) * H + rows - 1) // rows - 1

Bounds x0..x1 and y0..y1 are **inclusive**. The nominal centre is:

    centre_x = (x0 + x1) // 2
    centre_y = (y0 + y1) // 2

For even widths/heights, choose the lower coordinate of the two central choices. This is a deterministic tie-break, not a tactical preference.

**Do not replace the ceiling divisions in the bounds with floor divisions.** The inverse of floor(x * columns / W) starts at ceil(column * W / columns). Mixing these conventions assigns boundary tiles to the wrong chunk.

### Why this covers every tile exactly once

For each axis, the starts are ceil(i * length / number_of_parts). Part i ends one tile before part i+1 starts; the first start is zero and the last exclusive end is the map length. Therefore there are no gaps or overlaps.

Widths differ by at most one and never exceed 15, since number_of_parts = ceil(length / 15). With dimensions at most 100, there are at most seven parts on either axis and 49 chunk IDs.

### Worked examples

| Map | Grid | Chunk count | Valid IDs | Chunk side lengths |
| --- | --- | ---: | --- | --- |
| 30×30 | 2×2 | 4 | 0–3 | 15 × 15 |
| 31×31 | 3×3 | 9 | 0–8 | 10 or 11 |
| 45×45 | 3×3 | 9 | 0–8 | 15 × 15 |
| 46×46 | 4×4 | 16 | 0–15 | 11 or 12 |
| 70×50 | 5×4 | 20 | 0–19 | Width 14; height 12 or 13 |
| 99×99 | 7×7 | 49 | 0–48 | 14 or 15 |
| 100×30 | 7×2 | 14 | 0–13 | Width 14 or 15; height 15 |
| 100×100 | 7×7 | 49 | 0–48 | 14 or 15 |

For a 31-wide map, x ranges are **0–10, 11–20, 21–30**. Thus x=10 belongs to column 0; x=11 belongs to column 1.

For 100×100, tile (23,47):

    column = 23 * 7 // 100 = 1
    row    = 47 * 7 // 100 = 3
    id     = 3 * 7 + 1 = 22
    bounds = x 15..28, y 43..57
    centre = (21,50)

The last tile (99,99) maps to ID 48, with bounds 86..99 on both axes and centre (92,92). Chunk neighbours are grid neighbours only; that does not mean terrain allows a direct path.

## 4. Six-bit encoding and validation

Every location field is six bits on **every** map. Do not vary offsets by map size. Even the 30×30 map uses six bits, so all readers share one fixed layout.

| Value | Interpretation |
| --- | --- |
| 0 <= ID < chunk_count | Valid chunk. |
| chunk_count <= ID <= 62 | Invalid for this map. |
| 63 (binary 111111) | Explicit NONE/unknown sentinel. |

Zero is a real chunk. The invalid sentinel is never passed into the bounds decoder. A malformed ID cannot be repaired using modulo or bit masking.

Each location now needs six rather than fourteen coordinate bits. Leader, rally, and enemy location fields together use 18 bits instead of the previous 21. [communciation.md](../communciation.md) contains the updated offsets; this frees three more bits, leaving 17 reserved bits in that proposal.

The format is incompatible with the earlier seven-bit chunk layout. All team bodies must use the same version at initialization. Do not mix old 127 sentinels or old bit offsets with this mapping.

## 5. Resolve the target before selecting a viewpoint

An inspection request includes:

| Input | Meaning |
| --- | --- |
| Kind | LEADER, CAMP, BANK, or ENEMY_AREA / identified enemy. |
| Chunk | Valid fresh location record. |
| Identity | Leader roster slot; known camp group, altar coordinate, carrier, or enemy handle when available. |
| Record identity | The communication record's generation/ownership identity once that protocol is finalized. |
| Caller constraints | Current state's allowed movement, risk/commitment policy, and action availability. |
| Lifetime | Communication expiry plus the caller's own lifetime, such as the absolute attack-rally cap. |

Apply the following in order:

| Target | Resolution |
| --- | --- |
| Visible intended leader/enemy/carrier | Use its current exact position immediately, even if it has crossed the reported chunk boundary. Recheck leader ownership first. |
| Known exact altar | Use its static location and legal adjacent/guard positions. Do not route onto the altar tile. No centre search is needed. |
| BANK chunk with exactly one indexed altar | The altar position is unambiguous; resolve it directly. Carrier identity and live channel still require confirmation. |
| BANK chunk with multiple altars | Use an already saved exact altar/carrier observation. Otherwise return AMBIGUOUS; do not pick the nearest altar and pretend it is the caller's target. |
| Known camp group | Use its static spawn positions and current legal group-state queries. Its current monsters/rewards are not known merely from the static index. |
| CAMP chunk with one group assigned to that chunk | Resolve that group; obtain live state before acting. |
| CAMP chunk with multiple assigned groups | Use a personally resolved observed leader target or an unambiguous activity report; otherwise AMBIGUOUS. There are no team task allocations. |
| Leader not currently visible | Inspect the reported chunk for the specific leader handle; another allied body is not a successful match. |
| Enemy concentration report | Inspect for contact if the caller chooses. Finding any enemy gives area contact, not confirmation about a different specific enemy or the report's total count. |

### Camp groups spanning chunk boundaries

Choose each group's canonical anchor as the spawn tile with smallest (y, x). Its home chunk is the chunk of that anchor. Index the whole group under that one home chunk, even if monsters span several chunks.

A CAMP command publishes that home chunk; it is an **objective address**, not necessarily the initiator's own location. Store the exact group privately when identified. For convenience, a separate private intersection index can list all groups touching a chunk, but do not use it to change the broadcast convention.

Two groups can have the same home chunk. Chunking cannot fix this information loss; the observation encoding must distinguish them without allocating roles. Do not split the actual game camp group at a chunk boundary.

Static altar selection remains in the later altar strategy: this system only resolves which altar an existing request means.

## 6. Choosing legal inspection positions

### 6.1 Separate the nominal centre from a real destination

The nominal centre is geometric. The actual destination must be reachable and legal for this body.

Ordinary walking candidates exclude walls, holes, altars, and enemy spawn tiles. Recheck dynamic occupancy, action restrictions, and current move masks before moving. Sleeping/living camps, allied bodies, and unseen enemies can block a tile that passed the static filter.

The pathfinder may use a legal dash/teleport when the caller permits it. Chunking never assumes every champion can cross a hole or teleport. A walking failure is not proof that a special-mobility route exists or does not exist.

### 6.2 Compute the central range-valid rectangle

Let R = CHAMPION_VISION_RADIUS = 8. A viewpoint p is within radius R of **every** tile of the chunk exactly when:

    x1 - R <= p.x <= x0 + R
    y1 - R <= p.y <= y0 + R

Intersect this rectangle with map bounds and legal candidate tiles. Call it the central candidate set. It is a range guarantee only; check the actual hypothetical vision mask for occlusion.

Order these candidates by:

1. Chebyshev distance from nominal centre, ascending.
2. Chebyshev distance from self, ascending.
3. y, then x, ascending.

The nominal centre is considered first if legal. Different bodies may choose different reachable viewpoints while still agreeing on every chunk ID.

### 6.3 Use engine vision, then bounded path checks

For each candidate evaluated:

    predicted = me.visible_tiles_from(candidate)
    visible_part = predicted intersect chunk_mask

For a static resolved target, score visibility of the target's relevant tiles rather than the entire chunk. For an unresolved dynamic target, prefer a candidate whose predicted mask covers the whole chunk; otherwise prefer more as-yet-uninspected chunk tiles.

Evaluate no more than CHUNK_VIEW_QUERIES_PER_TURN candidates with the SDK per turn. Among evaluated candidates, rank:

1. Covers the resolved target / the whole chunk.
2. Number of new relevant tiles visible, descending.
3. Known route length, ascending; unknown route costs are not treated as zero.
4. Distance to nominal centre, then y, then x.

Try bounded path queries in that order, within CHUNK_PATH_QUERIES_PER_TURN and the shared per-turn CHUNK_PATH_NODE_BUDGET. A path-budget exhaustion returns DEFER, not UNREACHABLE. Route search may go outside the chunk: a doorway can be in a neighbouring region.

This finds a usable candidate from a bounded sample; it does not claim to find the globally best viewpoint. Never hold the turn waiting to evaluate every tile.

Hypothetical masks may be cached privately by map, champion vision profile, and candidate position, up to CHUNK_VIEW_CACHE_ENTRIES (initially 32). Evict least recently used entries, ties by (y,x), and invalidate on a map/vision-profile change. They describe terrain visibility; they contain no hidden enemy observations. Actual vision, including the body's own ward, remains authoritative after movement.

### 6.4 Fall back to a wider candidate set

If central positions do not reveal the target, consider legal positions in the chunk's rectangle expanded by R tiles on each side and clipped to the map. This includes every possible radius-R position capable of seeing at least one chunk tile. At maximum chunk size the rectangle has at most 31×31 = 961 tiles.

Do not evaluate all 961 positions with the SDK in one turn. Incrementally enumerate at most CHUNK_CANDIDATE_SCAN_PER_TURN raw tiles, persist the cursor, reject illegal/previously inspected positions, and add candidates to a private queue. It can contain no more than the clipped rectangle's tile count, at most 961; do not duplicate entries across tiers.

Prioritize raw candidates by these tiers, with distance to self then (y,x) inside each tier:

1. Legal uninspected bush tiles in the target chunk, because entering a bush can expose hidden targets.
2. Other legal uninspected target-chunk tiles.
3. Remaining legal target-chunk positions.
4. Legal positions outside the chunk within the expanded rectangle.

Use the same exact hypothetical-vision and route ranking on the next bounded batch. Discard candidates with zero new relevant predicted coverage unless they directly reveal a resolved target not yet confirmed.

Freeze the distance-ordering origin when this candidate pass begins, so walking does not reorder the remaining queue every turn. An incremental iterator can visit Chebyshev rings around that origin, clipped to the inspection rectangle, yielding matching-tier tiles in (y,x) order. Count every raw tile examined against the scan budget, including rejected tiles; persist both tier and ring position. Do not perform an unbudgeted 961-tile sort first.

Bush entry still follows the caller's risk policy. It can expose an enemy; it is not guaranteed safe. The search helper must never cancel a committed objective or ignore RUN_AWAY just to finish coverage.

Do not create extra shared subchunks for walls, bushes, disconnected rooms, or viewpoints. Inspection positions and visited masks stay private.

## 7. Bounded inspection lifecycle

This helper has private phases, **not new champion states**. FOLLOW_LEADER remains FOLLOW_LEADER while inspecting; the caller owns all state transitions.

Retain the request identity, current chunk, viewpoint/candidate cursors, inspected viewpoints, union of previously observed chunk tiles, local search start, movement cost, and counters.

| Phase | Exact behaviour |
| --- | --- |
| Resolve | Validate record and target identity. Use visible/unique static targets immediately; return AMBIGUOUS where necessary. |
| Approach | Route to the selected legal inspection position, checking the request and visible target each turn. Long-distance travel is the existing pathfinder's job. |
| Inspect | On reaching an inspection position, query actual visibility and visible identities before moving again. Stop immediately if the target is found. If the whole chunk is currently visible and has no matching dynamic target, return NO_MATCH_NOW. |
| Search | Update private coverage history; select another viewpoint under the query, movement, and turn budgets. |
| Finish | Return FOUND or a precise failure/defer result to the caller. Do not silently start unrelated camp work. |

Local inspection begins when self enters the target chunk or reaches the first chosen inspection viewpoint, whichever happens first. That turn is local search age zero. Budget checks precede further search actions.

| Budget | Initial value | Counting rule |
| --- | ---: | --- |
| CHUNK_SEARCH_MAX_STEPS | 12 | Successful movement distance after local inspection starts. Charge Chebyshev distance between old/new tiles, including dash/teleport distance; failed moves cost zero. |
| CHUNK_SEARCH_MAX_TURNS | 8 | Stop at local age >= value in own turns; waiting/stun/computation delays count. |
| CHUNK_SEARCH_MAX_VIEWPOINTS | 4 | Maximum distinct inspection viewpoints visited, including the first. Refresh observations before declaring the limit exhausted. |
| CHUNK_APPROACH_STALL_TURNS | 3 | During approach, return BLOCKED after this many consecutive own turns with neither route-planner progress nor movement toward an inspection goal. |
| CHUNK_CANDIDATE_SCAN_PER_TURN | 128 | Maximum raw candidate tiles processed in a turn. Persist cursor. |
| CHUNK_VIEW_QUERIES_PER_TURN | 4 | Maximum hypothetical-vision calls in a turn. |
| CHUNK_PATH_QUERIES_PER_TURN | 4 | Maximum candidate route queries in a turn. |
| CHUNK_PATH_NODE_BUDGET | 128 | Future combined route-expansion cap; inactive under NATIVE_MVP, which uses the shared native-field quota/fuel checks. |

These are tuning defaults centralized in config.md, not evidence that every chunk can be searched within eight turns. State transitions, request expiry, and attack deadlines can end search sooner.

A heartbeat refresh of the same target/record in the same chunk **does not reset search budgets**. A real target/leader replacement starts a different request. A changed chunk replans inspection and resets local coverage for that chunk; it must not reset the parent task's absolute lifetime.

After EXHAUSTED, BLOCKED, NO_LOCAL_VIEWPOINT, or NO_MATCH_NOW, do not immediately recreate the same unchanged request every turn. Retry only after CHUNK_RETRY_ROUNDS or a material change: target becomes visible, leader/target identity changes, reported chunk changes, or a known obstruction clears. Mere timestamp refresh is not a material change. AMBIGUOUS requires new identity information; repeating inspection cannot resolve identical messages for different objectives.

Recheck record freshness after any suspension/resumption. A valid new observation beats a cached waypoint.

### Result contract

| Result | Meaning and caller response |
| --- | --- |
| FOUND | Intended entity is currently visible, or exact static objective identity resolved. Includes exact target/identity and whether live state was observed. Static location alone does not confirm an active bank channel/camp state. |
| CONTACT | Enemy-area request found visible enemy contact, without identifying an unspecified original target. Combat caller chooses its permitted action. |
| NO_MATCH_NOW | The entire chunk is in this body's current actual vision and the intended dynamic target is absent there. Re-read the report; this does not prove death, absence in neighbouring chunks, or lasting safety. |
| MOVING | A legal waypoint/path is selected and approach/search continues. |
| DEFER | Not enough fuel/query budget to finish this turn. Preserve cursor; do not mark unreachable. |
| EXPIRED / REPLACED | Current request no longer valid. Stop using its position; caller handles the replacement normally. |
| AMBIGUOUS | More than one objective can match the available message. Need exact objective identity or observation. No arbitrary choice. |
| NO_LOCAL_VIEWPOINT | Candidate enumeration exhausted with no further permitted/reachable candidate giving useful coverage in the inspection rectangle. This is not proof that the target is dead or globally unreachable by every mobility option. |
| BLOCKED | Current approach stopped making progress for the configured limit. A temporary obstacle may clear later. |
| EXHAUSTED | Search movement/turn/viewpoint budget reached before finding the target. Outcome unknown. |

For a failed FOLLOW_LEADER inspection, retain the state, reread leadership, and hold safely/seek a fresh report under the retry rule; use spawn fallback if no valid leader/anchor remains. Do not declare the leader dead. For ATTACK, failed local search is not proof of a kill; the owner applies existing contact-loss/deadline rules. For committed bank protection, its BANK_REACQUIRE_TURNS and saved carrier/altar take precedence over this generic budget.

## 8. Observation, coverage, and moving targets

Keep these concepts separate:

| Fact | What it proves |
| --- | --- |
| Hypothetical mask covers the chunk | That position should expose all chunk tiles under the modeled terrain/vision profile. No statement about hidden occupants until observed. |
| Current actual mask covers the chunk | All those tiles are visible **now**, to this body. Current visible-unit queries can inspect their occupants. |
| Union of masks over several turns covers the chunk | Those tiles were seen at different times. A moving enemy/leader can cross between observations; this does not prove present absence. |
| Leader absent from one inspection position | Only that it is not currently visible from here. It may have moved or be behind occlusion. |
| Enemy report count | Number of distinct enemy champions seen by that reporter in that chunk, not an upper bound. |
| A group-state query says reward available | Whole group is cleared under that engine result; actual collection/occupancy still needs its own checks. |

Always accept a currently visible intended leader even if outside its last reported chunk. If a target is visible only through this body's ward, identity is resolved but the movement path still needs terrain/safety checks.

Never clear another body's fresh concentration report just because this observer has a smaller view. Never accumulate enemy counts across time or observers. Count current visible enemy handles once each, assigning each to the chunk of its current position. Combat outnumbering still uses local range across chunk boundaries and excludes camps.

## 9. Edge cases

| Case | Required handling |
| --- | --- |
| 30×30 minimum | Four balanced 15×15 chunks; same six-bit protocol. |
| 100×100 maximum | Forty-nine chunks, IDs 0–48; no allocation overflow. |
| Odd dimensions / rectangles | Independent integer formulas; no floating rounding or square assumption. |
| Exactly on boundary | Forward mapping determines ownership; inclusive bounds must decode it back consistently. |
| Corner/edge chunk | Bounds and expanded inspection region clipped to map. Never query hypothetical vision out of bounds. |
| Centre is wall, hole, altar, enemy spawn | Use legal alternatives, not movement into centre. |
| Centre occupied by ally or camp | Treat as dynamic blockage; select another viewpoint or wait within limits. Do not permanently blacklist terrain. |
| Hidden enemy blocks a legal-looking step | Respect SDK false/failed move result, refresh revealed information, and re-evaluate state safety before another move. |
| Wall divides a chunk into rooms | Route through a legal doorway, possibly outside the chunk; visit multiple viewpoints or return unknown within budget. |
| Fully disconnected region | Do not assume neighbour chunks imply connectivity. Reachability is specific to body/allowed movement; bounded path exhaustion is not a proof of disconnection. |
| Bush hides part of chunk | Use hypothetical masks and legal bush-entry viewpoints, subject to safety. Do not assume all bush clusters become visible from one bush. |
| Hole separates two platforms | It does not occlude sight, but walking connectivity differs. Special mobility is optional and must be legal for this body. |
| No walkable tile inside chunk | Try legal inspection positions in the expanded region; do not delete/renumber the chunk. |
| Several altars/camps share a chunk | Return ambiguity unless a saved assignment/observation resolves it. |
| Camp crosses multiple chunks | One canonical home chunk; the game group remains indivisible. |
| Enemy/leader changes chunk | Visible exact position wins; otherwise replan from fresh report. Chunk changes do not reset attack lifetime. |
| Same chunk, different leader | Roster identity/replacement record changes the target even when location bits do not. |
| Party report means work anchor | Inspect the objective indicated by leader message; do not mistake its chunk for the new leader's physical location. |
| Ward gives distant view | Resolve observations, but still enforce path distance and state safety. |
| Rally centre close but actual target far | Join only after resolving a useful target/guard tile and checking actual configured path range. |
| Fuel exhausted/resumed later | Invalidate stale observations/buffers, re-read record and actual state; continue bounded work only if still relevant. |
| Malformed ID or dimensions | Reject explicitly. Never wrap, clamp, divide by zero, or alias to another chunk. |

Production supports the documented per-axis interval 30..100. Arithmetic can also be exercised on 1..29 in isolated development checks, but such maps are outside the stated game contract. Zero/negative dimensions are always invalid. A future larger map/radius change requires a versioned config/protocol review, not silently increasing the number of chunks.

## 10. Precomputation, fuel, and interface

### Startup / draft facts

Compute columns/rows, all bounds/centres, and optional axis lookup arrays x_to_column[W], y_to_row[H]. Index static altars by chunk and camp groups by canonical home chunk. The mapping requires no shared-memory writes or draft-memory table; every body can derive it from static map dimensions.

Axis lookup arrays total at most 200 entries. At most 49 chunk descriptions are required. Do not precompute hypothetical vision for every tile of every chunk. Create chunk masks, candidate queues, and a limited viewpoint cache only as needed.

Static map masks are SDK-owned/cached: copy before mutation. Team-relative standability may differ, but the chunk ID mapping never does.

### Required helper interfaces

| Helper | Contract |
| --- | --- |
| chunk_of(x,y) | Validate coordinate; return six-bit-compatible ID in constant time. |
| chunk_bounds(id) | Validate ID; return inclusive bounds. |
| chunk_centre(id) | Return deterministic nominal centre, without promising standability. |
| objectives_in_chunk(kind,id) | Return static altar list or canonical camp-group list, without live state claims. |
| begin_inspection(request) | Validate target/record; create private search record or return immediate resolution/ambiguity. |
| advance_inspection(record, caller_constraints) | Bounded queries/observations; returns the result enum above and optional waypoint/target. |
| stop_inspection(record) | Release private search data; never clear shared objective ownership as a side effect. |

Route planning accepts a tile/goal set and returns FOUND_PATH/AT_GOAL, NO_ROUTE_NOW under the current mask, or DEFER, with distance/next step where applicable. Only a completed static-only search can establish STATIC_UNREACHABLE. The temporary native backend is specified in pathfinding.md; future resumable searches must never treat a node budget as proof of disconnection.

Check FUEL_CHUNK_QUERY_MIN plus FUEL_CRITICAL_RESERVE before costly vision work; route calls also check FUEL_PATH_MIN plus reserve. If not available, return DEFER. Config provides provisional Python values that need measurement; call-count caps alone cannot guarantee staying under the fuel limit.

A fixed static membership query is O(1), per-visible-enemy counting is O(number of visible enemies), and target inspection is incremental with explicit caps. The return dispatcher does not perform a full-map scan.

## 11. Verification and implementation boundaries

The integer partition/centre arithmetic was checked over all 5,041 width/height combinations from 30 through 100, covering all 21,298,225 tile positions across those shapes. Every tile mapped inside its decoded bounds. Observed maxima were 49 chunks, side length 15, and nominal-centre Chebyshev distance seven. Implementation must also reject sentinels and malformed IDs before decoding.

Implementation-level checks later should cover opaque walls, multiple bush clusters, an occupied centre, a group crossing a boundary, two altars in one chunk, stale leader reports, fuel suspension, and limited paths. Arithmetic checks do not establish engine visibility behaviour or strategic performance.

This design resolves the chunk mapping, six-bit capacity, inspection approach, and bounded failure semantics. Shared freshness/replacement tokens and exact observation identity remain communication work; nonleader roles are never allocated. Altar scoring, route construction, ward placement, and shopping remain their own strategies.

