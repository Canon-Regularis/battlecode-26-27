"""SDK-dependent map preparation and route-plan construction.

Read DraftPlanner.build() for the pipeline; draft.py handles champion selection
and the engine entry point. This module does not make picks or submit memory.
The scoring/search math lives in planner.py; combat estimates live in combat.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import cambc
from cambc import game_map

import settings
from combat import estimate_camp_clear
from navigation import (
    DistanceMap, blocked_terrain, build_distance_map, build_enemy_spawn_map,
    spawn_risk_at, tiles_within,
)
from plan_memory import DraftPlan, RoutePlan
from planner import CampGroupInfo, LoopPlanner, RiskProfile


@dataclass(frozen=True)
class CandidateCamp:
    info: CampGroupInfo
    priority: float
    distance_from_spawn: int
    risk: float


@dataclass(frozen=True)
class CandidateAltar:
    position: cambc.Vec2
    approach_tiles: cambc.Bitboard
    distance_from_spawn: int


@dataclass(frozen=True)
class PlanningData:
    camps: list[CampGroupInfo]
    altars: list[CandidateAltar]
    distances: list[list[int]]
    altar_distances: list[list[int]]
    spawn_distances: list[int]
    risk: RiskProfile


@dataclass(frozen=True)
class DraftMapContext:
    """SDK-only inputs shared by the map-preparation stages of one build."""

    squad: list[cambc.Champion]
    groups: tuple[game_map.CampGroup, ...]
    blocked: cambc.Bitboard
    ally: DistanceMap
    enemy: DistanceMap


def draft_budget_exhausted() -> bool:
    if cambc.fuel_remaining() >= settings.FUEL_RESERVE:
        return False
    print("Search stopped at the draft fuel reserve; reporting best candidates so far.", flush=True)
    return True


def route_plan_for(loop, data: PlanningData) -> RoutePlan:
    altar = data.altars[loop.altar_index].position
    return RoutePlan((altar.x, altar.y), tuple(data.camps[index].anchor for index in loop.camp_indices))


def fallback_group_priority(group, spawn):
    health_per_gem = sum(camp.base_stats().base_health for camp in group) / group.gem_value()
    nearest_spawn_tile = min(spawn.chebyshev_distance(camp.spawn_position()) for camp in group)
    return health_per_gem + nearest_spawn_tile


class DraftPlanner:
    """Own a squad/configuration and orchestrate its SDK-dependent draft work.

    Construction performs no engine queries. Each build reads a fresh, explicit
    map context instead of leaving partially initialized map fields on self.
    """

    def __init__(self, roster: tuple[cambc.ChampionType, ...],
                 config: settings.SearchConfig = settings.DEFAULT_SEARCH_CONFIG):
        self.roster = roster
        self.config = config

    def build(self) -> DraftPlan:
        """Read map -> prepare candidates -> search -> report -> create plan."""
        context = self._read_map()
        candidates = self._collect_camps(context)
        altars = self._collect_altars(context)
        if not altars:
            raise ValueError("no reachable altar")
        if not candidates:
            empty = PlanningData([], altars, [], [], [], RiskProfile((), ()))
            self._publish_report([], empty)
            altar = altars[0].position
            return DraftPlan(RoutePlan((altar.x, altar.y), ()), self.roster)

        print(f"Searching {len(candidates)} of {len(context.groups)} camp groups and {len(altars)} altars",
              flush=True)
        data = self._prepare_data(context, candidates, altars)
        loops = self._search(data)
        self._publish_report(loops, data)
        return self._create_plan(loops, data)

    def fallback_plan(self) -> DraftPlan:
        """Create something cheap before any fuel-heavy precomputation."""
        spawn = game_map.spawn_region(cambc.Team.ALLY).positions()[0]
        altars = game_map.altars().positions()
        if not altars:
            raise ValueError("map has no altar")
        altar = min(altars, key=spawn.chebyshev_distance)
        groups = [group for group in game_map.camp_groups() if group.gem_value()]
        camp_anchors = ()
        if groups:
            group = min(groups, key=lambda candidate: fallback_group_priority(candidate, spawn))
            anchor = min(group.spawn_tiles().positions(), key=lambda position: (position.y, position.x))
            camp_anchors = ((anchor.x, anchor.y),)
        return DraftPlan(RoutePlan((altar.x, altar.y), camp_anchors), self.roster)

    def _read_map(self) -> DraftMapContext:
        squad = [cambc.Champion.design(kind) for kind in self.roster]
        blocked = blocked_terrain()
        ally = build_distance_map(game_map.spawn_region(cambc.Team.ALLY), blocked)
        enemy = build_enemy_spawn_map(blocked)
        return DraftMapContext(squad, game_map.camp_groups(), blocked, ally, enemy)

    def _collect_camps(self, context: DraftMapContext) -> list[CandidateCamp]:
        squad, ally, enemy = context.squad, context.ally, context.enemy
        config = self.config
        candidates = []
        for group in context.groups:
            estimate = estimate_camp_clear(group, squad)
            positions = group.spawn_tiles().positions()
            anchor = min(positions, key=lambda position: (position.y, position.x))
            distance_from_spawn = ally.distance_at(anchor)
            if distance_from_spawn < 0 or not estimate.survivable:
                continue

            risk = sum(spawn_risk_at(position, ally, enemy) for position in positions) / len(positions)
            info = CampGroupInfo(
                anchor=(anchor.x, anchor.y), gems=group.gem_value(), gold=group.gold_value(),
                service_turns=estimate.service_turns, respawn_turns=group.max_respawn_timer(),
            )
            reward_value = info.gems + config.gold_weight * info.gold
            priority = reward_value / (info.service_turns + distance_from_spawn + 1)
            priority *= 1 - (1 - config.risk_tolerance) * risk
            candidates.append(CandidateCamp(info, priority, distance_from_spawn, risk))

        candidates.sort(key=lambda candidate: candidate.priority, reverse=True)
        return candidates[:settings.CANDIDATE_LIMIT]

    def _collect_altars(self, context: DraftMapContext) -> list[CandidateAltar]:
        blocked, ally = context.blocked, context.ally
        candidates = []
        for position in game_map.altars().positions():
            approaches = tiles_within(position, cambc.constants.SUBMIT_GEMS_RANGE) & ~blocked
            distance = ally.nearest_distance(approaches.positions())
            if distance >= 0:
                candidates.append(CandidateAltar(position, approaches, distance))
        candidates.sort(key=lambda altar: (
            altar.distance_from_spawn, altar.position.y, altar.position.x,
        ))
        return candidates[:settings.ALTAR_LIMIT]

    def _prepare_data(self, context: DraftMapContext, candidates, altars) -> PlanningData:
        """Build aligned matrices, reducing their size if BFS consumes too much fuel."""
        blocked, ally, enemy = context.blocked, context.ally, context.enemy
        camps = [candidate.info for candidate in candidates]
        points = [cambc.Vec2(*camp.anchor) for camp in camps]

        altar_distances = []
        previous_bfs_cost = 0
        for altar in altars:
            fuel_before = cambc.fuel_remaining()
            if altar_distances and fuel_before - previous_bfs_cost < settings.PRECOMPUTE_RESERVE:
                break
            field = build_distance_map(altar.approach_tiles, blocked)
            altar_distances.append([field.distance_at(point) for point in points])
            previous_bfs_cost = max(0, fuel_before - cambc.fuel_remaining())
        altars = altars[:len(altar_distances)]

        altar_risks = []
        for altar in altars:
            reachable_tiles = [point for point in altar.approach_tiles.positions()
                               if ally.visited.is_set(point)]
            altar_risks.append(
                sum(spawn_risk_at(point, ally, enemy) for point in reachable_tiles) / len(reachable_tiles)
            )

        distances = []
        for point in points:
            # Native BFS cannot be interrupted; budget for it before starting it.
            fuel_before = cambc.fuel_remaining()
            if fuel_before - previous_bfs_cost < settings.PRECOMPUTE_RESERVE:
                break
            field = build_distance_map(tiles_within(point, 0), blocked)
            distances.append([field.distance_at(destination) for destination in points])
            previous_bfs_cost = max(0, fuel_before - cambc.fuel_remaining())

        camp_count = len(distances)
        if not camp_count:
            # A singleton needs only its zero self-distance; altar fields exist.
            camp_count, distances = 1, [[0]]
        if camp_count < len(camps):
            print(f"BFS fuel limit: retaining {camp_count} candidate camps and {len(altars)} altars", flush=True)

        return PlanningData(
            camps=camps[:camp_count], altars=altars,
            distances=[row[:camp_count] for row in distances],
            altar_distances=[row[:camp_count] for row in altar_distances],
            spawn_distances=[candidate.distance_from_spawn for candidate in candidates[:camp_count]],
            risk=RiskProfile(tuple(candidate.risk for candidate in candidates[:camp_count]), tuple(altar_risks)),
        )

    def _search(self, data: PlanningData):
        planner = LoopPlanner(
            camps=data.camps, distances=data.distances,
            altar_distances=data.altar_distances, spawn_distances=data.spawn_distances,
            risk=data.risk, config=self.config,
        )
        return planner.find_loops(should_stop=draft_budget_exhausted, limit=settings.REPORT_LIMIT)

    def _create_plan(self, loops, data: PlanningData) -> DraftPlan:
        if loops:
            primary = route_plan_for(loops[0], data)
        else:
            # Keep a valid small plan even if search hit its fuel guard at entry.
            camp_index = min(range(len(data.camps)), key=lambda index: (
                not bool(data.camps[index].gems),
                data.spawn_distances[index] + data.camps[index].service_turns,
            ))
            altar = data.altars[0].position
            primary = RoutePlan((altar.x, altar.y), (data.camps[camp_index].anchor,))
        alternatives = tuple(route_plan_for(loop, data) for loop in loops[1:])
        return DraftPlan(primary, self.roster, alternatives)

    def _build_report_payload(self, loops, data: PlanningData) -> dict:
        loop_reports = []
        for loop in loops:
            route = route_plan_for(loop, data)
            evaluation = loop.evaluation
            loop_reports.append({
                "altar": list(route.altar), "camps": [list(point) for point in route.camps],
                "gems": evaluation.gems, "gold": evaluation.gold,
                "travel": evaluation.travel_turns, "clear_capture": evaluation.service_turns,
                "tribute": evaluation.tribute_turns,
                "respawn_wait": evaluation.period - evaluation.active_turns,
                "period": evaluation.period, "first_deposit": evaluation.first_deposit,
                "gems_per_turn": evaluation.gems / evaluation.period, "score": evaluation.score,
                "risk": evaluation.risk, "risk_multiplier": evaluation.risk_multiplier,
                "base_score": evaluation.base_score,
            })
        return {"roster": list(self.roster), "risk_tolerance": self.config.risk_tolerance, "loops": loop_reports}

    def _publish_report(self, loops, data: PlanningData) -> None:
        payload = self._build_report_payload(loops, data)
        print(f"Squad loop candidates (approximate; risk tolerance {self.config.risk_tolerance:.2f}):")
        for rank, loop in enumerate(payload["loops"], 1):
            order = " -> ".join(str(tuple(point)) for point in loop["camps"])
            print(f"#{rank}: altar {tuple(loop['altar'])} -> {order} -> altar")
            print(f"  {loop['gems']} gems + {loop['gold']} gold | travel {loop['travel']}, "
                  f"clear/capture {loop['clear_capture']}, tribute {loop['tribute']}, "
                  f"respawn wait {loop['respawn_wait']}")
            print(f"  period {loop['period']}, first deposit ~{loop['first_deposit']}, "
                  f"gems/turn {loop['gems_per_turn']:.3f}, adjusted score {loop['score']:.3f}")
            print(f"  risk {loop['risk']:.1%}, multiplier {loop['risk_multiplier']:.3f}, "
                  f"base score {loop['base_score']:.3f}")
        # Avoid a heavyweight JSON encoder inside the fuel-metered bot.
        print(settings.REPORT_MARKER + repr(payload), flush=True)
