"""New-fit group exclusion and real-only primary inference contracts."""
import unittest
import numpy as np
import torch
from .data import FeatureBank
from .protocol import fold


class DataContracts(unittest.TestCase):
    def test_group_fold_is_deterministic_and_preserves_all_rows(self):
        groups=np.repeat(np.arange(55),3)
        fit,held=fold(groups)
        self.assertEqual(len(held),15);self.assertEqual(len(np.unique(groups[fit])),40)
        self.assertFalse(set(groups[fit])&set(groups[~fit]))
        again,again_held=fold(groups[::-1])
        np.testing.assert_array_equal(again[::-1],fit);np.testing.assert_array_equal(again_held,held)
        self.assertEqual(int(fit.sum()+(~fit).sum()),len(groups))

    def test_control_training_and_both_primary_inferences_use_correct_fields(self):
        own=np.zeros((3,2,24),bool);real=np.zeros((3,2,48),bool);shuffled=np.ones_like(real)
        own[0,0,3]=True;real[1,1,7]=True
        bank=FeatureBank(own,real,shuffled,np.array([True,True,False]))
        torch.testing.assert_close(bank.evaluation_features(np.array([0,1,2])),
                                   torch.from_numpy(np.concatenate((own,real),-1)),rtol=0,atol=0)
        control=bank.training_features(np.array([0,1]),'RC00')
        treatment=bank.training_features(np.array([0,1]),'RC01')
        self.assertTrue(control[:,:,24:].all());self.assertFalse(torch.equal(control,treatment))
        torch.testing.assert_close(control[:,:,:24],treatment[:,:,:24],rtol=0,atol=0)
        for arm in ('RC00','RC01'):
            with self.assertRaisesRegex(RuntimeError,'Correction-held'):
                bank.training_features(np.array([0,2]),arm)


if __name__=='__main__':unittest.main()
