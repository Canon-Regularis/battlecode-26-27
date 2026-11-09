import copy
import unittest
import numpy as np
import torch
from ..reliable_model import JointModel
from .model import SegmentPolicy
from .inference import put, take


def fixture(hierarchy):
    torch.manual_seed(3031)
    teacher = JointModel(253, 24, 15, dict(history=16, spatial=True, constrain=True))
    model = SegmentPolicy(teacher, hierarchy)
    n = 3
    values = dict(x=torch.randn(n, 253), history=torch.randn(n, 16, 24),
        observations=torch.randn(n, 16, 253), history_gaps=torch.zeros(n, 16, 5),
        transition_gap=torch.zeros(n, 18), position=torch.randn(n, 2),
        position_known=torch.tensor([True, True, False]), entities=torch.randn(n, 4, 119),
        entity_mask=torch.ones(n, 4, dtype=torch.bool), public_tokens=torch.randn(n, 2, 8),
        public_mask=torch.ones(n, 2, dtype=torch.bool))
    values['transition_gap'][:, 0] = float(np.log(2)/8)
    values['transition_gap'][:, 2] = 1
    values['history_gaps'][:, :, 1] = 1
    grid = torch.randn(n, 289, 20)
    grid[:, :, 5] = 1
    geo = dict(grid=grid, valid=torch.ones(n, 289, dtype=torch.bool), rules=torch.tensor([[3, 3, 3, 31, 31.]]).repeat(n, 1))
    target = dict(y=torch.tensor([8, 9, 4]), py=torch.tensor([144, -1, -1]),
        priority_parameter_nll=torch.tensor([0., 4., 0.], dtype=torch.float64), priority_value=torch.tensor([0, 33, 0]))
    return model, values, geo, target


class PolicyContracts(unittest.TestCase):
    def test_shared_initialization_and_comparable_active_capacity(self):
        direct, _, _, _ = fixture(False)
        semi, _, _, _ = fixture(True)
        a = direct.state_dict(); b = semi.state_dict()
        for k in set(a) & set(b): torch.testing.assert_close(a[k], b[k], rtol=0, atol=0)
        count = lambda m: sum(p.numel() for p in m.parameters() if p.requires_grad)
        self.assertLess(abs(count(direct)-count(semi))/count(direct), .01)

    def test_probability_decoder_and_sequence_gradients(self):
        for hierarchy in (False, True):
            model, values, geo, target = fixture(hierarchy)
            state = model.empty(3)
            losses = []
            for t in range(3):
                values['transition_gap'][:, 2] = int(t == 0)
                step = model.begin(**values, state=state)
                p = model.decode(step, **geo, priority_mode=target['priority_value'],
                                 priority_mode_logp=torch.full((3,), -4., dtype=torch.float64))
                torch.testing.assert_close(p['type_logp'].exp().sum(-1), torch.ones(3, dtype=torch.float64), rtol=0, atol=2e-12)
                for lp in p['parameter_logp'].values():
                    torch.testing.assert_close(lp.exp().sum(-1), torch.ones(3, dtype=torch.float64), rtol=0, atol=2e-12)
                loss, state = model.observed(step, **geo, **target)
                # Recorded command can never outrank the decoded MAP.
                self.assertTrue(bool((-loss <= p['family_mode_logp'].max(-1).values+1e-12).all()))
                losses.append(loss.mean())
            parameters = {k: v for k, v in model.named_parameters() if v.requires_grad}
            gradients = torch.autograd.grad(sum(losses), list(parameters.values()), allow_unused=True)
            required = ['execution.current', 'execution.query', 'execution.candidate', 'execution.action',
                'filter.transition', 'filter.termination', 'filter.age_logits', 'condition'] if hierarchy else ['memory', 'memory_projection']
            for prefix in required:
                subset = [g for k, g in zip(parameters, gradients) if k.startswith(prefix) and g is not None]
                self.assertTrue(subset, prefix)
                self.assertTrue(all(bool(torch.isfinite(g).all()) for g in subset), prefix)
                self.assertGreater(sum(float(g.detach().norm()) for g in subset), 1e-12, prefix)

    def test_current_answer_not_an_input_and_gap_reset(self):
        for hierarchy in (False, True):
            model, values, geo, target = fixture(hierarchy)
            model.eval()
            first = model.begin(**values, state=model.empty(3))
            _, past = model.observed(first, **geo, **target)
            values['transition_gap'][:, 2] = 0
            values['transition_gap'][:, 0] = float(np.log(8)/8)
            a = model.begin(**values, state=past)
            b = model.begin(**values, state=model.empty(3))
            torch.testing.assert_close(a['context'], b['context'], rtol=0, atol=0)
            torch.testing.assert_close(a['logprior'], b['logprior'], rtol=0, atol=0)
            with self.assertRaises(TypeError): model.begin(**values, state=past, y=target['y'])

    def test_padding_never_updates_other_streams(self):
        for hierarchy in (False, True):
            model, _, _, _ = fixture(hierarchy)
            old = model.empty(5)
            ids = torch.tensor([1, 4])
            selected = take(old, ids)
            update = {k: v + 3 for k, v in selected.items()}
            new = put(old, ids, update)
            for k in old:
                torch.testing.assert_close(new[k][[0, 2, 3]], old[k][[0, 2, 3]], rtol=0, atol=0)
                torch.testing.assert_close(new[k][ids], update[k], rtol=0, atol=0)


if __name__ == '__main__': unittest.main()
