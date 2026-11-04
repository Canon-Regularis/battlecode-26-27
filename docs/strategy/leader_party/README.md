# C++ leader-party bot

The preferred bot is [leader_party_subhan](../../../bots/leader_party_subhan/README.md), built against CAMBC 4.0.0. It adds Subhan's C++ camp-loop planner to the unchanged [leader_party baseline](../../../bots/leader_party/README.md). It won the direct comparison **93–79** across 86 maps and the combined controls **73–23**, versus the baseline's **72–24**. This is a modest, uncertain upgrade; keep the baseline as a fallback. See [planner integration and evaluation](subhan_comparison.md) for all 364 comparison matches and [baseline implementation results](implementation_results.md) for the original release's coverage and limitations.

Both variants use autonomous local camp selection, capture, spending, recovery and banking. Shared leader guidance and remote rallies are disabled after the paired comparison. The versioned protocol and election implementation remain available for experiments; local protection needs no shared messages. The baseline uses distance routing. The preferred variant follows eligible planned camp loops after its first two equipment phases, with the original selector as fallback. No collector, runner or escort roles are allocated. The platform submission was not changed by the planner experiment.

| Reference | Responsibility |
| --- | --- |
| [State machine](state_machine.md) | Ordered decisions, task deadlines, channels and protection |
| [Communication](communciation.md) | Experimental shared protocol and visibility rules |
| [Configuration](config.md) | Release defaults and important constants |
| [Combat](combat.md) | Ability adapters, action ordering and limitations |
| [Routing](strategies/route_planning.md) | Distance/value alternatives and exploration |
| [Subhan planner comparison](subhan_comparison.md) | Preferred variant, C++ port, adaptations and full-pool evaluation |
| [Navigation](strategies/pathfinding.md) | Native fields, occupancy, fuel and suspension |
| [Banking](strategies/altar_selection.md) | Local courtesy and carrier protection |
| [Shopping](strategies/shop.md) | Draft and equipment progression |
| [Wards](strategies/ward_placing.md) | Optional local placement |

The [all-bot baseline tournament](all_bots_results.md) records the original bot's 166–14 result against the 15 then-existing opponents. This was a smaller map sample than the planner comparison and does not rank the clone against every bot.

The [pre-implementation strategy documents](history/2026-11-04-pre-implementation/README.md) are retained as design history. Their older binary layout and leadership-only planning restrictions are superseded by the current references above. The [retired implementation](../../../bots/archive/state-machine-2026-11-04/README.md) remains intact. Completed implementation plans and the old critique have been removed; current behavior, remaining gaps and measured outcomes are recorded here and in the linked references.
