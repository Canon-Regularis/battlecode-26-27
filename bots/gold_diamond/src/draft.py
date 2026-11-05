"""Draft for economic throughput with compact roster memory."""

import cambc
from comm import pack_roster
from strategy_config import DEFAULT_PICKS, PICK_TO_TYPES


def _features():
    game_map = cambc.game_map
    area = max(1, game_map.width() * game_map.height())
    obstacles = game_map.walls().count() + game_map.holes().count()
    bushes = game_map.bushes().count()
    compact = area < 1500
    dense = obstacles / area > 0.13
    bushy = bushes / area > 0.12
    return compact, dense, bushy


def _order(own, enemies):
    compact, dense, bushy = _features()
    order = list(DEFAULT_PICKS)
    enemy_types = {int(pick) for pick in enemies}
    # Cassi/Issac's linked death is expensive against a revealed stun/burst
    # lineup. Theoretical synergy alone does not remove them from contention.
    danger = len(enemy_types & {4, 8, 10, 3}) >= 2
    if danger and 3 not in own:
        order.remove(3)
        order.insert(4, 3)
    if dense and 9 not in own:
        order.remove(9)
        order.insert(1, 9)
    if compact and 4 not in own:
        order.remove(4)
        order.insert(2, 4)
    if bushy and 8 not in own:
        order.remove(8)
        order.insert(3, 8)
    if len(enemy_types & {0, 3, 6, 8, 10}) >= 3 and 6 not in own:
        order.remove(6)
        order.insert(3, 6)
    return order


def play():
    own = [int(value) for value in cambc.draft.current_draft(cambc.Team.ALLY)]
    enemies = cambc.draft.current_draft(cambc.Team.ENEMY)
    order = _order(own, enemies)
    pick = next(value for value in order if value not in own)
    roster = tuple(kind for selection in (*own, pick)
                   for kind in PICK_TO_TYPES[selection])
    cambc.draft_memory.submit(pack_roster(roster))
    cambc.draft.pick(pick)

