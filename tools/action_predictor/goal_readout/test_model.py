"""Matched input contrast, gradient boundaries and unchanged loss algebra."""
import unittest
import torch
from .model import FrozenGoalReadout
from ..reliable_model import JointModel
from ..learned_policy.model import GoalPolicy


class TestReadout(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(20261114)
        teacher = JointModel(3, 27, 15, dict(history=0, spatial=True, constrain=False))
        self.upstream = GoalPolicy(teacher, True)
        with torch.no_grad():
            self.upstream.goal_condition.weight.normal_(0, .03)
        self.mean = torch.randn(4, 2)
        self.dynamic = FrozenGoalReadout(self.upstream, self.mean, True)
        self.control = FrozenGoalReadout(self.upstream, self.mean, False)
        self.inputs = dict(latent=torch.randn(6, 4, 128), features=torch.randn(6, 4, 5),
                           logprior=torch.randn(6, 4).log_softmax(-1),
                           position_known=torch.tensor([True, False, True, False, True, False]))
        self.inputs['features'][~self.inputs['position_known'], :, :2] = 0
        self.geo = dict(grid=torch.randn(6, 289, 20), valid=torch.ones(6, 289, dtype=torch.bool),
                        rules=torch.ones(6, 5))
        self.target = dict(y=torch.tensor([8, 3, 2, 5, 6, 9]), py=torch.tensor([12, 50, 123, 0, 288, -1]),
                           priority_parameter_nll=torch.tensor([0., 0., 0., 0., 0., 2.]))

    def test_same_initialization_and_only_declared_weights_train(self):
        for key, value in self.dynamic.state_dict().items():
            torch.testing.assert_close(value, self.control.state_dict()[key], rtol=0, atol=0)
        active = ('goal_condition.', 'execution.action.', 'execution.query.', 'execution.candidate.',
                  'execution.family.', 'execution.offset_bias.', 'execution.special.')
        for name, parameter in self.dynamic.named_parameters():
            self.assertEqual(parameter.requires_grad, name.startswith(active), name)
        before = {k: v.detach().clone() for k, v in self.upstream.state_dict().items()}
        step = self.dynamic.begin(**self.inputs)
        self.dynamic.command_loss(step, **self.geo, **self.target).mean().backward()
        for name, parameter in self.dynamic.named_parameters():
            if not parameter.requires_grad:
                self.assertIsNone(parameter.grad, name)
        for key, value in self.upstream.state_dict().items():
            torch.testing.assert_close(value, before[key], rtol=0, atol=0)

    def test_geometry_mean_removes_only_named_channel_variation(self):
        changed = dict(self.inputs, features=self.inputs['features'].clone())
        changed['features'][self.inputs['position_known'], :, :2] += 2
        original = self.inputs['features'].clone()
        a = self.control.begin(**self.inputs)
        b = self.control.begin(**changed)
        torch.testing.assert_close(a['context'], b['context'], rtol=0, atol=0)
        x = self.dynamic.begin(**self.inputs)
        y = self.dynamic.begin(**changed)
        self.assertGreater(float((x['context'] - y['context']).detach().abs().max()), .01)
        torch.testing.assert_close(x['context'][~self.inputs['position_known']],
                                   a['context'][~self.inputs['position_known']], rtol=0, atol=0)
        torch.testing.assert_close(self.inputs['features'], original, rtol=0, atol=0)

    def test_original_observed_command_probability_is_preserved(self):
        step = self.dynamic.begin(**self.inputs)
        old = dict(step, world=torch.zeros(6, 4, 2), known=torch.ones(6, 4, dtype=torch.bool),
                   age=torch.zeros(6, 4))
        expected, _ = self.upstream.observed(old, **self.geo, **self.target)
        actual = self.dynamic.command_loss(step, **self.geo, **self.target)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
