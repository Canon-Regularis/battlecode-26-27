# Temporary dynamic camp routing

Historical pre-implementation strategy; superseded by the [current bot documentation](../../../README.md).

Status: user-approved direction recorded on 22 October 2026. A teammate is developing a replacement planner; keep this baseline behind a small replaceable interface. This document chooses objectives, while pathfinding.md supplies movement and state_machine.md alone defines transitions.

## Objective selection

Choose efficiently reachable camps by travel distance, without weighting gem value, gold value, monster difficulty, or reward type. Break equal distance/arrival-cost ties by canonical camp ID, sorted by camp anchor (y,x).

Reassess dynamically when the current objective becomes less reachable than another. Do not force completion of an unavailable route. Preserve a valid CAPTURE_POINT/PROTECT_POINT commitment until its state-machine exit; routing is not permission to abandon that commitment.

Use known camp respawn timing at estimated arrival. A known respawning camp may qualify if it is expected to be available when reached. Otherwise ignore it until expected availability rather than waiting on its spawn tile. Hidden current lifecycle state remains unknown; an old respawn prediction is not a fresh engine observation.

Stop at ordinary selected nodes until capture completes or the state machine permits escape from danger. When passing a single gold/gem node, the leader walks past rather than imposing a full-party stop. The exact definition of a single node and whether followers independently clear/collect it remain interview decisions. There is no nominated runner or collector.

When no camp qualifies, explore to find/reobserve camps. The requested exploring state, who performs exploration, viewpoint ordering, and its transition table remain to be specified in state_machine.md before implementation.

## Interface boundary

The baseline should return a chosen camp/approach, an exploration request, or a deferred computation. Distance/fuel deferral must not claim that a camp is unreachable. Keep observations, cached respawn estimates, and movement feasibility separate so the replacement planner can consume them without owning state transitions.
