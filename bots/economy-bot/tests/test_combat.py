from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sdk_fakes import fake_camp, fake_champion, fake_sdk, load_game_modules


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.combat = load_game_modules(fake_sdk()).combat

    def test_combined_damage_reduces_fighting_time(self):
        group = [fake_camp(2400)]
        solo = self.combat.estimate_camp_clear(group, [fake_champion()])
        squad = self.combat.estimate_camp_clear(group, [fake_champion() for _ in range(3)])
        self.assertEqual(solo.service_turns, 37)
        self.assertEqual(squad.service_turns, 17)

    def test_capture_cost_is_not_divided_by_squad_size(self):
        group = [fake_camp(1)]
        solo = self.combat.estimate_camp_clear(group, [fake_champion()])
        squad = self.combat.estimate_camp_clear(group, [fake_champion() for _ in range(3)])
        self.assertEqual(solo.service_turns, 1 + 5 + 2)
        self.assertEqual(squad.service_turns, solo.service_turns)

    def test_dangerous_camp_is_filtered(self):
        result = self.combat.estimate_camp_clear(
            [fake_camp(20000, 200)], [fake_champion() for _ in range(3)],
        )
        self.assertFalse(result.survivable)

    def test_attack_reset_damage_discount_is_unchanged(self):
        champion = fake_champion()
        reset = MagicMock()
        reset.info.return_value = SimpleNamespace(max_cooldown=8)
        reset.is_attack_reset.return_value = True
        champion.abilities.return_value = (reset,)
        damage, healing = self.combat.estimate_squad_power([champion], 1)
        self.assertEqual(damage, 87)  # (100 + 100/8*.7) * .8
        self.assertEqual(healing, 0)

    def test_healing_discount_is_unchanged(self):
        champion = fake_champion()
        champion.base_stats.return_value.base_focus = 120
        heal = MagicMock()
        heal.info.return_value = SimpleNamespace(max_cooldown=8, modifier=3)
        heal.is_attack_reset.return_value = False
        heal.is_heal.return_value = True
        champion.abilities.return_value = (heal,)
        damage, healing = self.combat.estimate_squad_power([champion], 1)
        self.assertEqual(damage, 80)
        self.assertAlmostEqual(healing, 31.5)

    def test_splash_target_cap_is_unchanged(self):
        champion = fake_champion()
        champion.passive.return_value = 4
        damage, _ = self.combat.estimate_squad_power([champion], 4)
        self.assertEqual(damage, 160)  # 100 * (1 + .5*2) * .8


if __name__ == "__main__":
    unittest.main()
