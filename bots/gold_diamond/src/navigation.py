"""Goal-set navigation using the SDK's legal terrain and distance field."""

import cambc
from cambc import game_map, vision
from world import distance


def occupied_blocked(world, me):
    result = (world.static_blocked | vision.champion_tiles()
              | vision.camp_tiles() | vision.teleport_tiles())
    result.set(me.position(), False)
    return result


def ring_goals(centres, radius):
    result = cambc.Bitboard()
    for centre in centres:
        local = cambc.Bitboard()
        local.draw_chebyshev(centre, radius)
        result |= local
    return result


def move_to_goals(me, world, goals, enemies=(), forbidden=None):
    """Take a decreasing-distance legal step, retrying hidden collisions."""
    if not me.can_move():
        return False
    origin = me.position()
    blocked = occupied_blocked(world, me)
    if forbidden is not None:
        blocked |= forbidden
        blocked.set(origin, False)
    roots = goals & ~blocked
    if roots.is_empty() or roots.is_set(origin):
        return False
    field = cambc.DistanceField()
    destinations = cambc.Bitboard()
    destinations.set(origin)
    field.compute_to(blocked, roots, destinations, cambc.Bitboard())
    current_distance = field.get(origin)
    if current_distance >= 250:
        return False
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)
    steps = [p for p in reachable.positions() if p != origin
             and field.get(p) < current_distance]
    def score(tile):
        threat = 0
        for enemy in enemies:
            try:
                if enemy.is_visible() and enemy.is_alive() and distance(tile, enemy.position()) <= enemy.attack_range() + 1:
                    threat += 3
            except cambc.Error:
                continue
        return (field.get(tile) + threat, field.get(tile), tile.y, tile.x)
    for tile in sorted(steps, key=score):
        try:
            if me.move_absolute(tile):
                return True
        except cambc.Error:
            continue
    return False


def move_to_tile(me, world, target, enemies=(), forbidden=None):
    goals = cambc.Bitboard()
    goals.set(target)
    return move_to_goals(me, world, goals, enemies, forbidden)


def best_retreat_step(me, world, enemies):
    if not me.can_move():
        return False
    origin = me.position()
    blocked = occupied_blocked(world, me)
    candidates = blocked.reachable_tiles(origin, me.base_stats().base_move_speed).positions()
    if not candidates:
        return False
    def risk(tile):
        enemy_risk = 0.0
        for enemy in enemies:
            try:
                if enemy.is_visible() and enemy.is_alive():
                    enemy_risk += (max(0, enemy.attack_range() + 2 - distance(tile, enemy.position()))
                                   * max(1, enemy.strength()))
            except cambc.Error:
                continue
        home = min(distance(tile, s) for s in world.own_cells)
        return (enemy_risk, home, tile.y, tile.x)
    for tile in sorted(candidates, key=risk):
        if risk(tile) >= risk(origin):
            break
        try:
            if me.move_absolute(tile):
                return True
        except cambc.Error:
            continue
    return False

