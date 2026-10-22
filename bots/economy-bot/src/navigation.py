"""Static terrain distances for draft planning; this module never moves units."""

from __future__ import annotations

from dataclasses import dataclass

import cambc
from cambc import game_map

from planner import positional_risk


@dataclass(frozen=True)
class DistanceMap:
    field: cambc.DistanceField
    visited: cambc.Bitboard

    def distance_at(self, position: cambc.Vec2) -> int:
        """Return -1 instead of the SDK sentinel for an unreachable tile."""
        return self.field.get(position) if self.visited.is_set(position) else -1

    def nearest_distance(self, positions) -> int:
        return min((self.field.get(position) for position in positions
                    if self.visited.is_set(position)), default=-1)


def tiles_within(position: cambc.Vec2, radius: int) -> cambc.Bitboard:
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def blocked_terrain() -> cambc.Bitboard:
    return (game_map.walls() | game_map.holes() | game_map.altars()
            | game_map.spawn_region(cambc.Team.ENEMY))


def build_distance_map(goals: cambc.Bitboard, blocked: cambc.Bitboard) -> DistanceMap:
    """Compute native eight-direction BFS from legal goal tiles."""
    roots = goals & ~blocked
    field, visited = cambc.DistanceField(), cambc.Bitboard()
    field.compute(blocked, roots, visited)
    return DistanceMap(field, visited)


def build_enemy_spawn_map(blocked: cambc.Bitboard) -> DistanceMap:
    """Use legal approaches because enemy spawn itself is forbidden terrain."""
    approaches = cambc.Bitboard()
    for position in game_map.spawn_region(cambc.Team.ENEMY).positions():
        approaches |= tiles_within(position, 1)
    return build_distance_map(approaches, blocked)


def spawn_risk_at(position: cambc.Vec2, ally: DistanceMap, enemy: DistanceMap) -> float:
    ally_distance = ally.distance_at(position)
    enemy_distance = enemy.distance_at(position)
    # The enemy field stops one legal step short of the actual spawn region.
    if enemy_distance >= 0:
        enemy_distance += 1
    return positional_risk(ally_distance, enemy_distance)
