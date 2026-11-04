# C++ leader-party bot

The preferred bot is [leader_party_tuned](../../../bots/leader_party_tuned/README.md), matching frozen `g07_search` and built against CAMBC 4.0.0. Its combined configuration won **409–107** across 86 published maps against three common opponents. See [complete configuration tuning](config_tuning_all_stats.md) for all values, generation comparisons and measured limits.

All variants use autonomous local camp selection, capture, spending, recovery and banking. Shared leader guidance and remote rallies are disabled after evaluation. The versioned protocol and election implementation remain available for experiments; local protection needs no shared messages. The original [leader_party](../../../bots/leader_party/README.md) uses distance routing. The untuned Subhan bot follows eligible planned camp loops after two equipment phases; the tuned bot starts after three. Both retain the original selector as fallback. No collector, runner or escort roles are allocated. The platform submission was not changed by these experiments.

| Reference | Responsibility |
| --- | --- |
| [State machine](state_machine.md) | Ordered decisions, task deadlines, channels and protection |
| [Communication](communciation.md) | Experimental shared protocol and visibility rules |
| [Configuration](config.md) | Release defaults and important constants |
| [Combat](combat.md) | Ability adapters, action ordering and limitations |
| [Routing](strategies/route_planning.md) | Distance/value alternatives and exploration |
| [Configuration tuning](config_tuning.md) | Current champion, exact values, generation comparisons and validation |
| [Subhan planner comparison](subhan_comparison.md) | Original C++ port, adaptations and full-pool evaluation |
| [Navigation](strategies/pathfinding.md) | Native fields, occupancy, fuel and suspension |
| [Banking](strategies/altar_selection.md) | Local courtesy and carrier protection |
| [Shopping](strategies/shop.md) | Draft and equipment progression |
| [Wards](strategies/ward_placing.md) | Optional local placement |

The [all-bot baseline tournament](all_bots_results.md) records the original bot's 166–14 result against the 15 then-existing opponents. This was a smaller map sample than the planner comparison and does not rank the clone against every bot.

The [pre-implementation strategy documents](history/2026-11-04-pre-implementation/README.md) are retained as design history. Their older binary layout and leadership-only planning restrictions are superseded by the current references above. The [retired implementation](../../../bots/archive/state-machine-2026-11-04/README.md) remains intact. Completed implementation plans and the old critique have been removed; current behavior, remaining gaps and measured outcomes are recorded here and in the linked references.
