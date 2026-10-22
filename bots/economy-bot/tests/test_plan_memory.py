from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan_memory import PLAN_HEADER, DraftPlan, RoutePlan


class PlanMemoryTests(unittest.TestCase):
    def test_round_trip(self):
        plan = DraftPlan(RoutePlan((5, 6), ((1, 2), (3, 4))), (10, 8, 2))
        self.assertEqual(DraftPlan.decode(plan.encode()), plan)
        self.assertLessEqual(len(plan.encode()), 1024)

    def plan_with_alternative(self):
        return DraftPlan(
            primary=RoutePlan((5, 6), ((1, 2),)), roster=(10, 8, 2),
            alternatives=(RoutePlan((7, 8), ((3, 4), (9, 10))),),
        )

    def test_round_trip_includes_alternative_drawing_routes(self):
        plan = self.plan_with_alternative()
        self.assertEqual(DraftPlan.decode(plan.encode()), plan)
        self.assertEqual(len(plan.routes), 2)

    def test_reads_engine_zero_padded_draft_memory(self):
        plan = self.plan_with_alternative()
        self.assertEqual(DraftPlan.decode(plan.encode().ljust(1024, b"\0")), plan)

    def test_rejects_nonzero_trailing_plan_data(self):
        with self.assertRaises(ValueError):
            DraftPlan.decode(self.plan_with_alternative().encode() + b"garbage")

    def test_reads_original_plan_version(self):
        data = PLAN_HEADER.pack(b"SQL1", 5, 6, 1, 1) + bytes((10, 1, 2))
        self.assertEqual(DraftPlan.decode(data), DraftPlan(RoutePlan((5, 6), ((1, 2),)), (10,)))

    def test_rejects_truncated_alternative_routes(self):
        with self.assertRaises(ValueError):
            DraftPlan.decode(self.plan_with_alternative().encode()[:-1])

    def test_rejects_invalid_or_truncated_data(self):
        with self.assertRaises(ValueError):
            DraftPlan.decode(b"bad")
        with self.assertRaises(ValueError):
            DraftPlan.decode(DraftPlan(RoutePlan((1, 1), ((2, 2),)), (10,)).encode()[:-1])

    def test_rejects_duplicate_roster_and_oversized_plan(self):
        with self.assertRaises(ValueError):
            DraftPlan(RoutePlan((1, 1), ()), (10, 10)).encode()
        with self.assertRaises(ValueError):
            DraftPlan(RoutePlan((1, 1), ((2, 2),) * 600), (10,)).encode()


if __name__ == "__main__":
    unittest.main()
