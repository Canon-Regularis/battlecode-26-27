import copy
import unittest
from unittest.mock import patch
import torch
from torch import nn
from .model import SegmentPolicy, SPATIAL
from .filter import NeuralSemiMarkov
from .history_model import HistorySegmentPolicy, encode_command
from .history_filter import CommandHistorySemiMarkov
from .gradient_diagnostic import gradient_summary
from .test_model import fixture
from ..reliable_model import JointModel


def matched():
    torch.manual_seed(3031)
    teacher = JointModel(253, 24, 15, dict(history=16, spatial=True, constrain=True))
    rng = torch.get_rng_state().clone()
    original = SegmentPolicy(teacher, True)
    after_original = torch.get_rng_state().clone()
    torch.set_rng_state(rng)
    corrected = HistorySegmentPolicy(teacher)
    return original, corrected, after_original


class HistoryContracts(unittest.TestCase):
    def test_initialization_and_exact_parameter_accounting(self):
        old, new, rng = matched()
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        count = lambda m: sum(p.numel() for p in m.parameters() if p.requires_grad)
        self.assertEqual(count(old), 149194)
        self.assertEqual(count(new), 149530)
        self.assertEqual(new.filter.initial.in_features, 128)
        self.assertEqual(new.filter.transition.in_features, 149)
        self.assertEqual(new.filter.termination.in_features, 149)
        for key, expected in old.state_dict().items():
            actual = new.state_dict()[key]
            if key in ('filter.transition.weight', 'filter.termination.weight'):
                torch.testing.assert_close(actual[:, :128], expected, rtol=0, atol=0)
                self.assertEqual(int(torch.count_nonzero(actual[:, 128:])), 0)
            else: torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_encoding_equals_actual_preserved_direct_update(self):
        direct, inputs, geometry, _ = fixture(False)
        repeat = lambda t: t.repeat((5,)+(1,)*(t.ndim-1))
        inputs = {k: repeat(v) for k, v in inputs.items()}
        geometry = {k: repeat(v) for k, v in geometry.items()}
        y = torch.arange(15)
        py = torch.where(torch.isin(y, torch.tensor(SPATIAL)), torch.arange(15)+130, -1)
        py[1] = 289; py[2] = 290
        priority = torch.arange(15)*123-300
        capture = []
        class Capture(nn.Module):
            def forward(self, values, hidden): capture.append(values[:, -21:].clone()); return hidden
        direct.memory = Capture()
        step = direct.begin(**inputs, state=direct.empty(15))
        direct.observed(step, **geometry, y=y, py=py, priority_parameter_nll=torch.ones(15).double(), priority_value=priority)
        torch.testing.assert_close(capture[0], encode_command(y, py, priority), rtol=0, atol=0)

    def test_previous_integer_path_and_gap_reset(self):
        _, new, _ = matched()
        _, inputs, geometry, target = fixture(True)
        with torch.no_grad():
            new.filter.transition.weight[0, 147] = .7
            new.filter.termination.weight[:, 147] = torch.tensor([.7, -.5, .9, -.8])
        first = new.begin(**inputs, state=new.empty(3))
        target.update(y=torch.full((3,), 9), py=torch.full((3,), -1))
        target['priority_value'] = torch.tensor([0, 100, 200])
        _, a = new.observed(first, **geometry, **target)
        target['priority_value'] = torch.tensor([1000, -1000, 900])
        _, b = new.observed(first, **geometry, **target)
        inputs['transition_gap'][:, 2] = 0
        sa = new.begin(**inputs, state=a); sb = new.begin(**inputs, state=b)
        self.assertGreater(float((sa['logprior'].exp()-sb['logprior'].exp()).abs().max().detach()), 1e-5)
        inputs['transition_gap'][:, 0] = float(torch.log(torch.tensor(8.))/8)
        sa = new.begin(**inputs, state=a); sb = new.begin(**inputs, state=b)
        torch.testing.assert_close(sa['logprior'], sb['logprior'], rtol=0, atol=0)
        torch.testing.assert_close(sa['context'], sb['context'], rtol=0, atol=0)
        self.assertTrue(bool(torch.isnan(sa['filter_prior']['transition_exit_probability']).all()))
        with self.assertRaises(TypeError): new.begin(**inputs, state=a, current_command=target)

    def test_exit_diagnostic_uses_previous_posterior(self):
        base = NeuralSemiMarkov(3, 3, 4).double()
        with torch.no_grad():
            base.termination.weight.zero_(); base.termination.bias.zero_(); base.age_logits.zero_()
        model = CommandHistorySemiMarkov(base).double()
        previous = torch.full((2, 3, 4), -torch.inf, dtype=torch.float64)
        previous[:, 0, -1] = 0  # Forced terminal age, actual exit probability one.
        result = model.predict(torch.zeros(2, 3, dtype=torch.float64), previous,
            torch.ones(2, dtype=torch.int64), torch.tensor([False, True]), torch.zeros(2, 21, dtype=torch.float64))
        self.assertAlmostEqual(float(result['transition_exit_probability'][0]), 1, places=12)
        self.assertAlmostEqual(float(result['state_exit_mass'][0].sum()), 1, places=12)
        self.assertAlmostEqual(float(result['previous_state_hazard'][0, 0]), 1, places=12)
        self.assertTrue(bool(torch.isnan(result['transition_exit_probability'][1])))
        # The old diagnostic gives .5: hazards on current age0 are a different event.
        old = (result['logp'][0].exp()*result['termination_logp'][0].exp()).sum()
        self.assertAlmostEqual(float(old.detach()), .5, places=12)

    def test_sequence_gradients_reach_new_columns_and_execution(self):
        _, new, _ = matched()
        _, inputs, geometry, target = fixture(True)
        state = new.empty(3); losses = []
        for t in range(4):
            inputs['transition_gap'][:, 2] = int(t == 0)
            step = new.begin(**inputs, state=state)
            decoded = new.decode(step, **geometry, priority_mode=target['priority_value'],
                priority_mode_logp=torch.full((3,), -4., dtype=torch.float64))
            torch.testing.assert_close(decoded['type_logp'].exp().sum(-1), torch.ones(3).double(), rtol=0, atol=2e-12)
            for lp in decoded['parameter_logp'].values():
                torch.testing.assert_close(lp.exp().sum(-1), torch.ones(3).double(), rtol=0, atol=2e-12)
            loss, state = new.observed(step, **geometry, **target)
            self.assertTrue(bool((-loss <= decoded['family_mode_logp'].max(-1).values+1e-12).all()))
            losses.append(loss.mean())
        names = ('filter.transition.weight', 'filter.termination.weight', 'filter.age_logits',
                 'execution.query.weight', 'execution.action.weight', 'condition.condition.weight')
        parameters = dict(new.named_parameters())
        gradients = torch.autograd.grad(sum(losses), [parameters[k] for k in names])
        for name, gradient in zip(names, gradients):
            self.assertTrue(bool(torch.isfinite(gradient).all()), name)
            self.assertGreater(float(gradient.detach().norm()), 1e-15, name)
            if name in names[:2]: self.assertGreater(float(gradient[:, 128:].detach().norm()), 1e-15, name)

    def test_gradient_logging_does_not_mutate_gradients_or_rng(self):
        _, new, _ = matched()
        for parameter in new.parameters():
            if parameter.requires_grad: parameter.grad = torch.ones_like(parameter)*.01
        before = {k: p.grad.clone() for k, p in new.named_parameters() if p.grad is not None}
        rng = torch.get_rng_state().clone()
        result = gradient_summary(new, 1, 1)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        for key, p in new.named_parameters():
            if key in before: torch.testing.assert_close(p.grad, before[key], rtol=0, atol=0)
        self.assertGreater(result['gradients']['hazard_command_columns']['L2'], 0)


if __name__ == '__main__': unittest.main()
