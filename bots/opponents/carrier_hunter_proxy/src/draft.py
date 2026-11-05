"""Deterministic composition policy, separate from match tactics."""

import cambc


# Hold the draft constant with G2 so this proxy isolates combat behavior.
PICK_ORDER = (10, 9, 8, 0, 2, 3, 6, 1, 5, 7, 4)
PICK_TO_TYPES = {
    0: (0,), 1: (1,), 2: (2,), 3: (3, 4), 4: (5,), 5: (6,),
    6: (7,), 7: (8,), 8: (9,), 9: (10,), 10: (11,),
}


def play():
    chosen = list(cambc.draft.current_draft(cambc.Team.ALLY))
    available = [pick for pick in PICK_ORDER if pick not in chosen]
    if not available:
        raise RuntimeError("no unpicked champion remains")
    pick = available[0]
    roster = [kind for selection in (*chosen, pick)
              for kind in PICK_TO_TYPES[int(selection)]]
    # LB2, body count, then each drafted ChampionType in stable draft order.
    cambc.draft_memory.submit(b"LB2" + bytes((len(roster), *roster)))
    cambc.draft.pick(pick)
