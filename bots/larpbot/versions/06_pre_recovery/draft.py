"""Deterministic composition policy, kept separate from match tactics."""

import cambc


# One draft selection for Cassi & Issac creates two independently acting bodies.
# The first three choices are the initial WHIM-inspired proxy; this is a test
# roster, not a claim that it is optimal. Additional slots test coverage.
# Integer values follow the checked-in ChampionDraft definition. Passing the
# native integer also matches the starter's documented `draft.pick` usage.
PICK_ORDER = (2, 9, 0, 3, 10, 6, 8, 4, 7, 1, 5)


def play():
    chosen = {int(candidate) for candidate in cambc.draft.current_draft(cambc.Team.ALLY)}
    pick = next((candidate for candidate in PICK_ORDER if candidate not in chosen), None)
    if pick is None:
        raise RuntimeError("no unpicked champion remains")

    # Match the starter SDK contract: commit draft metadata before the pick.
    cambc.draft_memory.submit(b"larpbot-stage1-v1")
    cambc.draft.pick(int(pick))
    print(f"LARP_DRAFT|{int(pick)}", flush=True)
