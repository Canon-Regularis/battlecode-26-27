"""Draft ordering, readable champion mappings, and report/plan assembly."""

from enum import IntEnum
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import get_type_hints
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan_memory import DraftPlan, RoutePlan
from planner import CampGroupInfo, RiskProfile
from settings import DEFAULT_SEARCH_CONFIG, PRECOMPUTE_RESERVE
from sdk_fakes import fake_sdk, load_game_modules


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.sdk = fake_sdk()
        modules = load_game_modules(self.sdk)
        self.draft = modules.draft
        self.planning = modules.draft_planner
        self.planner = self.planning.DraftPlanner((10, 8, 2))

    def test_entry_point_imports_planner_from_separate_module(self):
        self.assertEqual(self.planner.__class__.__module__, "draft_planner")
        self.assertIs(self.draft.DraftPlanner, self.planning.DraftPlanner)
        self.assertFalse(hasattr(self.draft, "PlanningData"))

    def test_maps_draft_ids_to_body_ids_including_linked_pair(self):
        self.assertEqual(self.draft.champion_types_for_picks(range(11)), tuple(range(12)))

    def test_assumed_squad_matches_subsequent_picks(self):
        self.assertEqual(self.draft.planned_draft_picks([]), (9, 7, 2))
        self.assertEqual(self.draft.planned_draft_picks([9]), (9, 7, 2))
        self.assertEqual(self.draft.planned_draft_picks([9, 7]), (9, 7, 2))

    def test_helper_annotations_preserve_sdk_enum_types(self):
        # Runtime SDK values act like integers, but editors use distinct enums.
        # Keep those types at the pick() and Champion.design() boundaries.
        self.sdk.ChampionDraft = IntEnum("ChampionDraft", vars(self.sdk.ChampionDraft))
        self.sdk.ChampionType = IntEnum("ChampionType", vars(self.sdk.ChampionType))
        pick_hints = get_type_hints(self.draft.planned_draft_picks)
        self.assertEqual(pick_hints["chosen"], list[self.sdk.ChampionDraft])
        self.assertEqual(pick_hints["return"], tuple[self.sdk.ChampionDraft, ...])
        body_hints = get_type_hints(self.draft.champion_types_for_picks)
        self.assertEqual(body_hints["return"], tuple[self.sdk.ChampionType, ...])

    def test_pick_happens_after_plan_is_published(self):
        plan = DraftPlan(RoutePlan((1, 1), ((2, 2),)), (10, 8, 2))
        events = []
        self.sdk.draft_memory.submit.side_effect = lambda data: events.append("publish")
        self.sdk.draft.pick.side_effect = lambda pick: events.append(("pick", pick))
        with patch.object(self.draft.DraftPlanner, "fallback_plan", return_value=plan), \
                patch.object(self.draft.DraftPlanner, "build", return_value=plan), \
                patch.object(self.draft, "draw_plan", side_effect=lambda plan: events.append("draw")), \
                patch("builtins.print"):
            self.draft.play()
        self.assertEqual(events, ["publish", "publish", "draw", ("pick", 9)])

    def test_later_picks_do_not_recompute_plan(self):
        self.sdk.draft.current_draft = lambda team: [9]
        with patch.object(self.draft.DraftPlanner, "build") as build_plan:
            self.draft.play()
        build_plan.assert_not_called()
        self.sdk.draft.pick.assert_called_once_with(7)

    def planning_data(self):
        altar = self.planning.CandidateAltar(SimpleNamespace(x=5, y=6), None, 1)
        return self.planning.PlanningData(
            camps=[CampGroupInfo((1, 2), 10, 20, 6, 40)], altars=[altar],
            distances=[[0]], altar_distances=[[3]], spawn_distances=[7],
            risk=RiskProfile((0.2,), (0.1,)),
        )

    def test_search_indices_become_saved_route_coordinates(self):
        data = self.planning_data()
        loops = self.planner._search(data)
        plan = self.planner._create_plan(loops, data)
        self.assertEqual(plan.primary, RoutePlan((5, 6), ((1, 2),)))

    def test_empty_search_still_has_a_valid_fallback(self):
        plan = self.planner._create_plan([], self.planning_data())
        self.assertEqual(plan.primary, RoutePlan((5, 6), ((1, 2),)))

    def test_report_preserves_public_fields(self):
        data = self.planning_data()
        loops = self.planner._search(data)
        report = self.planner._build_report_payload(loops, data)
        self.assertEqual(report["risk_tolerance"], 0.2)
        self.assertEqual(report["loops"][0]["camps"], [[1, 2]])
        self.assertAlmostEqual(report["loops"][0]["score"], loops[0].evaluation.score)

    def prepare_with_fuel(self, fuel_levels):
        self.sdk.Vec2 = lambda x, y: SimpleNamespace(x=x, y=y)
        self.sdk.fuel_remaining = MagicMock(side_effect=fuel_levels)
        candidates = [self.planning.CandidateCamp(
            CampGroupInfo((index, 1), 10, 0, 5, 40), 1, index + 1, 0.1 * index,
        ) for index in range(3)]
        altar = self.planning.CandidateAltar(
            self.sdk.Vec2(5, 6), SimpleNamespace(positions=lambda: [self.sdk.Vec2(4, 6)]), 1,
        )
        ally = SimpleNamespace(visited=SimpleNamespace(is_set=lambda position: True))
        field = SimpleNamespace(distance_at=lambda position: position.x)
        with patch.object(self.planning, "build_distance_map", return_value=field), \
                patch.object(self.planning, "spawn_risk_at", return_value=0.2), \
                patch.object(self.planning, "tiles_within"), patch("builtins.print"):
            context = self.planning.DraftMapContext([], (), None, ally, None)
            return self.planner._prepare_data(context, candidates, [altar])

    def test_partial_bfs_keeps_all_indices_and_profiles_aligned(self):
        reserve = PRECOMPUTE_RESERVE
        data = self.prepare_with_fuel([
            reserve + 10_000_000, reserve + 9_000_000,
            reserve + 1_000_000, reserve, reserve - 1_000_000,
        ])
        self.assertEqual(len(data.camps), 1)
        self.assertEqual(data.distances, [[0]])
        self.assertEqual(data.altar_distances, [[0]])
        self.assertEqual(data.spawn_distances, [1])
        self.assertEqual(data.risk.camps, (0.0,))
        self.assertEqual(data.risk.altars, (0.2,))

    def test_no_camp_bfs_still_supports_singleton_search(self):
        reserve = PRECOMPUTE_RESERVE
        data = self.prepare_with_fuel([reserve + 10_000_000, reserve + 9_000_000, reserve - 1_000_000])
        self.assertEqual(len(data.camps), 1)
        self.assertEqual(data.distances, [[0]])
        self.assertEqual(len(data.altar_distances[0]), 1)

    def test_bfs_guard_reserves_cost_of_next_native_search(self):
        reserve = PRECOMPUTE_RESERVE
        data = self.prepare_with_fuel([reserve + 10_000_000, reserve + 9_000_000, reserve + 500_000])
        # Fuel is above the reserve, but another estimated 1M BFS would eat it.
        self.assertEqual(data.distances, [[0]])
        self.assertEqual(len(data.camps), 1)


if __name__ == "__main__":
    unittest.main()
