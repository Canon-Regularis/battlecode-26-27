# Implemented combat policy

Source: `bots/leader_party/src/combat.cpp`. Adapters inspect SDK ability kinds and target masks rather than assuming slot meanings. The deterministic draft normally produces Heart, Marcella, Vesper, Ren and Vendetta; adapters also support damage, AoE, CC, heal, shield, reset and dash abilities of fallback picks. Every fallback champion and linked-body combination has not been exhaustively exercised in matches.

Channels are preserved. Escape tries movement first, then a useful defensive cast and in-range attacks. Travel and banking move before discretionary combat. A camp in basic range may be attacked before moving; a distant camp is approached first. Threatening visible champions take priority over the assigned camp, then lowest current HP targets are considered. Targets are owning SDK wrapper values through execution, avoiding pointers into destroyed temporary camp vectors.

A legal basic attack precedes a damage/reset cast. Damage casts prefer a lethal outcome, then effective primary damage, with AoE hit count as a small tie-break. AoE centers are the selected target tile; a global center search is not implemented. Movement-exclusive spells are skipped after normal movement is unavailable. Readiness alone does not establish this SDK restriction.

A shield is considered under incoming threat below 70% HP. Ally heals prioritize preventing estimated basic-damage death, then effective restoration, and require <75% HP and legal range. These heuristics do not infer damage type from HP differences. Self-only heal optimization and full champion-specific combo search remain future work.

Raw incoming damage includes visible enemy basic attacks and awake camps. It is a conservative heuristic that ignores armor, shields, hidden enemies and cooldown timing. Expected visibility/entity loss aborts the affected dispatch and refreshes the next snapshot; unexpected errors are logged separately and fail the benchmark harness.
