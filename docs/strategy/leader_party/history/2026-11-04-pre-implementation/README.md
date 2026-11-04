# Leader-party strategy

Design for a C++ bot named `leader_party`; implementation is pending the design interview. The existing starter is not the requested finished bot.

The earlier custom C++ implementation is [archived](../../../bots/archive/state-machine-2026-11-04/README.md). The [critical analysis](critical_analysis.md) reviews this revised plan, its implementation blockers, and strategic risks. Its recommendations are proposals, not changes to the confirmed policy below.

[state_machine.md](state_machine.md) alone defines transitions. The deleted team plan is not used. `analysis.md` and `team_meta.md` are excluded.

| Document | Purpose |
| --- | --- |
| [state_machine.md](state_machine.md) | State actions, ordered transitions, and the user's leadership correction. |
| [communciation.md](communciation.md) | Last-commit binary layout with current leader, messages, rallies, enemy observations, and original safety summaries; no eligibility or age slots. |
| [config.md](config.md) | Existing thresholds, distances, timers, and C++ fuel settings; nonleader allocation settings removed. |
| [combat.md](combat.md) | Only the user's confirmed combat principles; unresolved choices are marked. |
| [strategies/route_planning.md](strategies/route_planning.md) | Requested temporary closest-camp routing, respawn-at-arrival handling, and exploration requirement. |
| [state_machine.mmd](state_machine.mmd) | Diagram matching the settled state-table changes. |
| [strategies/chunking.md](strategies/chunking.md) | Existing grid and bounded inspection. |
| [strategies/pathfinding.md](strategies/pathfinding.md) | Existing native pathfinding with the user's travel/escape dash requirement. |
| [strategies/altar_selection.md](strategies/altar_selection.md) | Existing altar strategy plus the user's local patrol/carrier/turn-taking decisions. |
| [strategies/ward_placing.md](strategies/ward_placing.md) | Existing local ward strategy. |
| [strategies/shop.md](strategies/shop.md) | Unchanged committed shopping baseline. |

## Confirmed leadership and team correction

Only leadership is allocated. The current leader clears its three identity bits to 111 on low Health, then follows normal state-machine recovery. The next leader auto-selects using the existing preference order. Death cleanup clears a dead leader. Capture, banking, protection, rallies, and other state changes do not by themselves relinquish leadership. There are no nominations, shared eligibility offers, report-age slots, or handover cooldowns.

No runner, collector, or escort allocation is used. Existing capture tasks continue through leader changes. Bank protection remembers one observed carrier and patrols the current altar.

## Decisions still open

Earlier interview recommendations about exact ATTACK ratios, ability ordering, shield observation windows, heal thresholds, dash landing choices, exploration ownership, banking queue admission, and draft changes have not been accepted and are not implementation defaults. The shared binary reference reserves bits 41–63; do not fill them without an explicit user decision.
