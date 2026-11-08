import copy
import unittest
import numpy as np
from .memory import PersonalEntityMemory


def entity(kind, index, x, health=100, known=1):
    return dict(entity=dict(kind=kind, index=index), known=known, team=0 if index == 0 else 1,
        type=0, position=dict(x=x, y=4), health=health, maxHealth=100, alive=health > 0)


def view(entities):
    return dict(own=entity(1, 0, 2), entities=entities)


class MemoryContracts(unittest.TestCase):
    def test_refresh_is_not_limited_to_current_nearest_goal(self):
        memory = PersonalEntityMemory()
        memory.observe_pre(view([entity(1, 5, 4)]), 3)
        # Enemy5 is still visible, but enemy6 is now nearer. Both must refresh.
        memory.observe_pre(view([entity(1, 5, 12), entity(1, 6, 3)]), 4)
        keys, values = memory.snapshot(entity(1, 0, 2))
        row = values[keys.index((1, 5))]
        self.assertEqual(row[23], (12-2)/32)
        self.assertEqual(row[119+3], 1)
        self.assertEqual(row[119+4], 0)

    def test_unknown_fields_do_not_replace_observed_position(self):
        memory = PersonalEntityMemory()
        observation = view([entity(2, 8, 7)])
        original = copy.deepcopy(observation)
        memory.observe_pre(observation, 2)
        self.assertEqual(observation, original)
        memory.observe_pre(view([entity(2, 8, 999, health=0, known=0)]), 10)
        keys, values = memory.snapshot(entity(1, 0, 2))
        row = values[keys.index((2, 8))]
        self.assertEqual(row[23], (7-2)/32)
        self.assertEqual(row[119+3], 0)
        self.assertGreater(row[119+4], 0)
        self.assertEqual(row[119+6], 1)
        self.assertEqual(row[119+7], 0)

    def test_known_death_and_reappearance_are_explicit(self):
        memory = PersonalEntityMemory()
        memory.observe_pre(view([entity(2, 8, 7, health=0)]), 0)
        keys, values = memory.snapshot(entity(1, 0, 2))
        self.assertEqual(values[keys.index((2, 8)), 126], 1)
        memory.observe_pre(view([]), 1)
        keys, values = memory.snapshot(entity(1, 0, 2))
        row = values[keys.index((2, 8))]
        self.assertEqual(row[122], 0)  # Not a current observed-dead claim.
        self.assertEqual(row[126], 1)  # Last observed dead remains a memory.
        memory.observe_pre(view([entity(2, 8, 9, health=100)]), 2)
        keys, values = memory.snapshot(entity(1, 0, 2))
        self.assertEqual(values[keys.index((2, 8)), 126], 0)

    def test_identity_values_are_not_features_and_reset_is_explicit(self):
        a = PersonalEntityMemory(); b = PersonalEntityMemory()
        a.observe_pre(view([entity(2, 8, 7)]), 5)
        b.observe_pre(view([entity(2, 12345, 7)]), 5)
        ka, va = a.snapshot(entity(1, 0, 2)); kb, vb = b.snapshot(entity(1, 0, 2))
        np.testing.assert_array_equal(va, vb)
        self.assertNotEqual(ka, kb)
        self.assertEqual(ka[:2], [None, 'unknown'])
        with self.assertRaises(ValueError): a.observe_pre(view([]), 4)
        a.reset(prefix_unavailable=False)
        a.observe_pre(view([]), 0)
        keys, values = a.snapshot(entity(1, 0, 2))
        self.assertEqual(keys, [None, 'unknown', (1, 0)])
        self.assertTrue((values[:, 124] == 0).all())


if __name__ == '__main__': unittest.main()
