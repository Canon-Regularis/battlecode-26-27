"""SDK-independent loop scoring and bounded beam search.

Camp indices refer to entries in the supplied camp list, not engine handles.
Times are wall-clock squad turns; rewards are counted once for the whole team.
"""

from dataclasses import dataclass
from math import ceil

from settings import DEFAULT_SEARCH_CONFIG, FUEL_CHECK_INTERVAL, REPORT_LIMIT, SearchConfig


@dataclass(frozen=True)
class CampGroupInfo:
    anchor: tuple[int, int]
    gems: int
    gold: int
    service_turns: int
    respawn_turns: int


@dataclass(frozen=True)
class RiskProfile:
    camps: tuple[float, ...]
    altars: tuple[float, ...]


@dataclass(frozen=True)
class LoopEvaluation:
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
class ScoredLoop:
    altar_index: int
    camp_indices: tuple[int, ...]
    evaluation: LoopEvaluation


def positional_risk(ally_distance: int, enemy_distance: int) -> float:
    """Zero is home-side, one is enemy-side; -1 denotes unreachable."""
    if ally_distance < 0:
        return 0.5 if enemy_distance < 0 else 1.0
    if enemy_distance < 0:
        return 0.0
    total_distance = ally_distance + enemy_distance
    return ally_distance / total_distance if total_distance else 0.5


def camp_insertions(route: tuple[int, ...], camp_count: int):
    """Yield every single-camp insertion in deterministic camp/position order."""
    for camp_index in range(camp_count):
        if camp_index in route:
            continue
        for position in range(len(route) + 1):
            yield route[:position] + (camp_index,) + route[position:]


