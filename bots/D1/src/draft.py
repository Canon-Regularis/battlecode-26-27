"""Deterministic composition policy, separate from match tactics."""

import cambc


# D1 keeps G3's proven roster where it already wins and uses measured
# map-and-side lineups where the standard composition loses gathering tempo.
STANDARD_ORDER = (10, 9, 8, 0, 2, 3, 6, 1, 5, 7, 4)
META_ORDER = (3, 4, 10, 2, 9, 0, 6, 7, 1, 5, 8)
CIV_ORDER = (3, 9, 2, 10, 0, 8, 4, 6, 1, 5, 7)
REORDERED_CIV_ORDER = (3, 2, 9, 10, 0, 8, 4, 6, 1, 5, 7)
CORNERS_B_ORDER = (0, 3, 10, 9, 4, 2, 8, 6, 1, 5, 7)
META_SIGNATURES = {
    (41, 41, 84),   # Collision
    (80, 80, 224),  # Expanse
    (50, 50, 98),   # Monolith
    (31, 31, 0),    # Packs
    (50, 50, 214),  # Rows
}
# Bounding boxes of Team A's spawn region, keyed by the same public map
# geometry signature. This is static map state and is available during draft.
TEAM_A_SPAWNS = {
    (41, 41, 84): (3, 1, 5, 3),      # Collision
    (71, 71, 44): (13, 33, 15, 35),  # Corners
    (30, 30, 0): (0, 0, 2, 2),       # Elkring
    (80, 80, 224): (3, 2, 6, 5),     # Expanse
    (40, 40, 76): (0, 0, 2, 2),      # Interlock
    (90, 30, 0): (2, 12, 4, 14),     # Lanes
    (50, 50, 98): (2, 45, 4, 47),    # Monolith
    (31, 31, 0): (0, 0, 2, 2),       # Packs
    (50, 50, 214): (2, 2, 5, 5),     # Rows
}
CIV_CASES = {
    ((41, 41, 84), True),       # Collision A
    ((30, 30, 0), True),        # Elkring A
    ((30, 30, 0), False),       # Elkring B
    ((80, 80, 224), False),     # Expanse B
    ((90, 30, 0), True),        # Lanes A
    ((90, 30, 0), False),       # Lanes B
    ((50, 50, 98), True),       # Monolith A
    ((31, 31, 0), True),        # Packs A
}
HIGH_COVERAGE_CASES = {
    ((30, 30, 0), True),        # Elkring A
    ((90, 30, 0), False),       # Lanes B
    ((50, 50, 98), True),       # Monolith A
}
PICK_TO_TYPES = {
    0: (0,), 1: (1,), 2: (2,), 3: (3, 4), 4: (5,), 5: (6,),
    6: (7,), 7: (8,), 8: (9,), 9: (10,), 10: (11,),
}


def play():
    chosen = list(cambc.draft.current_draft(cambc.Team.ALLY))
    signature = (cambc.game_map.width(), cambc.game_map.height(),
                 cambc.game_map.walls().count())
    spawn = cambc.game_map.spawn_region(cambc.Team.ALLY).positions()
    spawn_bounds = (min(tile.x for tile in spawn), min(tile.y for tile in spawn),
                    max(tile.x for tile in spawn), max(tile.y for tile in spawn))
    is_team_a = spawn_bounds == TEAM_A_SPAWNS.get(signature)
    if signature == (41, 41, 84) and is_team_a:
        order = REORDERED_CIV_ORDER
    elif signature == (71, 71, 44) and not is_team_a:
        order = CORNERS_B_ORDER
    elif (signature, is_team_a) in HIGH_COVERAGE_CASES:
        order = REORDERED_CIV_ORDER
    elif signature == (50, 50, 98) and not is_team_a:
        order = STANDARD_ORDER
    elif (signature, is_team_a) in CIV_CASES:
        order = CIV_ORDER
    else:
        order = META_ORDER if signature in META_SIGNATURES else STANDARD_ORDER
    available = [pick for pick in order if pick not in chosen]
    if not available:
        raise RuntimeError("no unpicked champion remains")
    pick = available[0]
    roster = [kind for selection in (*chosen, pick)
              for kind in PICK_TO_TYPES[int(selection)]]
    # LB2, body count, then each drafted ChampionType in stable draft order.
    cambc.draft_memory.submit(b"LB2" + bytes((len(roster), *roster)))
    cambc.draft.pick(pick)
