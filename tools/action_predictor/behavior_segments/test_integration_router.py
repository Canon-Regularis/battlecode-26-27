import unittest
import numpy as np
import torch
from .integration_router import features, normalized_router, route, FEATURE_COUNT


class RouterTests(unittest.TestCase):
    def test_zero_initialization_is_exact_baseline(self):
        x = np.random.default_rng(5).normal(size=(8, FEATURE_COUNT)).astype(np.float32)
        net = normalized_router(x)
        self.assertTrue(torch.equal(net(torch.from_numpy(x)), torch.zeros(8)))
        self.assertEqual(route(dict(movement=(1, 0), eligible=True), 8, 144, 0), 144)

    def test_features_are_target_free_and_finite(self):
        p = np.zeros(9); p[5] = 1
        x = features(np.zeros(253), p, 145, -2, -.1, 32)
        self.assertEqual(x.shape, (FEATURE_COUNT,)); self.assertTrue(np.isfinite(x).all())
        self.assertAlmostEqual(float(x[-3]), 1.)
        with self.assertRaises(ValueError): features(np.zeros(253), p * 2, 145, -2, -.1, 32)

    def test_route_preserves_nonmovement_and_unavailable(self):
        r = dict(movement=(1, 0), eligible=True)
        for action in range(15):
            self.assertEqual(route(r, action, 3, -1), 3)
            if action != 8: self.assertEqual(route(r, action, 3, 1), 3)
        self.assertEqual(route(r, 8, 3, 1), 145)
        self.assertEqual(route(dict(r, eligible=False), 8, 3, 1), 3)
        self.assertEqual(route(dict(r, movement=None), 8, 3, 1), 3)

    def test_gradient_learns_signed_advantage(self):
        x = np.zeros((8, FEATURE_COUNT), np.float32); x[:4, 0] = -1; x[4:, 0] = 1
        y = torch.tensor([-1.] * 4 + [1.] * 4)
        net = normalized_router(x); optimizer = torch.optim.SGD(net.parameters(), lr=.1)
        loss = ((net(torch.from_numpy(x)) - y) ** 2).mean()
        loss.backward(); optimizer.step()
        self.assertTrue(torch.equal(net(torch.from_numpy(x)) > 0, y > 0))


if __name__ == '__main__': unittest.main()
