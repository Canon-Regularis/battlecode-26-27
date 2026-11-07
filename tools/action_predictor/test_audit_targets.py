import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from .audit import cursor, immutable_json, validate_decision
from .data import digest, features
from .model import ActionGRU, ActionMLP, CoordinateHead, StructuredPredictor
from .targets import OFFSETS, recorded_target, spatial_candidates


def fixture():
    own = dict(entity={'kind': 1, 'index': 0}, position={'x': 10, 'y': 10}, known=15,
               health=500, maxHealth=500, team=0, alive=True, abilityProps=[{'target': 16}, {'target': 2}])
    enemy = dict(entity={'kind': 1, 'index': 1}, position={'x': 11, 'y': 10}, known=1,
                 health=400, maxHealth=500, team=1, alive=True)
    label = dict(kind=5, root_class='attack', slot=None, **{'from': own['position'], 'to': enemy['position']})
    pre = dict(inputPosition=5, step={'substep': 3}, phase=10, currentChampion=0)
    step = dict(label, actor=own['entity'], phase=10, substep=0)
    return dict(pre_cursor='5:3', event_cursor='6:0', observation=dict(own=own, entities=[enemy],
                perspective={'team': 0, 'champion': 0}), label=label,
                audit=dict(pre_header=pre, header=dict(inputPosition=6, step=step), post_move_matches=True))


class AuditTargetTests(unittest.TestCase):
    def test_strict_pre_and_actor(self):
        d = fixture()
        turn = {'actor': 0, 'view': {'team': 0}}
        validate_decision(d, turn)
        d['pre_cursor'] = '6:0'
        with self.assertRaises(ValueError):
            validate_decision(d, turn)
        d = fixture()
        d['audit']['pre_header']['currentChampion'] = 2
        with self.assertRaises(ValueError):
            validate_decision(d, turn)

    def test_cursor_orders_substeps_numerically(self):
        self.assertLess(cursor('5:12'), cursor('6:0'))
        self.assertLess(cursor('5:2'), cursor('5:12'))

    def test_recorded_coordinate_and_unique_occupant(self):
        d = fixture()
        index, reason, entity = recorded_target(d, 'attack', 30, 30)
        self.assertEqual(reason, 'supported')
        np.testing.assert_array_equal(OFFSETS[index], [1, 0])
        self.assertEqual(entity, {'kind': 1, 'index': 1})
        d['observation']['entities'].append(copy.deepcopy(d['observation']['entities'][0]))
        self.assertIsNone(recorded_target(d, 'attack', 30, 30)[2])

    def test_hidden_targets_not_resolved(self):
        d = fixture()
        d['observation']['entities'][0]['known'] = 0
        self.assertEqual(recorded_target(d, 'attack', 30, 30)[1], 'no_visible_compatible_target')

    def test_candidate_grid_does_not_use_recorded_label(self):
        d = fixture()
        grid, mask, _ = spatial_candidates(d['observation'], 'move', 30, 30)
        d['label']['to'] = {'x': 0, 'y': 0}
        other, other_mask, _ = spatial_candidates(d['observation'], 'move', 30, 30)
        np.testing.assert_array_equal(grid, other)
        np.testing.assert_array_equal(mask, other_mask)

    def test_move_requires_post_confirmation_and_origin(self):
        d = fixture()
        self.assertEqual(recorded_target(d, 'move', 30, 30)[1], 'supported')
        d['audit']['post_move_matches'] = False
        self.assertEqual(recorded_target(d, 'move', 30, 30)[1], 'unverified_move')
        d['label']['from'] = {'x': 0, 'y': 0}
        self.assertEqual(recorded_target(d, 'move', 30, 30)[1], 'origin_mismatch')

    def test_ground_aim_is_coordinate_only(self):
        d = fixture()
        d['label']['to'] = {'x': 12, 'y': 12}
        self.assertEqual(recorded_target(d, 'cast_0', 30, 30)[1:], ('supported', None))
        self.assertIsNone(recorded_target(d, 'cast_1', 30, 30)[0])

    def test_ability_uses_pre_position_when_from_unset(self):
        d = fixture()
        d['label']['from'] = {'x': 0, 'y': 0}
        i, reason, entity = recorded_target(d, 'cast_1', 30, 30)
        self.assertEqual(reason, 'supported')
        np.testing.assert_array_equal(OFFSETS[i], [1, 0])
        self.assertEqual(entity, {'kind': 1, 'index': 1})

    def test_frozen_artifact_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'lock.json'
            immutable_json(path, {'test': [1, 2]})
            immutable_json(path, {'test': [1, 2]})
            with self.assertRaises(ValueError):
                immutable_json(path, {'test': [3]})
            self.assertEqual(json.loads(path.read_text()), {'test': [1, 2]})

    def test_prepare_and_fit_refuse_overwrite(self):
        from types import SimpleNamespace
        from .data import prepare
        from .experiment import fit
        from .train import train
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out/'data.npz').write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                prepare(out/'missing-source', out)
            (out/'model.pt').write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                train(SimpleNamespace(out=out, seed=26, threads=1))
            with self.assertRaises(FileExistsError):
                fit(out, out, out, out)
            self.assertEqual((out/'model.pt').read_bytes(), b'preserve')

    def test_stateless_model_ignores_all_history(self):
        model = ActionMLP(5, 4).eval()
        x = torch.randn(2, 4, 5)
        a, _ = model(x, torch.zeros(2, 4, dtype=torch.long))
        b, _ = model(x, torch.ones(2, 4, dtype=torch.long))
        torch.testing.assert_close(a, b)
        single, _ = model(x[:, 2])
        torch.testing.assert_close(a[:, 2], single)

    def test_structured_inference_binding_and_supported_family(self):
        obs = fixture()['observation']
        x, names = features(obs)
        model = ActionGRU(len(x), 3, 8)
        with tempfile.TemporaryDirectory() as directory:
            base, target = Path(directory)/'base.pt', Path(directory)/'target.pt'
            torch.save(dict(state_dict=model.state_dict(), mean=torch.zeros(len(x)), std=torch.ones(len(x)),
                            hidden=8, labels=['<unknown>', 'attack', 'end'], features=names), base)
            saved = dict(state_dict=CoordinateHead(8).state_dict(), supported_families=['attack'],
                         baseline_checkpoint_sha256=digest(base))
            torch.save(saved, target)
            predictor = StructuredPredictor(base, target)
            result = predictor.predict(obs, 30, 30, family='attack')
            self.assertEqual(result['targets'][0]['position'], {'x': 11, 'y': 10})
            self.assertEqual(result['targets'][0]['probability'], 1.)
            predictor.reset()
            self.assertEqual(predictor.predict(obs, 30, 30, family='cast_0')['targets'], [])
            saved['baseline_checkpoint_sha256'] = 'invalid'
            torch.save(saved, target)
            with self.assertRaises(ValueError):
                StructuredPredictor(base, target)


if __name__ == '__main__':
    unittest.main()
