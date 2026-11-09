"""Adapter parity with the original decoder and unavailable diagnostics."""
import unittest
import torch
from .test_model import TestReadout
from .decoder_interface import ReadoutDecoderInterface


class TestDecoderInterface(unittest.TestCase):
    def test_math_and_parameters_preserved(self):
        fixture = TestReadout()
        fixture.setUp()
        model = ReadoutDecoderInterface(fixture.upstream, fixture.mean, True)
        step = model.begin(**fixture.inputs)
        kwargs = dict(fixture.geo, priority_mode=torch.zeros(6, dtype=torch.long),
                      priority_mode_logp=torch.full((6,), -2.))
        actual = model.decode(step, **kwargs)
        old = dict(step, world=torch.randn(6, 4, 2), known=torch.ones(6, 4, dtype=torch.bool),
                   retain=torch.rand(6))
        expected = fixture.dynamic.decode(old, **kwargs)
        for key in ('prediction', 'coordinate', 'priority', 'type_logp', 'goal_prior'):
            torch.testing.assert_close(actual[key], expected[key], rtol=0, atol=0)
        for family, value in actual['parameter_logp'].items():
            torch.testing.assert_close(value, expected['parameter_logp'][family], rtol=0, atol=0)
        for key in ('goal_world', 'goal_known', 'retention'):
            self.assertIsNone(actual[key])
        for name, value in model.state_dict().items():
            torch.testing.assert_close(value, fixture.dynamic.state_dict()[name], rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
