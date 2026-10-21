from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from protocol import Plan
from visualization import COLORS, LoopOverlay, draw_plan, loop_index


class DrawingTests(unittest.TestCase):
    def setUp(self):
        # Deliberately no movement, attack, or champion APIs in this fake.
        self.sdk = SimpleNamespace(
            Vec2=lambda x, y: SimpleNamespace(x=x, y=y),
            game_map=SimpleNamespace(is_in_bounds=lambda p: 0 <= p.x < 30 and 0 <= p.y < 30),
            debug=SimpleNamespace(draw_line=MagicMock(), draw_dot=MagicMock()),
            round_number=MagicMock(return_value=1))
        self.plan = Plan((5, 5), ((10, 5), (10, 10)), (10,),
                         (((6, 6), ((12, 6),)),))
        self.sdk.draft_memory = self.plan.encode()
        self.members = {(10, 5): ((10, 5), (11, 5), (10, 6), (11, 6)),
                        (10, 10): ((10, 10),), (12, 6): ((12, 6),)}

        def camp_at(position):
            tiles = [self.sdk.Vec2(*p) for p in self.members[(position.x, position.y)]]
            group = SimpleNamespace(spawn_tiles=lambda: SimpleNamespace(positions=lambda: tiles))
            return SimpleNamespace(camp_group=lambda: group)

        self.sdk.game_map.camp = MagicMock(side_effect=camp_at)

    def test_cycles_one_loop_every_eight_rounds(self):
        self.assertEqual([loop_index(r, 5) for r in (1, 8, 9, 16, 17, 33, 41)],
                         [0, 0, 1, 1, 2, 4, 0])

    def test_draws_colored_lines_arrowheads_and_altar(self):
        with patch.dict(sys.modules, {"cambc": self.sdk}):
            draw_plan(self.plan, rank=0)
        # Three legs, each with two arrowhead wings.
        self.assertEqual(self.sdk.debug.draw_line.call_count, 9)
        self.assertTrue(all(call.args[2] == COLORS[0][1]
                            for call in self.sdk.debug.draw_line.call_args_list))
        self.assertEqual(self.sdk.debug.draw_dot.call_args.args[1], 0xFFFFFF)

    def test_draft_draws_all_ranks_with_best_on_top(self):
        with patch.dict(sys.modules, {"cambc": self.sdk}):
            draw_plan(self.plan)
        colors = [call.args[2] for call in self.sdk.debug.draw_line.call_args_list]
        self.assertEqual(colors[0], COLORS[1][1])
        self.assertEqual(colors[-1], COLORS[0][1])

    def test_highlights_every_member_of_selected_groups(self):
        with patch.dict(sys.modules, {"cambc": self.sdk}):
            draw_plan(self.plan, rank=0)
        dots = {(call.args[0].x, call.args[0].y): call.args[1]
                for call in self.sdk.debug.draw_dot.call_args_list}
        for tile in (*self.members[(10, 5)], *self.members[(10, 10)]):
            self.assertEqual(dots[tile], COLORS[0][1])
        self.assertNotIn((12, 6), dots)  # Only belongs to the alternate loop.
        self.assertEqual(dots[(5, 5)], 0xFFFFFF)

    def test_overlay_redraws_every_turn_without_gameplay_actions(self):
        overlay = LoopOverlay()
        with patch.dict(sys.modules, {"cambc": self.sdk}), patch("builtins.print") as output:
            overlay.draw()
            overlay.draw()
            self.assertEqual(output.call_count, 1)
            # Group membership is cached, not re-queried on every turn.
            self.assertEqual(self.sdk.game_map.camp.call_count, 3)
            self.sdk.round_number.return_value = 9
            overlay.draw()
            self.assertEqual(output.call_count, 2)
            self.assertEqual(self.sdk.game_map.camp.call_count, 3)
        self.assertEqual(self.sdk.debug.draw_line.call_args.args[2], COLORS[1][1])


if __name__ == "__main__":
    unittest.main()
