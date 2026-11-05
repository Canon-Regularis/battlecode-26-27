# car01: defer a camp occupancy plan after rejected movement

Base: `0a32c23b1432433d29164d642077bbe9fd01badf`, exact parent `bots/pi_camp-ally-occupancy-01/`. Candidate: `bots/pi_camp-ally-retry-01/`. Changes are uncommitted for the existing Pi bridge. No games, release builds, portal uploads or ranked changes were performed.

## Hypothesis and production delta

A rejected ordinary movement invalidates the occupancy evidence private to that navigation attempt. Returning `deferred` for any non-null uncertain pointer lets the next normal camp attempt prepare a fresh plan. This intentionally costs one deferred attempt instead of recursively using an obsolete overlay. An empty-but-present overlay identifies the same decision boundary.

The only production change is in `src/navigation.cpp::move_to`, immediately after `invalidate_observations();++mem.blocked;`:

```cpp
// A rejected move invalidates this attempt's private occupancy plan.
if(uncertain)return RouteStatus::deferred;
```

All 27 source files were compared with Git objects at the exact base. Only navigation.cpp differs; its full contents are asserted by the runner to equal the parent's contents plus these two lines. The successful path, helper error handling, invalidations, blocked counter, canonical blockers, field search, admission/reserves, progress accounting and null-pointer recursion remain unchanged. No forced end-turn is introduced: actual camp_action still observes, refreshes and can fight afterward. No additional behavioral correction was bundled. SOURCE_SHA256SUMS was regenerated; only navigation.cpp's checksum changes.

All other production files, including ally_occupancy.h, observations, caller integration, objectives, combat, economy, draft, config, protocol and task90/stall8, are byte-identical to the parent. Other bots, SDK, tools and settings were not edited.

Reviewed the bridge instructions; strategy overview, state machine, navigation, routing and historical meta strategy; SDK compatibility notes, game-rule movement/vision/fuel sections; and actual C++ movement, restrictions, visible champion enumeration and distance-field declarations.

## Actual-source fixture and results

`tests/run_occupancy.py` compiles four native executables: exact-parent integration control, candidate occupancy module, candidate integration, and unchanged streaming adapter. Temporary generated headers and executables stay under a temporary directory. Compilation uses `g++ -std=c++20 -O2 -Wall -Wextra -Werror`.

Extraction is literal, with no rewritten policy model. Start marker is inclusive and end marker exclusive:

| Source | Start | End | Adaptation |
| --- | --- | --- | --- |
| observations.cpp | `occupancy::Attempt prepare_camp_occupancy(` | newline `namespace {Snapshot` | None |
| observations.cpp | `void invalidate_observations()` | newline `bool move_checked(` | None |
| observations.cpp | `bool move_checked(` | newline `unsigned observation_version()` | None |
| observations.cpp | `const Snapshot& observe()` | newline `}` newline `}` | Append the function's closing brace |
| navigation.h | `enum class RouteStatus` | newline `}` | Includes real TurnBudget |
| navigation.cpp | `RouteStatus move_to(` | newline `bool retreat(` | None |
| bot.cpp | `void Bot::camp_action(` | newline `void Bot::play_turn(` | None |

The parent control substitutes only move_to's literal body obtained via `git show` from the exact base and parent path. A compile-time flag selects expected assertions, not policy. The cache header and Memory/Config/task_expired are actual candidate production code, unchanged from parent.

The new coverage has **13 scenarios per integration executable, 26 executions total**: three pointer/plan boundaries, one actual-caller continuation, two actual-caller no-deletion cases, one actual-caller pending-version case, four helper cases, and two successful overlay cases. Both executables also run the inherited integration scenarios.

- Identity2 is observed at X=(2,1) on round20, then hidden on round21 after actually moving to Y=(2,0). Actor=(1,1), goal=(3,1). The fixture opens only those four tiles. The first detour targets Y, returns false, reveals Y and preserves movement allowance. X remains hidden throughout. Field-input masks are recorded, not inferred from outcomes.
- Parent populated-overlay attempt: two fields, zero successful moves, `no_route_now`. Second field includes both stale X and current Y. Candidate: one field, zero successful moves, `deferred`, one blocked increment, no distance/progress credit.
- Actual caller continuation publishes identity2-at-Y through real observe after deferral. Next round's normal preparation has no uncertain X, canonical Y remains blocked, and movement through X succeeds with one additional field and actual progress credit. Same-round publication does not need visible-clear X evidence.
- Null-pointer ordinary navigation keeps its original two-field retry and moves through X on the same scripted rejection. Empty-but-present overlay defers after one field in the candidate; parent retries and moves. Populated and empty successful overlays both keep one-field movement and unchanged distance accounting.
- Restricted movement and expected bad-destination failure run through real camp_action/move_checked. Candidate defers after one field; still-hidden X survives next-round normal preparation, demonstrating no failure-deletion. Progress/distance remain unchanged. Parent retains its original three-field/wait behavior for these scripts.
- Direct real-helper checks cover unavailable/restricted movement without SDK movement or invalidation, expected bad destination with invalidation, and unexpected error propagation without the helper's post-call invalidation.
- Actual caller schedules failed-version X after genuine no-route; fresher same-round observation of identity2-at-Y supersedes that pending token. Hiding Y next round retains Y rather than deleting its fresh version. Belief changes do not credit progress.

