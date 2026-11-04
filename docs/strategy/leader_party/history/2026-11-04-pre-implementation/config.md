# Configuration reference

Status: documentation only. These variables must become one implementation config; do not scatter copies through bot code. Values are starting proposals for trial and error, not measured optima. Changing a value must not change the meaning of a state. The shop, navigation, altar, and ward settings below are **temporary MVP placeholders to replace/tune after initial matches**.

## Leadership and party

| Variable | Initial value | Exact use |
| --- | --- | --- |
| LEADER_PREFERENCE | Heart of Ruin, Ren, Marcella | Ordered preferred champion types. Ignore absent types. Append other bodies by descending maximum **starting** Health, then stable body number. |
| LEADER_MIN_HEALTH_FRACTION | 0.50 | At or below this Health fraction the current leader writes 111. The next leader auto-selects using configured precedence. Shields do not count. |
| PARTY_RADIUS_STEPS | 4 | A living visible ally belongs to the moving party when within this many reachable movement steps of the leader and in LEAD_TEAM/FOLLOW_LEADER. This is a local formation measure, never a role allocation; do not query hidden allied bot states. |
| FOLLOW_DISTANCE_TILES | 2 | Aim for a free safe tile within this Chebyshev distance of the visible leader. Do not occupy its tile. Use temporary pathfinding baseline for terrain/occupancy. |
| CAMP_GUARD_DISTANCE_TILES | 2 | Guards aim within this distance of the reward region, outside its spawn tiles. Terrain may require a different reachable guard tile. |
| BANK_GUARD_DISTANCE_TILES | 2 | Guard the saved altar/carrier within this distance when a legal tile exists. |
| PROTECT_PATROL_RADIUS_TILES | 1 | Maximum Chebyshev distance for quiet patrols around the protected collector/reward region or exact altar, within the existing guard limit. Collectors and channeling carriers remain stationary. If no legal patrol step exists, hold nearby. |
| BANK_REACQUIRE_TURNS | 2 | Own turns spent trying to regain a hidden carrier before releasing an unconfirmed attempt. This never proves the carrier died or banked. |

Maximum starting Health is a fixed draft-time tie-breaker, so buying Health does not repeatedly change the hierarchy. Explicit precedence is a strategic choice: the existing leadership order is retained rather than sorting by current item totals. Only leadership precedence is computed once and stored in draft/static planning data. Nonleader roles have no allocation or preference order.

## State conditions and rallies

| Variable | Initial value | Exact use |
| --- | --- | --- |
| BANK_GEM_THRESHOLD | 20 | Start ordinary banking at bag >= value. A bag that wins immediately may bank sooner. |
| RECALL_ENTER_FRACTION | 0.35 | Low Health at fraction <= value. |
| RECALL_EXIT_FRACTION | 0.55 | An unstarted recall may be abandoned at fraction >= value. |
| LOCAL_THREAT_RANGE | 6 | Enemy-champion proximity threshold for local combat danger; see the state reference. |
| LOCAL_SUPPORT_RANGE | 4 | Range for allies who can support the current fight. |
| FLEE_CLEAR_TURNS | 2 | Consecutive own turns without a visible enemy champion required for the contact-loss escape exit. |
| ATTACK_RESPONSE_STEPS | 6 | Maximum entry path to a useful attack participation position. |
| BANK_RESPONSE_STEPS | 8 | Maximum entry path to a useful altar guard position. |
| RALLY_STALE_ROUNDS | 3 | A request is live at refresh age <= value; stale above it. |
| ATTACK_MAX_ROUNDS | 12 | End at age >= value, even during combat. Refresh must not restart this clock. |
| ATTACK_LOST_CONTACT_TURNS | 2 | Owner cancels after this many consecutive own turns without target/contact. |
| ATTACK_RETRY_ROUNDS | 3 | Pause before recreating an expired request for the same contact, unless a genuinely new contact episode occurs. |
| ENEMY_REPORT_STALE_ROUNDS | 3 | Independent lifetime of an enemy observation. |

Recall safety is stricter than the numeric combat danger check: **any currently visible enemy champion** blocks starting/continuing recall, regardless of numbers. An awake camp blocks recall only if it can hit now. That is why LOCAL_THREAT_RANGE does not define recall safety.

## Chunk mapping and inspection

