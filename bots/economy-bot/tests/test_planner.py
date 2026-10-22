"""Pure scoring/search tests. Run: uv run python -m unittest discover -s bots/economy-bot/tests"""

from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from planner import CampGroupInfo, LoopPlanner, RiskProfile, positional_risk
from settings import RISK_TOLERANCE, SearchConfig


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.camps = [CampGroupInfo((1, 1), 10, 20, 6, 40), CampGroupInfo((5, 1), 20, 40, 7, 60)]
        self.distances = [[0, 4], [4, 0]]
        self.altars = [[3, 2]]
        self.spawn = [7, 8]

    def evaluate(self, route=(0, 1), **kwargs):
        planner = LoopPlanner(self.camps, self.distances, self.altars, self.spawn, **kwargs)
        return planner.evaluate_loop(route, 0)

    def test_counts_team_rewards_once(self):
        result = self.evaluate()
        self.assertEqual((result.gems, result.gold), (30, 60))
        self.assertEqual(result.travel_turns, 9)
        self.assertEqual(result.service_turns, 13)
        self.assertEqual(result.tribute_turns, 3)
        self.assertEqual(result.active_turns, 25)

    def test_respawn_includes_service_after_respawning(self):
        self.assertEqual(self.evaluate().period, 67)

    def test_opening_starts_at_spawn_not_altar(self):
        self.assertEqual(self.evaluate().first_deposit, 29)

    def test_unreachable_leg_is_rejected(self):
        self.distances[0][1] = -1
        self.assertIsNone(self.evaluate())

    def test_unreachable_spawn_is_rejected(self):
        self.spawn[0] = -1
        self.assertIsNone(self.evaluate())

    def test_empty_route_is_not_scored(self):
        self.assertIsNone(self.evaluate(()))

    def test_gold_weight_is_explicit(self):
        plain = self.evaluate(config=SearchConfig(gold_weight=0))
        economy = self.evaluate(config=SearchConfig(gold_weight=1))
        self.assertGreater(economy.score, plain.score)

    def test_extra_camp_can_fill_existing_respawn_wait(self):
        camps = [CampGroupInfo((1, 1), 10, 0, 5, 100), CampGroupInfo((2, 1), 10, 0, 5, 100)]
        planner = LoopPlanner(camps, [[0, 1], [1, 0]], [[1, 1]], [1, 1])
        one = planner.evaluate_loop((0,), 0)
        two = planner.evaluate_loop((0, 1), 0)
        self.assertEqual(one.period, two.period)
        self.assertGreater(two.score, one.score)

    def test_gold_only_route_does_not_channel_empty_bag(self):
        self.camps[0] = replace(self.camps[0], gems=0)
        self.assertEqual(self.evaluate((0,)).tribute_turns, 0)

    def test_default_risk_tolerance_is_point_two(self):
        self.assertEqual(RISK_TOLERANCE, 0.2)
        self.assertEqual(SearchConfig().risk_tolerance, 0.2)

    def test_invalid_risk_tolerance_is_rejected(self):
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SearchConfig(risk_tolerance=value)

    def test_positional_risk_increases_toward_enemy_spawn(self):
        self.assertEqual(positional_risk(0, 20), 0)
        self.assertEqual(positional_risk(10, 10), 0.5)
        self.assertEqual(positional_risk(20, 0), 1)
        self.assertLess(positional_risk(4, 16), positional_risk(16, 4))

    def test_positional_risk_handles_disconnected_regions(self):
        self.assertEqual(positional_risk(20, -1), 0)
        self.assertEqual(positional_risk(-1, 20), 1)
        self.assertEqual(positional_risk(-1, -1), 0.5)
        self.assertEqual(positional_risk(0, 0), 0.5)

    def test_time_weighted_risk_includes_service_travel_tribute_and_wait(self):
        result = self.evaluate(risk=RiskProfile((0.2, 0.8), (0.1,)))
        # Travel 3.35; service 6.8; tribute .3; respawn waiting at altar 4.2.
        self.assertAlmostEqual(result.risk, (3.35 + 6.8 + 0.3 + 4.2) / 67)
        self.assertAlmostEqual(result.risk_multiplier, 1 - 0.8 * result.risk)
        self.assertAlmostEqual(result.score, result.base_score * result.risk_multiplier)

    def test_uniform_risk_stays_uniform_after_time_weighting(self):
        result = self.evaluate(risk=RiskProfile((0.6, 0.6), (0.6,)))
        self.assertAlmostEqual(result.risk, 0.6)
        self.assertAlmostEqual(result.risk_multiplier, 0.52)

    def test_tolerance_one_disables_penalty_but_still_reports_risk(self):
        result = self.evaluate(config=SearchConfig(risk_tolerance=1),
                               risk=RiskProfile((0.8, 0.8), (0.8,)))
        self.assertAlmostEqual(result.risk, 0.8)
        self.assertEqual(result.risk_multiplier, 1)
        self.assertEqual(result.score, result.base_score)

    def test_tolerance_zero_applies_strongest_penalty(self):
        result = self.evaluate(config=SearchConfig(risk_tolerance=0),
                               risk=RiskProfile((0.8, 0.8), (0.8,)))
        self.assertAlmostEqual(result.risk_multiplier, 0.2)

    def test_increasing_tolerance_raises_risky_routes_score(self):
        risk = RiskProfile((0.8, 0.8), (0.8,))
        conservative = self.evaluate(config=SearchConfig(risk_tolerance=0.2), risk=risk)
        tolerant = self.evaluate(config=SearchConfig(risk_tolerance=0.8), risk=risk)
        self.assertGreater(tolerant.score, conservative.score)
        self.assertEqual(tolerant.base_score, conservative.base_score)

    def test_safest_route_has_no_penalty(self):
        result = self.evaluate(risk=RiskProfile((0, 0), (0,)))
        self.assertEqual(result.risk, 0)
        self.assertEqual(result.score, result.base_score)


