# Leader-party strategy

Current design for the travelling party, rotating leader, detached resource runners, and committed objective defense. This folder contains design documents, not an implemented bot.

| Read in this order | Purpose |
| --- | --- |
| [team_plan.md](team_plan.md) | Roles, leader succession, repeated small-node passes, collector and runner coordination. |
| [state_machine.md](state_machine.md) | Twelve states, short safety key, actions, ordered transition tables, return decision, execution priorities, and debug colours. |
| [config.md](config.md) | Single reference for configurable priorities, thresholds, distances, timers, and fuel budgets. |
| [communciation.md](communciation.md) | Proposed chunk-based shared payload, leader messages, safety/eligibility bits, and unresolved protocol metadata. Original filename spelling retained. |
| [state_machine.mmd](state_machine.mmd) | Whole connected coloured state diagram; transition tables define precedence. |
| [strategies/chunking.md](strategies/chunking.md) | Balanced 15-tile maximum chunks, six-bit IDs, exact mapping, visibility-aware inspection, and edge cases. |

## Temporary MVP strategies

These four documents now contain deliberately simple implementation specifications. Each is marked **TEMPORARY MVP PLACEHOLDER** at the top and should be replaced/tuned after working matches:

| File | MVP baseline |
| --- | --- |
| [strategies/pathfinding.md](strategies/pathfinding.md) | SDK native distance fields, legal task goals, simple threat masks, limited hidden-blocker retry. |
| [strategies/altar_selection.md](strategies/altar_selection.md) | Reachable altar distance plus visible risk/lock cost, stable choice, explicit lock removal and actual channel confirmation. |
| [strategies/ward_placing.md](strategies/ward_placing.md) | A few legal local placements scored by persistent coverage near the current objective. |
| [strategies/shop.md](strategies/shop.md) | Fixed champion builds, automatic-emblem bookkeeping, leftover-gold lock purchase, dead/spawn/Tavi handling. |

There is no separate states.md: state actions and transitions remain together.

## Before implementation

The current review settles the state structure and proposed payload meanings. It does not finish the whole strategy. Resolve these contracts next:

1. Integrate the documented chunk inspection helper with the existing pathfinder and measure provisional Python fuel budgets. NATIVE_MVP temporarily replaces chunking's hard expansion budget with native-call/fuel limits.
2. Freshness, initialization, replacement identity, hard attack deadlines, and resumed-write handling within 64 bits.
3. Exact camp/altar identity and runner assignment/acknowledgement, skip-counter persistence across baton handovers.
4. Existing planner integration and concrete bounded combat/support path helpers.
5. Implement the temporary strategy specifications and observe complete capture/bank cycles; then replace their fixed builds/scores/ward heuristic and tune values from results.

Eligibility offers use six bits because safety summaries alone cannot express the required Health/role check. Six-bit chunk locations leave 17 reserved bits in the communication proposal; its table accounts for every bit.

Parent [analysis.md](../analysis.md) retains the champion/ladder evidence. Parent [meta_strategy.md](../meta_strategy.md) is historical and does not override this folder. No new ladder research was performed for this rework.

