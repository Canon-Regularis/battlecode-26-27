"""Draft entry point: select champions, save the shared plan, and make a pick.

Map preparation and route planning live in draft_planner.py.
"""

from __future__ import annotations

import cambc

import settings
from draft_planner import DraftPlanner
from visualization import draw_plan


def champion_types_for_picks(picks) -> tuple[cambc.ChampionType, ...]:
    """Draft choices and champion bodies use different SDK enums."""
    pick, champion = cambc.ChampionDraft, cambc.ChampionType
    bodies_by_pick = {
        pick.RYTH: (champion.RYTH,),
        pick.VESPER_VALE: (champion.VESPER_VALE,),
        pick.VENDETTA: (champion.VENDETTA,),
        pick.CASSI_AND_ISSAC: (champion.CASSI, champion.ISSAC),
        pick.STELLAR: (champion.STELLAR,),
        pick.PRISM: (champion.PRISM,),
        pick.MARCELLA: (champion.MARCELLA,),
        pick.WILLOW: (champion.WILLOW,),
        pick.REN: (champion.REN,),
        pick.VARG: (champion.VARG,),
        pick.TAVI: (champion.TAVI,),
    }
    return tuple(body for choice in picks for body in bodies_by_pick[choice])


def planned_draft_picks(chosen: list[cambc.ChampionDraft]) -> tuple[cambc.ChampionDraft, ...]:
    preferred: list[cambc.ChampionDraft] = [
        getattr(cambc.ChampionDraft, name) for name in settings.PREFERRED_PICKS
    ]
    available = [choice for choice in preferred if choice not in chosen]
    remaining = cambc.draft.team_size() - len(chosen)
    return tuple(chosen) + tuple(available[:remaining])


def play() -> None:
    chosen = cambc.draft.current_draft(cambc.Team.ALLY)
    picks = planned_draft_picks(chosen)
    if not chosen:
        # Only this draft turn has the large compute budget. All champion bots
        # receive the same immutable plan later for their drawing overlays.
        roster = champion_types_for_picks(picks)
        print("Planning squad body types:", roster, flush=True)
        planner = DraftPlanner(roster)
        cambc.draft_memory.submit(planner.fallback_plan().encode())
        plan = planner.build()
        cambc.draft_memory.submit(plan.encode())
        draw_plan(plan)
    cambc.draft.pick(picks[len(chosen)])
