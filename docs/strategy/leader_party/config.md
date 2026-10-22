# Configuration reference

Status: documentation only. These variables must become one implementation config; do not scatter copies through bot code. Values are starting proposals for trial and error, not measured optima. Changing a value must not change the meaning of a state. The shop, navigation, altar, and ward settings below are **temporary MVP placeholders to replace/tune after initial matches**.

## Leadership and party

| Variable | Initial value | Exact use |
| --- | --- | --- |
| LEADER_PREFERENCE | Heart of Ruin, Ren, Marcella | Ordered preferred champion types. Ignore absent types. Append other bodies by descending maximum **starting** Health, then stable roster slot. |
| LEADER_MIN_HEALTH_FRACTION | 0.50 | A new/current leader must have Health fraction **strictly greater** than this. At or below it, relinquish leadership. Shields do not count. |
| LEADER_RECLAIM_DELAY_ROUNDS | 1 | After relinquishing, do not offer yourself again until this many full rounds have elapsed. Prevent immediate re-election on the same turn. |
| PARTY_RADIUS_STEPS | 4 | A living visible ally belongs to the moving party when within this many reachable movement steps of the leader and in LEAD_TEAM/FOLLOW_LEADER. Committed detached collectors do not count. |
| FOLLOW_DISTANCE_TILES | 2 | Aim for a free safe tile within this Chebyshev distance of the visible leader. Do not occupy its tile. Use temporary pathfinding baseline for terrain/occupancy. |
| SIDE_NODE_DISTANCE | 2 | Small camp must pass within this Chebyshev distance of the leader. |
| SIDE_PASS_MIN_PARTY_SIZE | 2 | Skip a small node only when the current moving party size is **greater than** this. Thus at least this many bodies remain after detaching one. |
| SIDE_PASS_MAX_CONSECUTIVE | 1 | Number of consecutive eligible small nodes the moving party may skip, each with one different runner. Zero means stop at the first. The next node after the cap is a full-party stop. |
| RUNNER_PREFERENCE | Vendetta, Vesper Vale, Marcella | Configured ordered runner pool. Append other nonleader bodies by stable roster slot. The leader is excluded. |
| RUNNER_MIN_HEALTH_FRACTION | 0.60 | Require Health fraction >= this before detaching. |
| RUNNER_MAX_ASSIGNMENT_STEPS | 3 | Runner must already be within this reachable distance of a legal camp approach tile. |
| RUNNER_REJOIN_RADIUS_STEPS | 4 | A detached runner is considered back with the party inside this distance, when visible and available for following. |
| PARTY_REJOIN_WAIT_ROUNDS | 6 | After a full-party stop completes, hold nearby safely for missing surviving runners for at most this many rounds. Danger may interrupt; after the deadline, resume travel and let them rejoin later. |
| CAMP_COLLECTOR_PREFERENCE_GEMS | Marcella, Vesper Vale, Vendetta | Prefer first eligible present body for a gem-bearing group. Append other bodies by stable slot. |
| CAMP_COLLECTOR_PREFERENCE_GOLD | Vesper Vale, Vendetta, Marcella | Same for a gold-only group. Existing living collector wins over this order. |
| CAMP_GUARD_DISTANCE_TILES | 2 | Guards aim within this distance of the reward region, outside its spawn tiles. Terrain may require a different reachable guard tile. |
| BANK_GUARD_DISTANCE_TILES | 2 | Guard the saved altar/carrier within this distance when a legal tile exists. |
| BANK_REACQUIRE_TURNS | 2 | Own turns spent trying to regain a hidden carrier before releasing an unconfirmed attempt. This never proves the carrier died or banked. |

Maximum starting Health is a fixed draft-time tie-breaker, so buying Health does not repeatedly change the hierarchy. Explicit precedence is a strategic choice: front-line durability and a free role matter more than current item totals. Full roster orders are computed once and stored in draft/static planning data.

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
| LEADER_REPORT_STALE_ROUNDS | 2 | Maximum age for a leader location/command. Expired commands cannot start camp work. |
| LEADER_ELIGIBILITY_STALE_ROUNDS | 1 | Ignore an eligibility offer older than this. The final communication protocol must make this check possible. |

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
| FUEL_CHUNK_QUERY_MIN | 350000 | Provisional Python fuel above critical reserve before expensive chunk visibility queries. Native route calls also require FUEL_PATH_MIN. |

## Temporary MVP shop, navigation, altar, and ward settings

These values let the placeholder documents provide concrete defaults. They do not claim measured fuel safety or optimal builds. Item prices, placement radii, and combination rules should be read from SDK metadata where available.

