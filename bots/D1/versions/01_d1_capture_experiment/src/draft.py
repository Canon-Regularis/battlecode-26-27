"""Small deterministic economic roster, independent of the G3 draft module."""

import cambc


# Tavi enables field investment; Varg has grouped-camp potential; Ren supplies
# robust single-target clear. This is a conservative starting roster to isolate
# D1's economic algorithm from linked-death risk.
ORDER = (10, 9, 8, 0, 2, 3, 6, 1, 5, 7, 4)
SELECTION_BODIES = {
    0: (0,), 1: (1,), 2: (2,), 3: (3, 4), 4: (5,), 5: (6,),
    6: (7,), 7: (8,), 8: (9,), 9: (10,), 10: (11,),
}


def play():
    selected = list(cambc.draft.current_draft(cambc.Team.ALLY))
    choice = next((pick for pick in ORDER if pick not in selected), None)
    if choice is None:
        raise RuntimeError("all draft selections are already used")
    bodies = [kind for pick in (*selected, choice)
              for kind in SELECTION_BODIES[int(pick)]]
    # D1 protocol marker and roster; currently only diagnostic/static metadata.
    cambc.draft_memory.submit(b"D1" + bytes((len(bodies), *bodies)))
    cambc.draft.pick(choice)
