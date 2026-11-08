import unittest
from unittest.mock import patch
from . import fit


class EntryContracts(unittest.TestCase):
    def test_gate_failure_cannot_construct_optimizer(self):
        for arm in ('E00', 'E01'):
            with patch.object(fit, 'preflight', side_effect=RuntimeError('Unreviewed/changed input')), \
                    patch.object(fit.torch.optim, 'AdamW') as optimizer, \
                    patch.object(fit, 'load_base') as loader:
                with self.assertRaises(RuntimeError): fit.run(arm)
                optimizer.assert_not_called()
                loader.assert_not_called()

    def test_unknown_arm_rejected_before_preflight(self):
        with patch.object(fit, 'preflight') as gate:
            with self.assertRaises(ValueError): fit.run('H01')
            gate.assert_not_called()


if __name__ == '__main__': unittest.main()
