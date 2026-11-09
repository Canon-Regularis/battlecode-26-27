import unittest
from unittest.mock import patch
import numpy as np
from .feature_inputs import inputs


class FeatureHistoryContracts(unittest.TestCase):
    def fixture(self):
        frame = dict(actor=4, round=10, turn='t2', event='10:0', pre='9:0',
            observation=dict(own=dict(position=dict(x=1, y=2))), supplement={})
        prior = dict(event='8:0', round=8, turn='t1', family='priority',
            step=dict(kind=9, actor=dict(kind=1, index=4), priority=77, to=dict(x=0, y=0)))
        return frame, prior

    def construct(self, frame, earlier, frames):
        with patch('tools.action_predictor.trajectory_history.feature_inputs.encode_frame', return_value=np.ones(253, np.float32)), \
                patch('tools.action_predictor.trajectory_history.feature_inputs.candidate_grid',
                      return_value=(np.zeros((289,20)), np.ones(289,bool), np.ones(289,bool))):
            return inputs(frame, earlier, frames, {}, ['priority'])

    def test_missing_observation_does_not_erase_actual_command(self):
        frame, prior = self.fixture()
        a = self.construct(frame, [prior], {})
        np.testing.assert_array_equal(a['history_gaps'][-1, :2], [1, 0])
        self.assertFalse(a['observations'].any())
        self.assertEqual(a['history'][-1, 0], 1)
        np.testing.assert_array_equal(a['priority_inputs'], [0,0,0,0,77,1,2])
        cached = dict(actor=4, event='8:0', pre='7:3', round=8)
        b = self.construct(frame, [prior], {'8:0':cached})
        np.testing.assert_array_equal(a['history'], b['history'])
        np.testing.assert_array_equal(b['history_gaps'][-1,:2], [1,1])
        self.assertTrue(b['observations'][-1].all())
        self.assertFalse(b['observations'][:-1].any())

    def test_future_command_and_wrong_observation_rejected(self):
        frame, prior = self.fixture(); prior['event'] = '10:0'
        with self.assertRaises(ValueError): self.construct(frame, [prior], {})
        frame, prior = self.fixture()
        cached = dict(actor=3, event='8:0', pre='7:3', round=8)
        with self.assertRaises(ValueError): self.construct(frame, [prior], {'8:0':cached})
        with self.assertRaises(ValueError): self.construct(frame, [prior,prior], {})


if __name__ == '__main__': unittest.main()
