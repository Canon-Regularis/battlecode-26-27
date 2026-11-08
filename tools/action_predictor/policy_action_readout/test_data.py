import unittest
import numpy as np
from .data import features,donors


class DataContracts(unittest.TestCase):
    def test_feature_scope_and_exact_equality(self):
        v=np.array([[2080375424,1,2080375425,1,0,0,0],[0,0,0,1,0,0,0]],np.int64)
        x=features(np.zeros((2,39)),v)
        np.testing.assert_array_equal(x[:,-2:],[[0,1],[1,0]])
        with self.assertRaises(ValueError):features(np.zeros((2,40)),v)

    def test_donors_preserve_boundaries_exclude_held_and_are_reproducible(self):
        group=np.repeat([1,2,3],4);engine=np.repeat([2,3,2],4)
        v=np.zeros((12,7),np.int64);v[:,[1,3,5]]=1;h=np.zeros((12,16,2),np.int64);h[:,:,1]=1
        fit=group!=3;donor,single=donors(group,engine,v,h,fit,seed=4)
        self.assertEqual(single,0);self.assertFalse(bool((donor[fit]==np.flatnonzero(fit)).any()))
        np.testing.assert_array_equal(group[donor[fit]],group[fit]);np.testing.assert_array_equal(donor[~fit],np.flatnonzero(~fit))
        np.testing.assert_array_equal(donor,donors(group,engine,v,h,fit,seed=4)[0])
        v[0,5]=0;donor,single=donors(group,engine,v,h,fit,seed=4)
        self.assertEqual(single,1);self.assertEqual(donor[0],0)


if __name__=='__main__':unittest.main()
