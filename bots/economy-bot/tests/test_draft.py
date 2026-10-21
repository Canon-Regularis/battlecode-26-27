"""Adapter tests use tiny SDK fakes; actual bindings only run inside WASM."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from protocol import Plan


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.sdk = ModuleType("cambc")
        self.sdk.game_map = SimpleNamespace()
        self.sdk.constants = SimpleNamespace(CAPTURE_TIME=5)
        self.sdk.PassiveType = SimpleNamespace(SPLASH_ATTACK=4)
        self.sdk.draft = SimpleNamespace(
            team_size=lambda: 3, current_draft=lambda team: [], pick=MagicMock())
        self.sdk.Team = SimpleNamespace(ALLY=0, ENEMY=1)
        self.sdk.draft_memory = SimpleNamespace(submit=MagicMock())
        navigation = ModuleType("navigation")
        for name in ("around", "distance_field", "distance_to", "enemy_spawn_field", "terrain"):
            setattr(navigation, name, MagicMock())
        path = Path(__file__).resolve().parents[1] / "src" / "draft.py"
        spec = importlib.util.spec_from_file_location("draft_under_test", path)
        self.draft = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"cambc": self.sdk, "navigation": navigation}):
            spec.loader.exec_module(self.draft)

    def test_maps_draft_ids_to_body_ids_including_linked_pair(self):
        self.assertEqual(self.draft.bodies(range(11)), tuple(range(12)))

    def test_assumed_squad_matches_subsequent_picks(self):
        self.assertEqual(self.draft.expected_picks([]), (9, 7, 2))
        self.assertEqual(self.draft.expected_picks([9]), (9, 7, 2))
        self.assertEqual(self.draft.expected_picks([9, 7]), (9, 7, 2))

    def test_pick_happens_after_plan_is_published(self):
        plan = Plan((1, 1), ((2, 2),), (10, 8, 2))
        events = []
        self.sdk.draft_memory.submit.side_effect = lambda data: events.append("publish")
        self.sdk.draft.pick.side_effect = lambda pick: events.append(("pick", pick))
        with patch.object(self.draft, "fallback_plan", return_value=plan), \
                patch.object(self.draft, "make_plan", return_value=plan), \
                patch.object(self.draft, "draw_plan", side_effect=lambda p: events.append("draw")), \
                patch("builtins.print"):
            self.draft.play()
        self.assertEqual(events, ["publish", "publish", "draw", ("pick", 9)])

    def test_later_picks_do_not_recompute_plan(self):
        self.sdk.draft.current_draft = lambda team: [9]
        with patch.object(self.draft, "make_plan") as make:
            self.draft.play()
        make.assert_not_called()
        self.sdk.draft.pick.assert_called_once_with(7)

    def champion(self):
        champion = MagicMock()
        champion.base_stats.return_value = SimpleNamespace(
            base_strength=100, base_focus=0, camp_damage_multiplier=1, base_health=1000)
        champion.abilities.return_value = ()
        champion.passive.return_value = 0
        return champion

    def camp(self, hp, strength=0):
        camp = MagicMock()
        camp.base_stats.return_value = SimpleNamespace(base_health=hp, base_strength=strength)
        return camp

    def test_combined_damage_reduces_fighting_time(self):
        group = [self.camp(2400)]
        solo, _ = self.draft.combat_estimate(group, [self.champion()])
        squad, _ = self.draft.combat_estimate(group, [self.champion() for _ in range(3)])
        self.assertLess(squad, solo)

    def test_capture_cost_is_not_divided_by_squad_size(self):
        group = [self.camp(1)]
        solo, _ = self.draft.combat_estimate(group, [self.champion()])
        squad, _ = self.draft.combat_estimate(group, [self.champion() for _ in range(3)])
        self.assertEqual(solo, 1 + 5 + 2)
        self.assertEqual(squad, solo)

    def test_dangerous_camp_is_filtered(self):
        _, feasible = self.draft.combat_estimate(
            [self.camp(20000, 200)], [self.champion() for _ in range(3)])
        self.assertFalse(feasible)

    def test_map_risk_includes_last_step_from_approach_to_enemy_spawn(self):
        with patch.object(self.draft, "distance_to", side_effect=(12, 7)):
            self.assertAlmostEqual(self.draft.map_risk(object(), object(), object()), 0.6)

    def test_map_risk_handles_unreachable_enemy_spawn(self):
        with patch.object(self.draft, "distance_to", side_effect=(12, -1)):
            self.assertEqual(self.draft.map_risk(object(), object(), object()), 0)


if __name__ == "__main__":
    unittest.main()
