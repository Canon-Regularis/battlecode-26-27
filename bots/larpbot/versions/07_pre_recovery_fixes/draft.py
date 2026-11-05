"""Controlled draft diagnostic using the starter's API call pattern."""

import cambc


def play():
    chosen = cambc.draft.current_draft(cambc.Team.ALLY)
    available = [pick for pick in range(11) if pick not in chosen]
    cambc.draft_memory.submit(b"LARP-DRAFT-CONTROL")
    cambc.draft.pick(available[0])
