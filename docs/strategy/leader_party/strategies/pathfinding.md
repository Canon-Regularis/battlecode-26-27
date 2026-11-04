# Navigation and fuel

Source: `navigation.cpp` and `observations.cpp`. Native bitboards and distance fields model walking. Walls, holes, altars, enemy spawn, known champions/camps and teleport occupancy block routes; only self is removed. Capture and attack goals exclude occupied tiles. Safe movement additionally excludes visible enemy range plus one tile and awake camp attack areas.

A reverse field chooses a strictly decreasing walking step with deterministic y/x ties. Travel dashes must improve distance by more than one and use a free walking-connected mask within ability range. This conservative subset does not exploit all legal cross-hole dash paths. Protection uses constrained walking. Retreat has a bounded local fallback ranked by incoming damage, distance from enemies and spawn distance.

After three blocked turns, a mutually visible higher-ID body may yield into a safe passing tile for two of five blocked turns. Task deadlines eventually release unresolved objectives. A rejected occupied destination invalidates observations and permits at most one field retry within the three-field quota.

Admission requires 55,000 remaining fuel and a current-round check. The critical write reserve is 10,000. Optional post-move attacks, wards and logs have separate admission guards. Noncommitted camp processing is staggered before costly bitboard intersections; failing to do so caused the reproducible lanes/expanse liveness bug. Snapshot storage is stable and invalidated after moves/casts/purchases/reveals.

Round checks discard stale field results and pending writes. Expected API visibility/entity disappearance aborts the dispatch and rebuilds facts next turn. WASM can resume inside arbitrary code after exhausting fuel; these guards are defensive boundaries, not a proof that every SDK getter is atomic. The release disables shared coordination. Custom low-fuel execution is stress-tested separately and is not a promise of useful scoring below native-query admission.
