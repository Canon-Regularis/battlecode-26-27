# D1 Development Plan — Beat G3

## Target

Turn D1 into a compact resource-cycle challenger that wins at least 10/18 fixed map/side matches against G3 at `--fuel 100000`, finishes with a positive aggregate submitted-gem differential, has no faults or fuel failures, and repeats the result after the source is frozen. G3 remains protected and no external submission is permitted.

## Feedback loop

Use the current 5/18 D1 matrix as the baseline. Screen one policy change on both sides of Collision, Interlock, Packs and Rows: two severe failures plus two existing strengths. A serious improvement advances to the complete nine-map/two-side matrix with exported statistics. Preserve every source candidate and its results.

## Ranked hypotheses

1. **Bank-route selection:** D1 chooses one altar by Chebyshev distance before pathfinding. On obstructed maps this can create poor or stalled return routes. Use one distance field across all currently viable altar approach tiles.
2. **Camp allocation:** every champion routes to the same global nearest-goal set. Add bounded, stable group scoring only after fixing banking, because previous soft assignment experiments elsewhere regressed.
3. **Capture commitment:** target churn may abandon useful clear/capture progress. Retain an objective while it remains viable and close to the best current option.
4. **Movement-level safety:** visible danger may justify rerouting carriers, but the low-death Collision and Interlock failures point first to throughput rather than survival.
5. **Full scorer risk:** D1's earlier full-cycle scorer underperformed. Reuse verified mechanics and small estimators, not that implementation wholesale.

## Candidate sequence

### D1.1 — Path-aware conversion

- Route carriers toward all unlocked altar approach tiles with the native distance field.
- Explicitly vacate a camp spawn tile known to be respawning before starting a bank channel.
- Keep the current farming and combat policy fixed.
- Screen on Collision, Interlock, Packs and Rows, both sides.

### D1.2 — Stable economic assignment

Only if D1.1 improves the screen:

- Rank each camp group by a bounded value estimate using static gems, path distance, visible/remembered state, capture cost, approximate clear cost, altar return geometry and visible ally occupancy.
- Assign different stable tie preferences by champion identity, without hard-partitioning camps.
- Retain the current objective until a materially better candidate appears or its state invalidates it.
- Keep nearest-camp navigation as the low-fuel fallback.

### D1.3 — Minimal regroup/safety

Only if telemetry identifies carrier losses or dangerous crossings as a remaining bottleneck:

- Add one local rule for visible carrier danger or nearby allied escort value.
- Do not add speculative fog prediction or map scripts.

## Fuel bounds

Static group metadata is cached once per champion instance. Each decision scans camp groups, visible allies/enemies and altar tiles linearly. Use at most a small constant number of native distance-field computations per turn. Optional scoring must fall back to the simple goal union when fuel is low.

## Evidence and promotion

Record outcome, round, submitted/collected gems, deaths and faults. Treat fixed map/side results as deterministic comparative evidence, not randomized trials. Promote D1 only after the full matrix and frozen repeat satisfy the target; then evaluate carrier-hunter and altar-denial proxies where practical. Otherwise preserve the strongest D1 candidate and report the remaining failure.
