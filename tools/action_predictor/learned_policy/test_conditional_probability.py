"""Probability and gradient contracts for rare-family marginalization."""
import unittest

import numpy as np
import torch

from .conditional_probability import conditional_log_probs


class TestConditionalProbability(unittest.TestCase):
    def test_independent_probability_sum_for_tiny_family(self):
        rng = np.random.default_rng(20261109)
        prior = rng.normal(size=(5, 4))
        prior -= np.log(np.exp(prior).sum(-1, keepdims=True))
        family = -80 + rng.normal(size=(5, 4))
        heads = rng.normal(size=(5, 4, 291))
        heads -= np.log(np.exp(heads).sum(-1, keepdims=True))
        actual, mass = conditional_log_probs(*[
            torch.from_numpy(x) for x in (prior, family, heads)])
        weights = np.exp(prior) * np.exp(family)
        expected_mass = weights.sum(-1)
        weights /= expected_mass[:, None]
        expected = (weights[:, :, None] * np.exp(heads)).sum(1)
        np.testing.assert_allclose(actual.exp(), expected, rtol=2e-14, atol=1e-16)
        np.testing.assert_allclose(mass.exp(), expected_mass, rtol=2e-14, atol=0)

    def test_command_gradients_equal_original_formula(self):
        generator = torch.Generator().manual_seed(20261109)
        raw = [torch.randn(shape, generator=generator, dtype=torch.float64,
                           requires_grad=True)
               for shape in ((3, 4), (3, 4), (3, 4, 9))]
        prior = raw[0].log_softmax(-1)
        family = raw[1] - 80
        heads = raw[2].log_softmax(-1)
        conditional, mass = conditional_log_probs(prior, family, heads)
        targets = torch.tensor([0, 3, 8])
        rows = torch.arange(3)
        stable_loss = -(mass + conditional[rows, targets]).sum()
        joint = torch.logsumexp((prior + family)[:, :, None] + heads, 1)
        original_loss = -joint[rows, targets].sum()
        expected = torch.autograd.grad(original_loss, raw, retain_graph=True)
        actual = torch.autograd.grad(stable_loss, raw)
        torch.testing.assert_close(stable_loss, original_loss, rtol=1e-14, atol=1e-13)
        for a, b in zip(actual, expected):
            torch.testing.assert_close(a, b, rtol=1e-12, atol=1e-13)

    def test_float32_rare_family_offset_and_zero_head_entries(self):
        prior = torch.tensor([[0., -1., -2., -3.]]).log_softmax(-1)
        family = torch.tensor([[0., -1., -2., -3.]])
        heads = torch.tensor([[[0., 1., -torch.inf],
                               [1., 0., -torch.inf],
                               [2., 1., -torch.inf],
                               [1., 2., -torch.inf]]]).log_softmax(-1)
        ordinary, _ = conditional_log_probs(prior, family, heads)
        tiny, mass = conditional_log_probs(prior, family - 80, heads)
        torch.testing.assert_close(tiny[:, :2], ordinary[:, :2], rtol=0, atol=2e-6)
        self.assertTrue(torch.isneginf(tiny[:, 2]).all())
        self.assertTrue(torch.isfinite(mass).all())
        self.assertLess(float((tiny.exp().sum(-1) - 1).abs().max()), 2e-6)
        self.assertEqual(int(tiny.argmax(-1)), int(ordinary.argmax(-1)))


if __name__ == '__main__':
    unittest.main()
