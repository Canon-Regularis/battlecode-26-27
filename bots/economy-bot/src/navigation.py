"""Native terrain-distance helpers for the draft planner."""

import cambc
from cambc import game_map


def around(position, radius):
    result = cambc.Bitboard()
    result.draw_chebyshev(position, radius)
    return result


def terrain():
    return (game_map.walls() | game_map.holes() | game_map.altars()
            | game_map.spawn_region(cambc.Team.ENEMY))


def distance_field(goals, blocked=None):
    blocked = terrain() if blocked is None else blocked
    roots = goals & ~blocked
    field, visited = cambc.DistanceField(), cambc.Bitboard()
    field.compute(blocked, roots, visited)
    return field, visited


def enemy_spawn_field(blocked):
    """Distances to legal enemy-spawn approaches; add one to reach spawn.

    Enemy spawn itself is blocked for us, so it must not be used as BFS roots.
    """
    approaches = cambc.Bitboard()
    for position in game_map.spawn_region(cambc.Team.ENEMY).positions():
        approaches |= around(position, 1)
    return distance_field(approaches, blocked)


def distance_to(field_and_visited, positions):
    field, visited = field_and_visited
    return min((field.get(p) for p in positions if visited.is_set(p)), default=-1)
