"""Pure, bounded beam search for a single squad's farming loop.

Distances and combat estimates are supplied by draft.py so this module can be
tested without the WASM-only cambc bindings. All times are team wall-clock turns.
"""

from dataclasses import dataclass
from math import ceil


RISK_TOLERANCE = 0.2


def positional_risk(ally_distance, enemy_distance):
    """Zero is home-side, one is enemy-side; -1 denotes unreachable."""
    if ally_distance < 0:
        return 0.5 if enemy_distance < 0 else 1.0
    if enemy_distance < 0:
        return 0.0
    total = ally_distance + enemy_distance
    return ally_distance / total if total else 0.5


@dataclass(frozen=True)
class RiskProfile:
    camps: tuple[float, ...]
    altars: tuple[float, ...]


@dataclass(frozen=True)
class Camp:
    anchor: tuple[int, int]
    gems: int
    gold: int
    service: int
    respawn: int


@dataclass(frozen=True)
class SearchConfig:
    beam_width: int = 8
    max_camps: int = 10
    max_expansions: int = 20000
    gold_weight: float = 0.02
    opening_weight: float = 0.15
    risk_tolerance: float = RISK_TOLERANCE

    def __post_init__(self):
        if not 0 <= self.risk_tolerance <= 1:
            raise ValueError("risk tolerance must be between 0 and 1")


@dataclass(frozen=True)
class Evaluation:
    gems: int
    gold: int
    active_turns: int
    period: int
    first_deposit: int
    score: float
    travel_turns: int
    service_turns: int
    tribute_turns: int
    risk: float
    risk_multiplier: float
    base_score: float


@dataclass(frozen=True)
class Loop:
    altar: int
    camps: tuple[int, ...]
    evaluation: Evaluation


def evaluate(route, altar, camps, distances, altar_distances, spawn_distances,
             config=SearchConfig(), risk=None):
    """Estimate a fixed loop; None means that some leg is unreachable.

    Tribute uses the conservative single-bag time: a one-tile camp cannot split
    its reward among a whole squad. Runtime channels can still run in parallel.
    """
    if not route:
        return None
    first, last = route[0], route[-1]
    legs = [altar_distances[altar][first], altar_distances[altar][last]]
    legs.extend(distances[a][b] for a, b in zip(route, route[1:]))
    if any(d < 0 for d in legs) or spawn_distances[first] < 0:
        return None
    gems = sum(camps[i].gems for i in route)
    gold = sum(camps[i].gold for i in route)
    service = sum(camps[i].service for i in route)
    tribute = ceil(gems / 10)
    active = sum(legs) + service + tribute
    period = max(active, max(camps[i].respawn + camps[i].service for i in route))
    first_deposit = active - legs[0] + spawn_distances[first]
    value = gems + config.gold_weight * gold
    base_score = value / (period + config.opening_weight * first_deposit)
    loop_risk = 0.0
    if risk is not None:
        altar_risk = risk.altars[altar]
        # Travel exposure is a trapezoidal approximation from endpoint risks;
        # avoid reconstructing every candidate's tile-by-tile path in draft.
        exposure = legs[0] * (altar_risk + risk.camps[first]) / 2
        exposure += legs[1] * (risk.camps[last] + altar_risk) / 2
        for a, b in zip(route, route[1:]):
            exposure += distances[a][b] * (risk.camps[a] + risk.camps[b]) / 2
        exposure += sum(camps[i].service * risk.camps[i] for i in route)
        # A fixed loop can put its extra respawn waiting at the altar.
        exposure += (tribute + period - active) * altar_risk
        loop_risk = min(1.0, max(0.0, exposure / period))
    multiplier = 1 - (1 - config.risk_tolerance) * loop_risk
    score = base_score * multiplier
    return Evaluation(gems, gold, active, period, first_deposit, score,
                      sum(legs), service, tribute, loop_risk, multiplier, base_score)


def find_loops(camps, distances, altar_distances, spawn_distances,
               config=SearchConfig(), should_stop=lambda: False, limit=5, risk=None):
    """Insert camps at every position, keeping distinct camp sets per altar.

    Each depth has its own beam, so good short loops don't prevent exploration
    of longer clusters. Expansion and optional fuel limits bound draft cost.
    """
    finalists = {}
    expansions = 0
    beams = {altar: [()] for altar in range(len(altar_distances))}
    exhausted = False
    for _depth in range(min(config.max_camps, len(camps))):
        candidates = {altar: {} for altar in beams}
        # Round-robin altars and beam positions so a budget limit doesn't give
        # all compute to the first altar in the map's enumeration.
        for beam_index in range(max((len(beam) for beam in beams.values()), default=0)):
            for altar, beam in beams.items():
                if beam_index >= len(beam):
                    continue
                route = beam[beam_index]
                for camp in range(len(camps)):
                    if camp in route:
                        continue
                    for position in range(len(route) + 1):
                        if (expansions >= config.max_expansions
                                or (expansions % 8 == 0 and should_stop())):
                            exhausted = True
                            break
                        expansions += 1
                        trial = route[:position] + (camp,) + route[position:]
                        result = evaluate(trial, altar, camps, distances,
                                          altar_distances, spawn_distances, config, risk)
                        if result is None:
                            continue
                        loop = Loop(altar, trial, result)
                        # Preserve different clusters instead of filling the beam
                        # with permutations of exactly the same camps.
                        key = frozenset(trial)
                        previous = candidates[altar].get(key)
                        if previous is None or result.score > previous.evaluation.score:
                            candidates[altar][key] = loop
                    if exhausted:
                        break
                if exhausted:
                    break
            if exhausted:
                break
        beams = {}
        for altar, routes in candidates.items():
            ranked = sorted(routes.values(), key=lambda loop: loop.evaluation.score, reverse=True)
            if ranked:
                beams[altar] = [loop.camps for loop in ranked[:config.beam_width]]
            for loop in ranked[:max(limit, config.beam_width)]:
                if loop.evaluation.gems:
                    finalists[(altar, frozenset(loop.camps))] = loop
        if exhausted or not beams:
            break
    return sorted(finalists.values(), key=lambda loop: loop.evaluation.score, reverse=True)[:limit]


def search(camps, distances, altar_distances, spawn_distances,
           config=SearchConfig(), should_stop=lambda: False, risk=None):
    """Convenience wrapper for callers that only need the top loop."""
    loops = find_loops(camps, distances, altar_distances, spawn_distances,
                       config, should_stop, 1, risk)
    return loops[0] if loops else None