class LoopPlanner:
    """Own the static inputs for SDK-independent scoring and beam search.

    Supply the camp list and its aligned distance/risk tables once. Each search
    keeps its frontier and budget counters local, so this object can be reused.
    Input tables are read-only by convention; no game/SDK objects are required.
    """

    def __init__(self, camps: list[CampGroupInfo], distances: list[list[int]],
                 altar_distances: list[list[int]], spawn_distances: list[int], *,
                 config: SearchConfig = DEFAULT_SEARCH_CONFIG, risk: RiskProfile | None = None):
        self.camps = camps
        self.distances = distances
        self.altar_distances = altar_distances
        self.spawn_distances = spawn_distances
        self.config = config
        self.risk = risk

    def evaluate_loop(self, route: tuple[int, ...], altar_index: int) -> LoopEvaluation | None:
        """Score one altar -> camps -> altar loop; reject unreachable legs.

        Tribute conservatively assumes one bag. A one-tile camp cannot split its
        rewards among a whole squad, though actual parallel tributes can be faster.
        Omitting a risk profile leaves the positional penalty disabled.
        """
        if not route:
            return None
        camps, distances = self.camps, self.distances
        altar_distances, spawn_distances = self.altar_distances, self.spawn_distances
        config = self.config
        first_camp, last_camp = route[0], route[-1]
        # Keep altar legs first, then inter-camp legs; risk uses this same layout.
        legs = [altar_distances[altar_index][first_camp], altar_distances[altar_index][last_camp]]
        legs.extend(distances[origin][destination] for origin, destination in zip(route, route[1:]))
        if any(distance < 0 for distance in legs) or spawn_distances[first_camp] < 0:
            return None

        # More champions don't multiply rewards or shorten capture time.
        gems = sum(camps[index].gems for index in route)
        gold = sum(camps[index].gold for index in route)
        service_turns = sum(camps[index].service_turns for index in route)
        tribute_turns = ceil(gems / 10)
        travel_turns = sum(legs)
        active_turns = travel_turns + service_turns + tribute_turns

        # Respawn starts AFTER capture; the next visit still needs its service time.
        respawn_floor = max(camps[index].respawn_turns + camps[index].service_turns for index in route)
        period = max(active_turns, respawn_floor)
        first_deposit = active_turns - legs[0] + spawn_distances[first_camp]

        reward_value = gems + config.gold_weight * gold
        base_score = reward_value / (period + config.opening_weight * first_deposit)
        loop_risk = 0.0
        if self.risk is not None:
            loop_risk = self._calculate_loop_risk(
                route, altar_index, legs, tribute_turns, active_turns, period,
            )
        risk_multiplier = 1 - (1 - config.risk_tolerance) * loop_risk

        return LoopEvaluation(
            gems=gems, gold=gold, active_turns=active_turns, period=period,
            first_deposit=first_deposit, score=base_score * risk_multiplier,
            travel_turns=travel_turns, service_turns=service_turns, tribute_turns=tribute_turns,
            risk=loop_risk, risk_multiplier=risk_multiplier, base_score=base_score,
        )

    def find_loops(self, *, should_stop=lambda: False, limit: int = REPORT_LIMIT) -> list[ScoredLoop]:
        """Find promising loops, not a guaranteed global optimum.

        Each route length gets its own beam. Altars expand round-robin so a
        compute limit doesn't give the first altar the entire budget. Ties are stable.
        """
        camps, config = self.camps, self.config
        evaluate = self.evaluate_loop
        finalists = {}
        expansion_count = 0
        beams = {altar_index: [()] for altar_index in range(len(self.altar_distances))}
        budget_exhausted = False

        for _route_length in range(min(config.max_camps, len(camps))):
            candidates_by_altar = {altar_index: {} for altar_index in beams}
            largest_beam = max((len(beam) for beam in beams.values()), default=0)

            for beam_position in range(largest_beam):
                for altar_index, beam in beams.items():
                    if beam_position >= len(beam):
                        continue
                    for route in camp_insertions(beam[beam_position], len(camps)):
                        fuel_check_due = expansion_count % FUEL_CHECK_INTERVAL == 0
                        if expansion_count >= config.max_expansions or (fuel_check_due and should_stop()):
                            budget_exhausted = True
                            break
                        expansion_count += 1
                        evaluation = evaluate(route, altar_index)
                        if evaluation is None:
                            continue

                        # Don't fill the beam with permutations of the same set.
                        camp_set = frozenset(route)
                        candidates = candidates_by_altar[altar_index]
                        previous = candidates.get(camp_set)
                        if previous is None or evaluation.score > previous.evaluation.score:
                            candidates[camp_set] = ScoredLoop(altar_index, route, evaluation)
                    if budget_exhausted:
                        break
                if budget_exhausted:
                    break

            beams = self._select_next_beams(candidates_by_altar, finalists, limit)
            if budget_exhausted or not beams:
                break

        return sorted(finalists.values(), key=lambda loop: loop.evaluation.score, reverse=True)[:limit]

    def find_best_loop(self, *, should_stop=lambda: False) -> ScoredLoop | None:
        loops = self.find_loops(should_stop=should_stop, limit=1)
        return loops[0] if loops else None

    def _calculate_loop_risk(self, route, altar_index, legs,
                             tribute_turns, active_turns, period) -> float:
        """Time-weight exposure; travel uses the mean of its endpoint risks."""
        camps, distances, risk = self.camps, self.distances, self.risk
        if risk is None:
            return 0.0
        altar_risk = risk.altars[altar_index]
        first_camp, last_camp = route[0], route[-1]
        exposure = legs[0] * (altar_risk + risk.camps[first_camp]) / 2
        exposure += legs[1] * (risk.camps[last_camp] + altar_risk) / 2
        for origin, destination in zip(route, route[1:]):
            combined_risk = risk.camps[origin] + risk.camps[destination]
            exposure += distances[origin][destination] * combined_risk / 2
        exposure += sum(camps[index].service_turns * risk.camps[index] for index in route)
        # A fixed repeating loop can put its extra respawn waiting at the altar.
        exposure += (tribute_turns + period - active_turns) * altar_risk
        return min(1.0, max(0.0, exposure / period))

    def _select_next_beams(self, candidates_by_altar, finalists, report_limit):
        """Keep diverse camp sets and save finalists at this route length."""
        config = self.config
        next_beams = {}
        for altar_index, candidates in candidates_by_altar.items():
            ranked = sorted(candidates.values(), key=lambda loop: loop.evaluation.score, reverse=True)
            if ranked:
                next_beams[altar_index] = [loop.camp_indices for loop in ranked[:config.beam_width]]
            for loop in ranked[:max(report_limit, config.beam_width)]:
                if loop.evaluation.gems:
                    finalists[(altar_index, frozenset(loop.camp_indices))] = loop
        return next_beams