| Variable | Initial value | Meaning |
| --- | --- | --- |
| SHOP_BUILDS | Table in strategies/shop.md | Fixed per-champion two-phase builds plus repeating batches; encode that table once in the implementation config. |
| SHOP_BATCH_SHARDS | 5 | Purchased shards per phase; compare against SDK combine count when reconstructing inventory. |
| SHOP_MAX_SHARDS_PER_TURN | 40 | Bound successful single-shard purchases; retain unfinished phase. |
| SHOP_BUY_ALTAR_LOCK | true | Buy one lock with leftover gold after planned shard purchases when legal. |
| NAVIGATION_BACKEND | NATIVE_MVP | Native DistanceField; temporary override of chunking's resumable hard-node-cap contract. |
| PATH_MAX_NATIVE_FIELDS_PER_TURN | 3 | Combined full/compute_to calls for all distance, movement, and chunk-inspection helpers in one own turn. |
| PATH_ENEMY_MARGIN | 1 | Extra tiles beyond visible enemy basic range in TRAVEL/ESCAPE risk masks. CAPTURE combat follows its own Danger guard. |
| PATH_HIDDEN_BLOCK_RETRIES | 1 | Maximum different-step retry after a failed move newly reveals an obstruction. |
| PATH_STALL_TURNS | 3 | Eligible movement turns without successful task movement before rebuilding/reporting obstruction. |
| FUEL_PATH_MIN | 600000 | Provisional Python fuel above critical reserve before starting a native distance-field computation. |
| ALTAR_RECHECK_ROUNDS | 3 | Reassess scores this often during preparation, or sooner for a relevant obstruction/change. |
| ALTAR_SWITCH_MARGIN | 3 | Switch only if new_score + margin < current_score, unless current route is unusable. |
| ALTAR_BLOCK_RETRY_ROUNDS | 2 | Short exclusion after a completed approach search fails under current occupancy/risk. |
| ALTAR_LOCK_HIT_COST | 1 | Score cost per observed remaining basic hit on an enemy lock; fresh lock has five under current rules. |
| ALTAR_UNKNOWN_LOCK_COST | 2 | Small penalty when altar lock status is not visible. |
| ALTAR_ENEMY_COST | 6 | Score penalty per visible enemy champion within danger radius of altar. |
| ALTAR_CAMP_COST | 3 | Penalty per visible awake camp threatening a legal adjacent approach. |
| ALTAR_DANGER_RADIUS | 6 | Chebyshev radius for the altar enemy-count penalty. |
| BANK_PLACE_OWN_LOCK | true | Carrier/assigned escort may use one carried lock at its current altar before channeling. |
| WARD_RELEVANCE_RADIUS | 6 | Score ward coverage in this Chebyshev radius around objective/waypoint. |
| WARD_MAX_CANDIDATES | 4 | Maximum candidate Ward.visible_tiles_from queries per ward call. Old-ward lookup is one additional query. |
| WARD_MIN_GAIN | 8 | Required net increase in relevant persistent ward coverage, in tiles. |
| WARD_RELOCATE_DISTANCE | 6 | Chebyshev movement from last successful ward position permitting replacement, unless task changed. |
| FUEL_WARD_MIN | 350000 | Provisional Python fuel above critical reserve before optional ward scoring. |

## Execution and protocol limits

| Variable | Value | Meaning |
| --- | --- | --- |
| RETURN_DISPATCH_MAX_PER_TURN | 1 | Run the return decision at most once per own turn. Reaching it again ends discretionary action for that turn. |
| MAX_STATE_CHANGES_PER_TURN | 4 | Bound action-triggered state changes. After reaching the cap, publish state/status and yield; next turn starts with death/channel checks. |
| FUEL_CRITICAL_RESERVE | 150000 | Provisional Python reserve for mandatory communication/yield. Must be measured in the actual MVP runtime. |
| FUEL_ENEMY_REPORT_MIN | 400000 | Only compute optional enemy concentrations above this fuel level plus critical reserve. |
| FUEL_DEBUG_MIN | 600000 | Only draw debug labels/colours above this level plus critical reserve. |
| CHUNK_ID_BITS | 6 | Fixed six-bit location fields. Selected partition needs at most 49 chunks, IDs 0–48; 63 is the invalid sentinel. |
| SHARED_ROSTER_SLOTS | 6 | Fixed slots, including separate Cassi and Issac bodies. |
| STATE_COLOURS | See state overview | Stable RGB hex values used by the diagram and eventual debug drawing. |

Fuel defaults are provisional for the configured Python bot (rules describe 2,500,000 fuel per ordinary Python turn); other languages need different values. A threshold is an admission check, not an enforced cap inside a native call. Measure usage before raising work limits. Memory widths, enum values, and sentinels are protocol constants; thresholds, priorities, ranges, and budgets are configuration variables. Victory score and channel/capture timing come from the game rules.

