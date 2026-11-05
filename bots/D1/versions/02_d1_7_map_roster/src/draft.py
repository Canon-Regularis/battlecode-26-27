"""Deterministic composition policy, separate from match tactics."""

import cambc


# D1 keeps G3's proven roster on maps where it won the direct mirror, and uses
# the measured Cassi/Issac + Stellar + Tavi economy roster on maps where that
# composition improved the two-side secured-gem result against G3.
STANDARD_ORDER = (10, 9, 8, 0, 2, 3, 6, 1, 5, 7, 4)
META_ORDER = (3, 4, 10, 2, 9, 0, 6, 7, 1, 5, 8)
META_SIGNATURES = {
    (41, 41, 84),   # Collision
    (80, 80, 224),  # Expanse
    (50, 50, 98),   # Monolith
    (31, 31, 0),    # Packs
    (50, 50, 214),  # Rows
}
PICK_TO_TYPES = {
    0: (0,), 1: (1,), 2: (2,), 3: (3, 4), 4: (5,), 5: (6,),
    6: (7,), 7: (8,), 8: (9,), 9: (10,), 10: (11,),
}


def play():
    chosen = list(cambc.draft.current_draft(cambc.Team.ALLY))
    signature = (cambc.game_map.width(), cambc.game_map.height(),
                 cambc.game_map.walls().count())
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
