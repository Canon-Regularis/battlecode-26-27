"""Actual fit entry rejects failed prerequisites before optimizer construction."""
import unittest
from unittest.mock import patch
from . import fit


class EntryContracts(unittest.TestCase):
    def test_failed_prerequisite_cannot_construct_optimizer(self):
        with patch.object(fit, 'preflight', side_effect=RuntimeError('injected prerequisite failure')):
            with patch.object(fit.torch.optim, 'AdamW', side_effect=AssertionError('optimizer reached')) as opt:
                with self.assertRaisesRegex(RuntimeError, 'injected prerequisite failure'): fit.run('H00')
                opt.assert_not_called()

    def test_wrong_arm_cannot_reach_prerequisites(self):
        with patch.object(fit, 'preflight', side_effect=AssertionError('prerequisites reached')) as gate:
            with self.assertRaises(ValueError): fit.run('unknown')
            gate.assert_not_called()


if __name__ == '__main__': unittest.main()
