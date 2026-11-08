"""Actual-return commit and rejection checks; no game or state simulation."""
import unittest
from types import SimpleNamespace
import numpy as np
from .portable_actor import PortableActor
from .execution import SDK4Executor, UnsupportedCommand

LABELS = ['<unknown>', 'altar', 'attack', 'blocked', 'cancel', 'cast_0',
          'cast_1', 'end', 'move', 'priority', 'recall', 'shop', 'submit',
          'teleport', 'ward']


class TestPortableActor(unittest.TestCase):
    def setUp(self):
        self.calls = []; self.family = 8
        parent = self
        class Policy:
            def empty(self, n): return {'belief': np.ones((1, 1), np.float32)}
            def begin(self, **kwargs): parent.calls.append('predict'); return {}
            def decode(self, *args, **kwargs):
                return dict(prediction=np.array([parent.family]), coordinate=np.array([145]))
            def observed(self, step, **kwargs):
                parent.calls.append(('commit', int(kwargs['y'][0])))
                return np.zeros(1), {'belief': np.full((1, 1), 2, np.float32)}
        priority = SimpleNamespace(raw=lambda *args: np.zeros((1, 3), np.float32),
                                   modes=lambda *args: (np.array([-784], np.int64), np.zeros(1)),
                                   log_mass=lambda *args: np.zeros(1))
        self.actor = PortableActor(Policy(), priority, LABELS, 'actor')
        self.inputs = dict(x=np.zeros((1, 253), np.float32), history=np.zeros((1, 32, 24), np.float32),
                           position=np.zeros((1, 2), np.float32), position_known=np.ones(1, bool))
        self.values = np.zeros((1, 7), np.int64); self.history = np.zeros((1, 16, 2), np.int64)
        me = SimpleNamespace(move_absolute=lambda p:self.calls.append(('move', p)) or False)
        self.executor = SDK4Executor(SimpleNamespace(me=lambda:me, Vec2=lambda x,y:(x,y)), lambda:None)

    def test_actual_blocked_return_is_assimilated_after_dispatch(self):
        result = self.actor.act(self.inputs, {}, self.values, self.history,
                                self.executor, actor_key='actor')
        self.assertEqual(result.actual_action, 'blocked')
        self.assertEqual(self.calls, ['predict', ('move', (1, 0)), ('commit', 3)])
        self.assertIsNone(self.actor.pending)
        self.assertEqual(float(self.actor.state['belief'][0, 0]), 2)

    def test_unsupported_purchase_never_commits_a_forecast(self):
        self.family = 11
        with self.assertRaises(UnsupportedCommand):
            self.actor.act(self.inputs, {}, self.values, self.history,
                           self.executor, actor_key='actor')
        self.assertEqual(self.calls, ['predict'])
        self.assertEqual(float(self.actor.state['belief'][0, 0]), 1)
        self.assertIsNone(self.actor.pending)

    def test_actor_metadata_cannot_mix_memory(self):
        with self.assertRaises(ValueError):
            self.actor.decide(self.inputs, {}, self.values, self.history, actor_key='another')
        self.assertEqual(self.calls, [])


if __name__ == '__main__': unittest.main()
