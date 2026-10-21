# Draft-only squad loop planner

Gameplay is intentionally a no-op. During draft, this bot searches for one loop
for the entire squad and reports its five best distinct camp-set/altar combinations.

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

`RISK_TOLERANCE = 0.2` is defined in `src/planner.py`. It ranges from **0**
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

- `src/draft.py`: `PICK_ORDER` sets the assumed squad and actual draft picks;
  defaults to Varg, Willow, Vendetta, Marcella, then Tavi as team size permits.
- `CANDIDATE_LIMIT = 24`: spawn-accessible, high-value candidate groups.
- `ALTAR_LIMIT = 4`: nearest reachable altars to spawn.
- Distance precomputation can reduce these counts on large maps to leave fuel
  for searching and reporting.
- `src/planner.py`: `SearchConfig` controls beam width, maximum route length,
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