The algorithm and exact counting rules are in [strategies/chunking.md](strategies/chunking.md). Mapping settings are fixed for the whole team/match; search limits are starting tuning values.

| Variable | Value | Meaning |
| --- | ---: | --- |
| MAP_MIN_SIDE | 30 | Documented production minimum per dimension; reject smaller production maps. |
| MAP_MAX_SIDE | 100 | Documented production maximum per dimension. |
| CHAMPION_VISION_RADIUS | 8 | Rule-derived champion radius, including diagonals; visibility still uses engine masks. |
| CHUNK_MAX_SIDE | 15 | Balanced chunks at most 15×15. Changing this requires revalidating the bit budget and centre guarantee. |
| CHUNK_INVALID_ID | 63 | Six-bit absent/unknown sentinel. |
| CHUNK_INSPECTION_HALO | 8 | Derived from champion radius; expand the candidate rectangle by this many tiles, clipped to map. |
| CHUNK_SEARCH_MAX_STEPS | 12 | Successful Chebyshev movement distance after local inspection begins. |
| CHUNK_SEARCH_MAX_TURNS | 8 | Stop local search at this many own turns since local inspection began. |
| CHUNK_SEARCH_MAX_VIEWPOINTS | 4 | Distinct inspection positions visited; observe before returning exhausted. |
| CHUNK_APPROACH_STALL_TURNS | 3 | Consecutive approach turns without movement or route-planner progress before BLOCKED. |
| CHUNK_CANDIDATE_SCAN_PER_TURN | 128 | Raw candidate tiles processed per turn, persisting enumeration state. |
| CHUNK_VIEW_QUERIES_PER_TURN | 4 | Hypothetical champion-vision queries per turn. |
| CHUNK_VIEW_CACHE_ENTRIES | 32 | Maximum cached hypothetical masks per body; evict least recently used, ties by (y,x). |
| CHUNK_PATH_QUERIES_PER_TURN | 4 | Candidate route queries per turn. |
| CHUNK_PATH_NODE_BUDGET | 128 | Future resumable-pathfinder target. **Inactive under NATIVE_MVP**: the SDK cannot enforce a hard expansion cap. Use the global native-field quota instead. |
| CHUNK_RETRY_ROUNDS | 3 | Delay before retrying an unchanged blocked/exhausted request. Material target/location/obstruction changes may retry sooner. |
| FUEL_CHUNK_QUERY_MIN | 45000 | C++ fuel admission threshold before native path/visibility work. Retain critical reserve below this point. |

## Temporary MVP shop, navigation, altar, and ward settings

These values let the placeholder documents provide concrete defaults. They do not claim measured fuel safety or optimal builds. Item prices, placement radii, and combination rules should be read from SDK metadata where available.

