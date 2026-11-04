# C++ leader-party bot

The active replacement is [bots/leader_party](../../../bots/leader_party/src/main.cpp), built against CAMBC 4.0.0. See [implementation results](implementation_results.md) for measured performance and limitations and [plan.md](../../../plan.md) for the implementation contract and deviations.

The release uses autonomous local camp selection, capture, spending, recovery and banking. Shared leader guidance and remote rallies are disabled after the paired comparison. The versioned protocol and election implementation remain available for experiments; local protection needs no shared messages. Distance routing is the release default. No collector, runner or escort roles are allocated.

| Reference | Responsibility |
| --- | --- |
| [State machine](state_machine.md) | Ordered decisions, task deadlines, channels and protection |
| [Communication](communciation.md) | Experimental shared protocol and visibility rules |
| [Configuration](config.md) | Release defaults and important constants |
| [Combat](combat.md) | Ability adapters, action ordering and limitations |
| [Routing](strategies/route_planning.md) | Distance/value alternatives and exploration |
| [Navigation](strategies/pathfinding.md) | Native fields, occupancy, fuel and suspension |
| [Banking](strategies/altar_selection.md) | Local courtesy and carrier protection |
| [Shopping](strategies/shop.md) | Draft and equipment progression |
| [Wards](strategies/ward_placing.md) | Optional local placement |

The [critical analysis](critical_analysis.md) and [pre-implementation documents](history/2026-11-04-pre-implementation/README.md) are historical inputs, not active specifications. Their older binary layout and leadership-only planning restrictions are superseded. The [retired implementation](../../../bots/archive/state-machine-2026-11-04/README.md) remains intact.
