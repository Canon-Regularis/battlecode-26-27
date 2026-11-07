import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from .data import features
from .model import ActionGRU, Predictor
from .train import Turns, collate


def observation():
    return {'own': {'entity': {'index': 0, 'kind': 1}, 'team': 0, 'position': {'x': 4, 'y': 4},
                    'health': 800, 'maxHealth': 1000, 'alive': True}, 'entities': []}


class PredictorTests(unittest.TestCase):
    def test_hidden_entities_do_not_change_features(self):
        obs = observation()
        original, names = features(obs)
        obs['entities'].append({'known': 0, 'entity': {'kind': 1}, 'team': 1,
                                'position': {'x': 5, 'y': 5}, 'health': 100})
        np.testing.assert_array_equal(original, features(obs)[0])
        self.assertEqual(len(names), len(original))

    def test_relative_features_translation_invariant(self):
        obs = observation()
        obs['entities'] = [{'known': 1, 'entity': {'kind': 1}, 'team': 1,
                            'position': {'x': 5, 'y': 7}, 'health': 100}]
        other = copy.deepcopy(obs)
        for e in [other['own'], *other['entities']]:
            e['position']['x'] += 10
            e['position']['y'] += 10
        np.testing.assert_array_equal(features(obs)[0], features(other)[0])

    def test_previous_action_shift_and_turn_reset(self):
        d = Turns({'train_x': np.zeros((4, 2), dtype=np.float32),
                   'train_y': np.array([1, 2, 3, 1]), 'train_offsets': np.array([0, 2, 4])},
                  'train', torch.zeros(2), torch.ones(2), 4)
        self.assertEqual(d[0][2].tolist(), [4, 1])
        self.assertEqual(d[1][2].tolist(), [4, 3])
        self.assertEqual(len(list(d)), 2)

    def test_future_does_not_change_prediction(self):
        torch.manual_seed(1)
        model = ActionGRU(5, 4, 8).eval()
        x, previous = torch.randn(2, 4, 5), torch.zeros(2, 4, dtype=torch.long)
        a, _ = model(x, previous)
        x[:, 2:] = 999
        previous[:, 2:] = 3
        b, _ = model(x, previous)
        torch.testing.assert_close(a[:, :2], b[:, :2])

    def test_online_matches_full_sequence(self):
        model = ActionGRU(5, 4, 8).eval()
        x, previous = torch.randn(1, 4, 5), torch.tensor([[4, 2, 1, 3]])
        expected, _ = model(x, previous)
        hidden, outputs = None, []
        for i in range(4):
            output, hidden = model(x[:, i:i+1], previous[:, i:i+1], hidden)
            outputs.append(output)
        torch.testing.assert_close(expected, torch.cat(outputs, dim=1))

    def test_padding_is_ignored_in_labels(self):
        rows = [(torch.ones(n, 2), torch.zeros(n, dtype=torch.long), torch.zeros(n, dtype=torch.long)) for n in (1, 3)]
        _, y, _ = collate(rows)
        self.assertEqual(y[0].tolist(), [0, -100, -100])

    def test_checkpoint_predictor_and_reset(self):
        x, names = features(observation())
        model = ActionGRU(len(x), 3, 8)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'model.pt'
            torch.save(dict(state_dict=model.state_dict(), mean=torch.zeros(len(x)), std=torch.ones(len(x)),
                            hidden=8, labels=['<unknown>', 'move', 'end'], features=names), path)
            predictor = Predictor(path)
            first = predictor.predict(observation())
            self.assertAlmostEqual(sum(first.values()), 1., places=6)
            with self.assertRaises(ValueError):
                predictor.predict(observation())
            predictor.predict(observation(), previous_action='move')
            predictor.reset()
            self.assertEqual(first, predictor.predict(observation()))


if __name__ == '__main__':
    unittest.main()
