"""Nondegenerate intervention and mutation checks; frozen V1 tests retained."""
import unittest
import torch
from torch import nn
from .pathway_inputs import features, contrast, CONTRASTS


class TestNondegenerateContrasts(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(20261109)
        self.model = nn.Module()
        self.model.goal_condition = nn.Linear(5, 128)
        with torch.no_grad():
            self.model.goal_condition.weight.copy_(torch.randn(128, 5, generator=generator))
            self.model.goal_condition.bias.copy_(torch.randn(128, generator=generator))
        self.known = torch.tensor([True, False, True, False, True, False, True, False])
        self.inputs = dict(position=torch.randn(8, 2, generator=generator), position_known=self.known)
        self.step = dict(world=torch.randn(8, 4, 2, generator=generator),
                         known=torch.ones(8, 4, dtype=torch.bool),
                         logscale=torch.randn(8, 4, 2, generator=generator),
                         logprior=torch.randn(8, 4, generator=generator).log_softmax(-1))
        self.f = features(self.step, self.inputs)
        self.latent = torch.randn(8, 4, 128, generator=generator)
        self.step['context'] = self.latent + self.model.goal_condition(self.f)
        self.ref = dict(geometry_known=self.f[self.known, :, :2].mean(0).numpy(),
                        uncertainty_by_position_known=torch.stack([
                            self.f[self.known == v, :, 2:4].mean(0) for v in (False, True)]).numpy(),
                        availability=self.f[:, :, 4].mean(0).numpy())

    def expected(self, name):
        f = self.f.clone()
        if name in ('geometry_mean', 'all_means'):
            f[self.known, :, :2] = torch.tensor(self.ref['geometry_known'])
            f[~self.known, :, :2] = 0
        if name in ('uncertainty_mean', 'all_means'):
            f[:, :, 2:4] = torch.tensor(self.ref['uncertainty_by_position_known'])[self.known.long()]
        if name in ('availability_mean', 'all_means'):
            f[:, :, 4] = torch.tensor(self.ref['availability'])[None]
        result = self.latent + self.model.goal_condition(f)
        if name == 'bias_off':
            result = result - self.model.goal_condition.bias
        if name == 'projection_off':
            result = self.latent
        return result

    def test_replacements_match_independent_forward_and_are_nonzero(self):
        for name in CONTRASTS:
            with self.subTest(name=name):
                result = contrast(self.model, self.step, self.inputs, self.ref, name)
                expected = self.expected(name)
                torch.testing.assert_close(result['context'], expected, rtol=2e-6, atol=2e-6)
                self.assertGreater(float((expected - self.step['context']).detach().abs().max()), .01)
                for key in ('world', 'known', 'logscale', 'logprior'):
                    self.assertIs(result[key], self.step[key])
        geometry = contrast(self.model, self.step, self.inputs, self.ref, 'geometry_mean')
        torch.testing.assert_close(geometry['context'][~self.known],
                                   self.step['context'][~self.known], rtol=0, atol=0)

    def test_known_broken_replacements_are_detected(self):
        broken = {'geometry_mean': self.step['context'],
                  'uncertainty_mean': self.step['context'],
                  'all_means': contrast(self.model, self.step, self.inputs,
                                        self.ref, 'availability_mean')['context']}
        for name, bad in broken.items():
            with self.subTest(name=name):
                with self.assertRaises(AssertionError):
                    torch.testing.assert_close(bad, self.expected(name), rtol=2e-6, atol=2e-6)

    def test_sample_mean_preserved_and_inputs_not_changed(self):
        original = {key: value.clone() for key, value in self.step.items()}
        result = contrast(self.model, self.step, self.inputs, self.ref, 'all_means')
        torch.testing.assert_close(result['context'].mean(0), self.step['context'].mean(0),
                                   rtol=2e-6, atol=2e-6)
        for key, value in original.items():
            torch.testing.assert_close(self.step[key], value, rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
