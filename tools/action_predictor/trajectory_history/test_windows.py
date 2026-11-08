import unittest
from .window_inventory import complete_blocks, select_blocks


class WindowSelectionTests(unittest.TestCase):
    def test_gap_splits_runs_and_blocks_do_not_overlap(self):
        roots = [(i, f'{i}:0', i//5) for i in range(100)]
        available = {r[1] for r in roots} - {'40:0'}
        blocks = list(complete_blocks(roots, available))
        self.assertEqual([b[0][0] for b in blocks], [0, 41])
        self.assertEqual(len({r[1] for b in blocks for r in b}), 64)

    def test_budget_counts_only_new_roots_and_never_cuts_block(self):
        roots = [(i, f'{i}:0', i//5) for i in range(96)]
        blocks = [(4, b) for b in complete_blocks(roots, {r[1] for r in roots})]
        selected = {f'{i}:0' for i in range(8)}
        extra, kept = select_blocks(list(reversed(blocks)), selected, 56)
        self.assertEqual(len(extra), 56)
        self.assertEqual([b[0][0] for _, b in kept], [0, 32])
        self.assertFalse(extra & selected)
        extra, kept = select_blocks(blocks, selected, 23)
        self.assertEqual((extra, kept), (set(), []))


if __name__ == '__main__': unittest.main()
