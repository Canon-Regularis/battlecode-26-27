"""Family diagnostics change without changing chosen-command correctness."""
import unittest
import numpy as np
from .comparator_schema import conditional_reference


class TestComparatorSchema(unittest.TestCase):
    def test_chosen_coordinates_are_not_conditional_coordinates(self):
        raw = dict(y=np.array([8, 2, 9, 10]), py=np.array([0, 5, -1, -1]),
                   priority=np.array([0, 0, 17, 0]))
        family = np.full((4, 15, 3), -1, dtype=np.int64)
        family[:, :, 0] = np.arange(15)[None]
        family[0, 8, 1] = 0
        family[1, 2, 1] = 5
        family[:, 9, 2] = [3, 4, 17, 6]
        prediction = dict(prediction=np.array([8, 10, 9, 8]), coordinate=np.array([0, -1, -1, 7]),
                          priority=np.array([0, 0, 17, 0]), family_commands=family)
        original = prediction['coordinate'].copy()
        result = conditional_reference(raw, prediction)
        np.testing.assert_array_equal(result['coordinate'], [0, 5, -1, -1])
        np.testing.assert_array_equal(result['priority'], [3, 4, 17, 6])
        np.testing.assert_array_equal(prediction['coordinate'], original)
        self.assertIs(result['prediction'], prediction['prediction'])


if __name__ == '__main__':
    unittest.main()