class SearchTests(unittest.TestCase):
    def test_returns_ranked_distinct_camp_sets(self):
        camps = [CampGroupInfo((index, 0), 10 + index, 0, 5, 40) for index in range(4)]
        matrix = [[abs(origin - destination) for destination in range(4)] for origin in range(4)]
        loops = LoopPlanner(camps, matrix, [[1, 2, 3, 4]], [1, 2, 3, 4]).find_loops()
        scores = [loop.evaluation.score for loop in loops]
        self.assertEqual(scores, sorted(scores, reverse=True))
        keys = [(loop.altar_index, frozenset(loop.camp_indices)) for loop in loops]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreater(len(loops), 1)
        self.assertTrue(all(len(loop.camp_indices) == len(set(loop.camp_indices)) for loop in loops))

    def test_considers_later_altar_with_small_budget(self):
        camps = [CampGroupInfo((1, 1), 10, 0, 5, 0)]
        result = LoopPlanner(camps, [[0]], [[100], [1]], [1],
                             config=SearchConfig(max_expansions=2)).find_best_loop()
        self.assertEqual(result.altar_index, 1)

    def test_longer_cluster_can_beat_profitable_single_camp(self):
        camps = [CampGroupInfo((index, 1), 10, 0, 5, 80) for index in range(3)]
        result = LoopPlanner(camps, [[0, 1, 2], [1, 0, 1], [2, 1, 0]],
                             [[2, 3, 4]], [1, 2, 3]).find_best_loop()
        self.assertEqual(len(result.camp_indices), 3)

    def test_fuel_guard_stops_cleanly(self):
        planner = LoopPlanner([CampGroupInfo((1, 1), 10, 0, 5, 0)], [[0]], [[1]], [1])
        result = planner.find_loops(should_stop=lambda: True)
        self.assertEqual(result, [])

    def test_expansion_limit_stops_cleanly(self):
        camps = [CampGroupInfo((1, 1), 10, 0, 5, 0)]
        planner = LoopPlanner(camps, [[0]], [[1]], [1], config=SearchConfig(max_expansions=0))
        self.assertEqual(planner.find_loops(), [])

    def test_gold_only_camps_do_not_become_scoring_loops(self):
        camps = [CampGroupInfo((1, 1), 0, 100, 5, 0)]
        self.assertIsNone(LoopPlanner(camps, [[0]], [[1]], [1]).find_best_loop())

    def test_empty_map_and_missing_altars(self):
        self.assertEqual(LoopPlanner([], [], [[]], []).find_loops(), [])
        self.assertEqual(LoopPlanner([CampGroupInfo((1, 1), 10, 0, 5, 0)], [[0]], [], [1]).find_loops(), [])

    def test_risk_changes_camp_ranking_without_changing_rewards(self):
        camps = [CampGroupInfo((index, 0), 10, 0, 5, 40) for index in range(2)]
        risk = RiskProfile((0.9, 0.1), (0.5,))
        args = (camps, [[0, 2], [2, 0]], [[1, 1]], [1, 1])
        conservative = LoopPlanner(*args, config=SearchConfig(max_camps=1), risk=risk).find_best_loop()
        tolerant = LoopPlanner(*args, config=SearchConfig(max_camps=1, risk_tolerance=1), risk=risk).find_best_loop()
        self.assertEqual(conservative.camp_indices, (1,))
        self.assertEqual(tolerant.camp_indices, (0,))
        self.assertEqual(conservative.evaluation.gems, tolerant.evaluation.gems)

    def test_risk_changes_altar_choice_for_identical_camp(self):
        camps = [CampGroupInfo((1, 1), 10, 0, 5, 40)]
        result = LoopPlanner(camps, [[0]], [[1], [1]], [1],
                             risk=RiskProfile((0.5,), (0.9, 0.1))).find_best_loop()
        self.assertEqual(result.altar_index, 1)

    def test_repeated_search_does_not_keep_a_previous_frontier_or_budget(self):
        camps = [CampGroupInfo((index, 0), 10, 0, 5, 40) for index in range(3)]
        planner = LoopPlanner(camps, [[0, 1, 2], [1, 0, 1], [2, 1, 0]], [[1, 2, 3]], [1, 2, 3])
        expected = planner.find_loops()
        self.assertEqual(planner.find_loops(should_stop=lambda: True), [])
        self.assertEqual(planner.find_loops(), expected)
        self.assertEqual(planner.find_best_loop(), expected[0])

    def test_input_tables_are_not_mutated_by_search(self):
        camps = [CampGroupInfo((1, 1), 10, 0, 5, 40)]
        distances, altars, spawn = [[0]], [[1]], [2]
        planner = LoopPlanner(camps, distances, altars, spawn)
        planner.find_loops()
        self.assertEqual(camps, [CampGroupInfo((1, 1), 10, 0, 5, 40)])
        self.assertEqual((distances, altars, spawn), ([[0]], [[1]], [2]))


if __name__ == "__main__":
    unittest.main()