| Variable | Initial value | Meaning |
| --- | --- | --- |
| SHOP_BUILDS | Table in strategies/shop.md | Fixed per-champion two-phase builds plus repeating batches; encode that table once in the implementation config. |
| SHOP_BATCH_SHARDS | 5 | Purchased shards per phase; compare against SDK combine count when reconstructing inventory. |
| SHOP_MAX_SHARDS_PER_TURN | 40 | Bound successful single-shard purchases; retain unfinished phase. |
| SHOP_BUY_ALTAR_LOCK | true | Buy one lock with leftover gold after planned shard purchases when legal. |
| NAVIGATION_BACKEND | NATIVE_MVP | Native DistanceField; temporary override of chunking's resumable hard-node-cap contract. |
| PATH_MAX_NATIVE_FIELDS_PER_TURN | 3 | Combined full/compute_to calls for distance, movement, chunk inspection, and initial enemy-approach ward field construction in one own turn. Reusing the static ward-direction field consumes no new call. |
| PATH_ENEMY_MARGIN | 1 | Extra tiles beyond visible enemy basic range in TRAVEL/ESCAPE risk masks. CAPTURE combat follows its own Danger guard. |
| PATH_HIDDEN_BLOCK_RETRIES | 1 | Maximum different-step retry after a failed move newly reveals an obstruction. |
| PATH_STALL_TURNS | 3 | Eligible movement turns without successful task movement before rebuilding/reporting obstruction. |
| FUEL_PATH_MIN | 45000 | C++ fuel admission threshold before a native distance-field computation; the C++ turn budget is 100,000. |
| ALTAR_RECHECK_ROUNDS | 3 | Reassess scores this often during preparation, or sooner for a relevant obstruction/change. |
| ALTAR_SWITCH_MARGIN | 3 | Switch only if new_score + margin < current_score, unless current route is unusable. |
| ALTAR_BLOCK_RETRY_ROUNDS | 2 | Short exclusion after a completed approach search fails under current occupancy/risk. |
| ALTAR_LOCK_HIT_COST | 1 | Score cost per observed remaining basic hit on an enemy lock; fresh lock has five under current rules. |
| ALTAR_UNKNOWN_LOCK_COST | 2 | Small penalty when altar lock status is not visible. |
| ALTAR_ENEMY_COST | 6 | Score penalty per visible enemy champion within danger radius of altar. |
| ALTAR_CAMP_COST | 3 | Penalty per visible awake camp threatening a legal adjacent approach. |
| ALTAR_DANGER_RADIUS | 6 | Chebyshev radius for the altar enemy-count penalty. |
| BANK_PLACE_OWN_LOCK | true | Carrier or an observing local protector may use one carried lock at its current altar before channeling. |
| WARD_RELEVANCE_RADIUS | 6 | Compare coverage near the objective/waypoint only to break equal forward-placement choices. |
| WARD_MAX_CANDIDATES | 4 | Maximum candidate Ward.visible_tiles_from queries for coverage tie-breaks; geometrically rank the at most 25 radius-two placement tiles first. |
| WARD_RELOCATE_DISTANCE | 6 | Chebyshev movement from last successful ward position permitting replacement, unless task changed. |
| FUEL_WARD_MIN | 35000 | C++ fuel admission threshold before optional ward scoring. |

## Execution and protocol limits

| Variable | Value | Meaning |
| --- | --- | --- |
| RETURN_DISPATCH_MAX_PER_TURN | 1 | Run the return decision at most once per own turn. Reaching it again ends discretionary action for that turn. |
| MAX_STATE_CHANGES_PER_TURN | 4 | Bound action-triggered state changes. After reaching the cap, publish state/status and yield; next turn starts with death/channel checks. |
| FUEL_CRITICAL_RESERVE | 10000 | C++ reserve for mandatory coordination and a clean yield. |
| FUEL_ENEMY_REPORT_MIN | 25000 | Only compute optional enemy concentrations above this fuel level. |
| FUEL_DEBUG_MIN | 35000 | Only draw optional labels/colours above this fuel level. |
| CHUNK_ID_BITS | 6 | Fixed six-bit chunk fields from the committed communication layout. Selected partition needs at most 49 chunks, IDs 0–48; 63 is the invalid sentinel. |
| SHARED_ROSTER_SLOTS | 6 | Body numbering only, including separate Cassi and Issac bodies; not role assignments. |
| STATE_COLOURS | See state overview | Stable RGB hex values used by the diagram and eventual debug drawing. |

The implementation target is C++ (100,000 fuel per ordinary turn; the first champion turn gets a larger budget). Thresholds are admission checks, not enforced caps inside native distance-field calls. Preserve the critical reserve and validate on full maps before raising query limits. Memory widths, enum values, and sentinels are protocol constants; thresholds, priorities, ranges, and budgets are configuration variables. Victory score and channel/capture timing come from the game rules.


## User decisions recorded on 22 October 2026

Only state_machine.md defines state transitions. Leadership is the sole allocated role. Runner, collector, and escort allocation settings were removed. No implicit runner limits or reward-ownership preferences survive the deleted team plan.

Camp routing uses efficient travel distance and canonical camp-ID ties, without reward weighting; account for known respawn at arrival. See strategies/route_planning.md. Exploration behavior/thresholds, objective-switch cadence, precise ATTACK confidence thresholds, shield observation window, heal policy, and banking queue timing remain unresolved. Do not turn proposed values into accepted config silently.

Dashes are enabled for normal travel and RUN_AWAY when legal; the previous walking-only integration limit is superseded. Strong attacks, lowest-Health reachable targets, area-hit maximization, and ranged attack priority are specified in combat.md; their unresolved precedence is explicit there.

Leadership correction: no eligibility bits, eligibility/report-age slots, handover cooldown, or automatic leadership loss on entering a different state. Shared bits 29–40 are the original safety summaries; bits 41–63 are reserved.
