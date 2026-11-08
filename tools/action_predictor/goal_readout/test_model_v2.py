"""Nonzero unequal mean references and explicit mutation rejection."""
import unittest
import torch
from . import test_model


class TestExactMeanReplacement(unittest.TestCase):
    def setUp(self):
        self.fixture = test_model.TestReadout()
        self.fixture.setUp()
        self.fixture.inputs['features'][:, :, 4] = self.fixture.inputs['position_known'][:, None].float()
        self.mean = torch.tensor([[-.5, .25], [.2, -.7], [.9, .1], [-.3, .4]])
        with torch.no_grad():
            self.fixture.control.geometry_mean.copy_(self.mean)
            self.fixture.control.goal_condition.bias.copy_(torch.linspace(-.3, .3, 128))

    def expected(self, mean=None, zero_uncertainty=False, zero_availability=False, remove_bias=False):
        f = self.fixture
        features = f.inputs['features'].clone()
        known = f.inputs['position_known']
        features[known, :, :2] = self.mean if mean is None else mean
        features[~known, :, :2] = 0
        if zero_uncertainty:
            features[:, :, 2:4] = 0
        if zero_availability:
            features[:, :, 4] = 0
        value = f.inputs['latent'] + torch.nn.functional.linear(features,
            f.control.goal_condition.weight, f.control.goal_condition.bias)
        return value - f.control.goal_condition.bias if remove_bias else value

    def test_full_expected_context_and_preserved_inputs(self):
        f = self.fixture
        original = {key: value.clone() for key, value in f.inputs.items()}
        result = f.control.begin(**f.inputs)
        torch.testing.assert_close(result['context'], self.expected(), rtol=1e-6, atol=1e-6)
        self.assertIs(result['logprior'], f.inputs['logprior'])
        for key, value in original.items():
            torch.testing.assert_close(f.inputs[key], value, rtol=0, atol=0)

    def test_bad_mean_and_dropped_channels_are_detected(self):
        expected = self.expected()
        mutants = [self.expected(mean=torch.zeros_like(self.mean)),
                   self.expected(mean=self.mean.flip(0)),
                   self.expected(zero_uncertainty=True),
                   self.expected(zero_availability=True),
                   self.expected(remove_bias=True)]
        for index, mutant in enumerate(mutants):
            with self.subTest(mutant=index):
                with self.assertRaises(AssertionError):
                    torch.testing.assert_close(mutant, expected, rtol=1e-6, atol=1e-6)


if __name__ == '__main__':
    unittest.main()
