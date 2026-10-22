"""Golden results captured BEFORE the readability refactor, not regenerated."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan_memory import DraftPlan, RoutePlan
from planner import CampGroupInfo, LoopPlanner, RiskProfile
from settings import SearchConfig


class RegressionTests(unittest.TestCase):
    def test_deterministic_search_matches_original_rankings_and_scores(self):
        camps = [CampGroupInfo((index, 0), 10 + index, 20 * index, 5 + index, 40 + 10 * index)
                 for index in range(4)]
        distances = [[abs(origin - destination) * 3 for destination in range(4)]
                     for origin in range(4)]
        planner = LoopPlanner(
            camps, distances, [[1, 2, 3, 4], [4, 3, 2, 1]], [1, 2, 3, 4],
            config=SearchConfig(max_expansions=2000),
            risk=RiskProfile((0.1, 0.3, 0.6, 0.9), (0.05, 0.8)),
        )
        loops = planner.find_loops()
        expected_routes = [(3, 2, 1, 0), (2, 1, 0), (3, 2, 1), (3, 2, 0), (3, 1, 0)]
        expected_scores = [
            0.4435476892822025, 0.41120192907329656, 0.35919900566220136,
            0.3494501118157032, 0.3477567555125904,
        ]
        self.assertEqual([loop.altar_index for loop in loops], [0] * 5)
        self.assertEqual([loop.camp_indices for loop in loops], expected_routes)
        for loop, score in zip(loops, expected_scores):
            self.assertAlmostEqual(loop.evaluation.score, score, places=14)
        best = loops[0].evaluation
        self.assertEqual((best.gems, best.gold), (46, 120))
        self.assertEqual((best.active_turns, best.period, best.first_deposit), (45, 78, 45))
        self.assertEqual((best.travel_turns, best.service_turns, best.tribute_turns), (14, 26, 5))
        self.assertAlmostEqual(best.risk, 0.2791666666666667, places=14)
        self.assertAlmostEqual(best.risk_multiplier, 0.7766666666666666, places=14)
        self.assertAlmostEqual(best.base_score, 0.5710914454277286, places=14)

    def test_sql2_memory_format_is_byte_for_byte_unchanged(self):
        original = bytes.fromhex("53514c3205060200030a0802010203040107080100090a")
        plan = DraftPlan(
            RoutePlan((5, 6), ((1, 2), (3, 4))), (10, 8, 2),
            (RoutePlan((7, 8), ((9, 10),)),),
        )
        self.assertEqual(plan.encode(), original)
        self.assertEqual(DraftPlan.decode(original), plan)


if __name__ == "__main__":
    unittest.main()
