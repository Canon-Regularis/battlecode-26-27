"""Run with: uv run python -m unittest discover -s bots/economy-bot/tests"""

from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inspect_loops import extract_report
from planner import (RISK_TOLERANCE, Camp, RiskProfile, SearchConfig, evaluate,
                     find_loops, positional_risk, search)
from protocol import PLAN_HEADER, Plan


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.camps = [Camp((1, 1), 10, 20, 6, 40), Camp((5, 1), 20, 40, 7, 60)]
        self.distances = [[0, 4], [4, 0]]
        self.altars = [[3, 2]]
        self.spawn = [7, 8]

    def evaluate(self, route=(0, 1), **kwargs):
        return evaluate(route, 0, self.camps, self.distances, self.altars, self.spawn, **kwargs)

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
        camps = [Camp((1, 1), 10, 0, 5, 100), Camp((2, 1), 10, 0, 5, 100)]
        one = evaluate((0,), 0, camps, [[0, 1], [1, 0]], [[1, 1]], [1, 1])
        two = evaluate((0, 1), 0, camps, [[0, 1], [1, 0]], [[1, 1]], [1, 1])
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
        # Travel: 3*.15 + 4*.5 + 2*.45 = 3.35
        # Service: 6*.2 + 7*.8 = 6.8; tribute: 3*.1 = .3
        # Respawn waiting at the altar: (67 - 25)*.1 = 4.2
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
        camps = [Camp((i, 0), 10 + i, 0, 5, 40) for i in range(4)]
        matrix = [[abs(i - j) for j in range(4)] for i in range(4)]
        loops = find_loops(camps, matrix, [[1, 2, 3, 4]], [1, 2, 3, 4])
        scores = [loop.evaluation.score for loop in loops]
        self.assertEqual(scores, sorted(scores, reverse=True))
        keys = [(loop.altar, frozenset(loop.camps)) for loop in loops]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreater(len(loops), 1)
        self.assertTrue(all(len(loop.camps) == len(set(loop.camps)) for loop in loops))

    def test_considers_later_altar_with_small_budget(self):
        camps = [Camp((1, 1), 10, 0, 5, 0)]
        result = search(camps, [[0]], [[100], [1]], [1], SearchConfig(max_expansions=2))
        self.assertEqual(result.altar, 1)

    def test_longer_cluster_can_beat_profitable_single_camp(self):
        camps = [Camp((i, 1), 10, 0, 5, 80) for i in range(3)]
        result = search(camps, [[0, 1, 2], [1, 0, 1], [2, 1, 0]], [[2, 3, 4]], [1, 2, 3])
        self.assertEqual(len(result.camps), 3)

    def test_fuel_guard_stops_cleanly(self):
        result = find_loops([Camp((1, 1), 10, 0, 5, 0)], [[0]], [[1]], [1],
                            should_stop=lambda: True)
        self.assertEqual(result, [])

    def test_expansion_limit_stops_cleanly(self):
        camps = [Camp((1, 1), 10, 0, 5, 0)]
        self.assertEqual(find_loops(camps, [[0]], [[1]], [1],
                                    SearchConfig(max_expansions=0)), [])

    def test_gold_only_camps_do_not_become_scoring_loops(self):
        camps = [Camp((1, 1), 0, 100, 5, 0)]
        self.assertIsNone(search(camps, [[0]], [[1]], [1]))

    def test_empty_map_and_missing_altars(self):
        self.assertEqual(find_loops([], [], [[]], []), [])
        self.assertEqual(find_loops([Camp((1, 1), 10, 0, 5, 0)], [[0]], [], [1]), [])

    def test_risk_changes_camp_ranking_without_changing_rewards(self):
        camps = [Camp((i, 0), 10, 0, 5, 40) for i in range(2)]
        risk = RiskProfile((0.9, 0.1), (0.5,))
        args = (camps, [[0, 2], [2, 0]], [[1, 1]], [1, 1])
        conservative = search(*args, config=SearchConfig(max_camps=1), risk=risk)
        tolerant = search(*args, config=SearchConfig(max_camps=1, risk_tolerance=1), risk=risk)
        self.assertEqual(conservative.camps, (1,))
        self.assertEqual(tolerant.camps, (0,))
        self.assertEqual(conservative.evaluation.gems, tolerant.evaluation.gems)

    def test_risk_changes_altar_choice_for_identical_camp(self):
        camps = [Camp((1, 1), 10, 0, 5, 40)]
        result = search(camps, [[0]], [[1], [1]], [1],
                        risk=RiskProfile((0.5,), (0.9, 0.1)))
        self.assertEqual(result.altar, 1)


class PlanTests(unittest.TestCase):
    def test_round_trip(self):
        plan = Plan((5, 6), ((1, 2), (3, 4)), (10, 8, 2))
        self.assertEqual(Plan.decode(plan.encode()), plan)
        self.assertLessEqual(len(plan.encode()), 1024)

    def test_round_trip_includes_alternative_drawing_routes(self):
        plan = Plan((5, 6), ((1, 2),), (10, 8, 2),
                    (((7, 8), ((3, 4), (9, 10))),))
        self.assertEqual(Plan.decode(plan.encode()), plan)
        self.assertEqual(len(plan.routes), 2)

    def test_reads_engine_zero_padded_draft_memory(self):
        plan = Plan((5, 6), ((1, 2),), (10,), (((7, 8), ((3, 4),)),))
        self.assertEqual(Plan.decode(plan.encode().ljust(1024, b"\0")), plan)

    def test_rejects_nonzero_trailing_plan_data(self):
        with self.assertRaises(ValueError):
            Plan.decode(Plan((5, 6), ((1, 2),), (10,)).encode() + b"garbage")

    def test_reads_original_plan_version(self):
        data = PLAN_HEADER.pack(b"SQL1", 5, 6, 1, 1) + bytes((10, 1, 2))
        self.assertEqual(Plan.decode(data), Plan((5, 6), ((1, 2),), (10,)))

    def test_rejects_truncated_alternative_routes(self):
        data = Plan((5, 6), ((1, 2),), (10,), (((7, 8), ((3, 4),)),)).encode()
        with self.assertRaises(ValueError):
            Plan.decode(data[:-1])

    def test_rejects_invalid_or_truncated_data(self):
        with self.assertRaises(ValueError):
            Plan.decode(b"bad")
        with self.assertRaises(ValueError):
            Plan.decode(Plan((1, 1), ((2, 2),), (10,)).encode()[:-1])

    def test_rejects_duplicate_roster_and_oversized_plan(self):
        with self.assertRaises(ValueError):
            Plan((1, 1), (), (10, 10)).encode()
        with self.assertRaises(ValueError):
            Plan((1, 1), ((2, 2),) * 600, (10,)).encode()

    def test_extracts_report_from_binary_framed_stdout(self):
        data = b'\0\x01draft message\nSQUAD_LOOPS_DATA {"roster":[10],"loops":[]}\n\0\xff'
        self.assertEqual(extract_report(data), {"roster": [10], "loops": []})

    def test_missing_report_explains_draft_error(self):
        with self.assertRaisesRegex(ValueError, "bot error: example"):
            extract_report(b"\0bot error: example\n")


if __name__ == "__main__":
    unittest.main()
