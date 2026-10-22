# Draft-only squad loop planner

Gameplay is intentionally a no-op. During draft, this bot searches for one loop
for the entire squad and reports its five best distinct camp-set/altar combinations.

## Code guide

Start with `src/draft_planner.py:DraftPlanner.build()`. Its pipeline is:

```text
choose squad -> collect camps/altars -> prepare distances and risks
             -> search loops -> publish report -> save/draw plan
```

Each source file has one main job:

| File | Responsibility |
| --- | --- |
| `src/main.py` | Dispatch draft turns and drawing-only champion turns. |
| `src/settings.py` | All tuning knobs: strategy, squad, search, fuel, combat approximations, colors. |
| `src/draft.py` | Champion selection and the draft entry point: save plans, draw, and make picks. |
| `src/draft_planner.py` | `DraftPlanner` owns the roster/config and connects SDK map preparation, search, and reports. |
| `src/combat.py` | Estimate clearing time, healing, and survivability; never issue combat actions. |
| `src/navigation.py` | Native BFS and spawn-risk distances; never move units. |
| `src/planner.py` | `LoopPlanner` owns SDK-free search inputs and performs scoring and bounded beam search. |
| `src/plan_memory.py` | Encode/decode compact `DraftPlan` and `RoutePlan` objects. |
| `src/visualization.py` | Draw all group member tiles, arrows, and cycling loop overlays. |
| `src/bot.py` | Unimplemented gameplay placeholder. |
| `inspect_loops.py` | Host-side CLI: run match, read replay reports, print results, optionally open viewer. |

The important data types make index/coordinate distinctions explicit:

- `CampGroupInfo`: an entire camp group's rewards, anchor, and service/respawn times.
- `CandidateCamp` / `CandidateAltar`: named map-preparation records, not positional tuples.
- `PlanningData`: aligned distance matrices, candidate lists, and positional risks.
- `DraftMapContext`: squad designs, camp groups, blocked terrain, and spawn-distance maps for one build.
- `ScoredLoop`: **indices** into those candidate lists, plus its `LoopEvaluation`.
- `RoutePlan`: actual **coordinates** used for saving and drawing.
- `DraftPlan`: primary route, squad roster, and alternative drawing routes.

### The two planner classes

During draft, construct the SDK-facing planner once:

```python
from draft_planner import DraftPlanner

planner = DraftPlanner(roster, settings.DEFAULT_SEARCH_CONFIG)
fallback = planner.fallback_plan()
plan = planner.build()
```

`DraftPlanner` stores the roster and configuration. Construction makes **no engine
queries**. `build()` reads a fresh `DraftMapContext`, then calls its internal
`_collect_camps()`, `_collect_altars()`, `_prepare_data()`, `_search()`,
`_publish_report()`, and `_create_plan()` stages. There are no partially initialized
map fields on the object. `play()` remains responsible for submitting the fallback
and final plan, drawing, and picking a champion.

The search receives only the prepared arrays, not SDK objects:

```python
search = LoopPlanner(
    camps=data.camps,
    distances=data.distances,
    altar_distances=data.altar_distances,
    spawn_distances=data.spawn_distances,
    risk=data.risk,
    config=config,
)

loops = search.find_loops()
# To score a particular route: search.evaluate_loop(route, altar_index)
# To return only the winner: search.find_best_loop()
```

This replaces passing the same six or seven arguments into every evaluation.
`LoopPlanner` keeps inputs/configuration on `self`; search frontiers, finalists,
and budget counters remain local to each `find_loops()` call. Reusing an instance
doesn't carry over an exhausted budget or old search results. Input tables are
read-only by convention and are not copied or mutated by search.

Small stateless operations such as `positional_risk()`, `camp_insertions()`, and
coordinate conversion remain functions. Drawing, memory encoding, scoring weights,
risk tolerance (`0.2`), and the beam-search ordering are unchanged.

`plan_memory.py` replaces the old `protocol.py` name. Its SQL2 byte format is
unchanged and still reads SQL1 and zero-padded engine buffers. Reports likewise
keep their existing fields and `SQUAD_LOOPS_DATA` marker. The bot prints a Python
literal that the host reads with `ast.literal_eval`; this intentionally avoids
importing a heavyweight JSON encoder into the fuel-metered game process.

## See the loops

From the repository root:

```sh
uv run python bots/economy-bot/inspect_loops.py --map packs
uv run python bots/economy-bot/inspect_loops.py --map packs --view
uv run python bots/economy-bot/inspect_loops.py --map monolith --side both
uv run python bots/economy-bot/inspect_loops.py --map packs --fuel 10000000
```

The helper runs a 40-round drawing-only self-match, reads the draft reports from the replay,
and prints the ranked camp coordinates and timing estimates. Use `--json` for
machine-readable results. Replays are retained under `replays/loop-inspection/`.
The helper launches the runner and viewer through `uv run cambc` as well.
Use `--view` to open the replay. Enable debug drawings for a champion on the team
you want to inspect. Each champion redraws the overlay every turn, cycling through
one ranked loop every eight rounds so overlapping routes remain readable:

- #1 green: rounds 1–8
- #2 cyan: rounds 9–16
- #3 orange: rounds 17–24
- #4 purple: rounds 25–32
- #5 pink: rounds 33–40

Colored dots mark **every member tile** of each selected camp group, including
gold and gem clusters in mixed groups. A white dot marks the altar, and arrows
connect the group anchors to show the visit order.
These are waypoint links, **not literal straight-line movement paths**. All loops
are also drawn during draft, with the best on top. If fewer than five loops are
found, playback cycles through those available. Drawing does not move or fight.
`--fuel` allows deeper local inspection, but an increased budget does not reflect
the competition's normal draft limit. Without it, the normal runner budget is used.

## Objective and limits

For each loop:

```text
active = terrain travel + team fighting/capture/repositioning + tribute
period = max(active, max(camp respawn + camp service time))
first_deposit = active - altar_to_first_camp + spawn_to_first_camp
base_score = (gems + 0.02 * gold) / (period + 0.15 * first_deposit)
location_risk = distance_to_our_spawn / (distance_to_our_spawn + distance_to_enemy_spawn)
risk_multiplier = 1 - (1 - RISK_TOLERANCE) * loop_risk
score = base_score * risk_multiplier
```

`RISK_TOLERANCE = 0.2` is defined in `src/settings.py`. It ranges from **0**
(strongest positional penalty) to **1** (ignore positional risk). At 0.2,
a loop with risk 0.5 retains 60% of its original score. The text and JSON reports
include tolerance, positional risk, multiplier, base score, and final score.

Spawn distances use terrain BFS, not straight-line distance. Enemy spawn tiles
are forbidden to our units, so their field starts on legal adjacent approach
tiles and includes the final one-step distance to spawn. A region unreachable
from enemy spawn has zero positional risk. Camp risk averages all member tiles;
altar risk averages its reachable, legal tribute tiles.

Loop risk is averaged over its full repeating period, weighted by turns spent
traveling, clearing/capturing, tributing, and waiting for respawns. Travel uses
the average of its endpoint risks as a draft-fuel-saving approximation, not
tile-by-tile path exposure. Respawn waiting is assumed to happen at the altar.
The initial spawn-to-loop trip is not part of this repeating-loop risk average.
Risk also influences which camps enter the candidate shortlist. This measures
positional exposure, **not an actual probability of an ambush or death**.

Also reports **unadjusted gems/turn = gems / period**. Rewards are counted once
for the squad, not once per champion. A camp group must be completely cleared,
its capture time is not divided by squad size, and its respawn timer starts
after capture. Tribute assumes a conservative single bag; actual parallel
tributes can be quicker when rewards are distributed.

Terrain distances use native eight-direction BFS around walls, holes, altars,
and enemy spawn. Camps use a canonical spawn coordinate as their identifier and
distance anchor. Fighting estimates use SDK champion/camp designs, discounted
combined DPS, limited splash/AoE benefit, and approximate healing. An incoming
damage check excludes individually dangerous camps.

This is **bounded heuristic search**, not a global optimality guarantee:

- `src/settings.py`: `PREFERRED_PICKS` sets the assumed squad and actual draft picks;
  defaults to Varg, Willow, Vendetta, Marcella, then Tavi as team size permits.
- `CANDIDATE_LIMIT = 24`: spawn-accessible, high-value candidate groups.
- `ALTAR_LIMIT = 4`: nearest reachable altars to spawn.
- Distance precomputation can reduce these counts on large maps to leave fuel
  for searching and reporting. It estimates the next native BFS's cost from the
  previous one before starting it, since that call cannot be interrupted by the
  Python search-budget callback. `PRECOMPUTE_RESERVE = 11_500_000` keeps the
  refactor's faster distance lookups from spending all their savings on a wider
  matrix and leaving too little fuel to explore multi-camp routes.
- `src/settings.py`: `SearchConfig` controls beam width, maximum route length,
  expansion budget, gold weight, opening-time penalty, and risk tolerance.
- Beam search inserts camps at every position, explores altars round-robin,
  keeps distinct camp sets, and saves finalists from every route length.

The model does not simulate enemy interference, crowding, exact combat turns,
ability cooldown carry-over between camps, or cumulative squad health over a
whole loop. Static paths may cross monster tiles that would require detours
while occupied. Treat the output as candidate farming loops to inspect, not
guaranteed achievable scoring rates. A cheap fallback plan is submitted before
search so fuel exhaustion cannot leave draft memory empty.

## Tests

```sh
uv run python -m unittest discover -s bots/economy-bot/tests -v
```

Tests are grouped by module: combat, draft, navigation, planner, plan memory,
visualization, and the inspection CLI. `tests/sdk_fakes.py` supplies small SDK
substitutes for host tests. `test_regression.py` pins the pre-refactor route
rankings/scores and exact SQL2 bytes, rather than deriving expected values from
the refactored implementation. Tests also cover SDK enum annotations, repeatable
class-based searches, budget reset, and non-mutated input tables.

SDK imports stay out of the search and settings modules. No third-party test or
runtime dependencies are required. Under a fuel cutoff, search depth can still
vary with implementation overhead; fixed-expansion searches are deterministic.