Inherited checks also passed: stale round/revision during collection/field, no stale movement, current blockers, no-route versus empty goals/overlay-empty versus deferred, exact-version/scope feedback protection, alive-query bounds, next-round relaxation, same-round retention, task90/stall8, necessary backtracking, at-goal/wait, and reward/absent/respawn scope paths. The unchanged occupancy unit suite ran once; streaming adapter smoke ran once and checked its three emitted mask lines. Native compatibility runner passed **84** dominant metadata/selection checks, protocol/state scenarios, **19** production fight/reference scenarios, and committed refresh/progress contracts. Those inherited runners do not report numeric totals for every assertion; no aggregate assertion count is claimed.

Host substitutions remain explicit: 8x8 uint64 bitboards, eight-neighbor walking BFS instead of the SDK native field, scripted visibility/roster/life/action/error values, constant fuel=100000, no dash availability, simplified camp/world/fight/facts adapters. Actual camp_action executes; its downstream fight and world refresh are stubs. This validates route/caller bookkeeping, not real combat or health refresh. Hidden rejection reveals only Y, independent of official shadowcasting. The BFS explores all reachable tiles rather than the engine's destination-limited expansion. This is a self-contained reachable-transition script, not official-visibility geometry or a release replay.

The added transition initially exposed a pre-existing fixture defect: its invalidation stub cleared unused cache_valid instead of valid_cache. The fixture now extracts real invalidate_observations and move_checked, removing that substitution. Initial failing development runs are not counted as passes; final commands below all passed.

## Commands run on Pi

Host: aarch64, Ubuntu GCC 13.3.0. From repository root:

```sh
python3 bots/pi_camp-ally-retry-01/tests/run_occupancy.py
python3 bots/pi_camp-ally-retry-01/tests/run_native.py
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_camp-ally-retry-01/src/*.cpp
```

All passed, including SDK syntax checking of all production translation units. The inherited cmath include and warning option accommodate host/SDK compilation; no SDK bytes changed. The Windows-specific planner translation runner was not run. Final checksum verification and exact-parent production/module/adapter comparisons also passed.

## PC handoff and gaps

`car01-protocol.json` records identity/provenance and unchanged geometry-input hashes separately. It does not replace the frozen `cao01-protocol.json`. The original JSON and PC-local reproducer are absent from this checkout; neither was reconstructed. The full original protocol, including exact game conditions, context exclusions and rejection definitions, must remain the authoritative PC input.

Unchanged SHA-256 inputs for possible reuse of the 17 already-passed PC official-visibility controls:

- `src/ally_occupancy.h`: `2b9b3bb55e176daafa7a96d78089d8894584276fe01f234f3a58ac0e5668aaa9`
- `tests/occupancy_adapter.cpp`: `514c8c32fd6df1decb05088e4fb1a940b530972a4dff57fcfa6bb562f0c58b4e`

These bytes were checked against the exact base. The 17 controls were not rerun here; reuse still requires PC hash verification. PC must review the exact production delta and rerun actual-source integration including failed-retry on the returned exact candidate regardless of geometry reuse.

car01 replaces cao01 before any release game; cao01 remains unplayed. After review, use only the frozen four Vault games (champion/C02, both sides), never standard80 first. Preserve every original gate: zero VM faults and caught SDK errors; at least 3/4 wins; champion A first central capture <200 and corresponding first positive recipient bank <250; B capture <=215 and bank <=238; A central damage through100 >1080; Marcella A >65 and B >=300; actual continued useful work; original through100 short-cycle rejection (period2–12, two repetitions, at least8 successful moves, with original context exclusions). This paragraph is a reminder, not a substitute for the full original definitions.

Any failure stops expansion. Passing four games requires a separately frozen regression panel. No duplicate baseline games, online challenge, upload, ranked replacement, automatic composition or fresh-confirmation claim follows. No WASM link, engine fuel/VM execution, official geometry or strength evaluation was done on Pi. Native passes prove neither engine fuel cost nor playing strength.
