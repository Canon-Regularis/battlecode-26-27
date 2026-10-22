from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sdk_fakes import fake_sdk, load_game_modules


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.navigation = load_game_modules(fake_sdk()).navigation

    def test_map_risk_includes_final_step_into_enemy_spawn(self):
        ally = SimpleNamespace(distance_at=lambda position: 12)
        enemy = SimpleNamespace(distance_at=lambda position: 7)
        self.assertAlmostEqual(self.navigation.spawn_risk_at(object(), ally, enemy), 0.6)

    def test_map_risk_handles_unreachable_enemy_spawn(self):
        ally = SimpleNamespace(distance_at=lambda position: 12)
        enemy = SimpleNamespace(distance_at=lambda position: -1)
        self.assertEqual(self.navigation.spawn_risk_at(object(), ally, enemy), 0)

    def test_unreachable_tile_does_not_read_sdk_distance_sentinel(self):
        field = MagicMock()
        visited = SimpleNamespace(is_set=lambda position: False)
        distances = self.navigation.DistanceMap(field, visited)
        self.assertEqual(distances.distance_at(object()), -1)
        self.assertEqual(distances.nearest_distance([object()]), -1)
        field.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
