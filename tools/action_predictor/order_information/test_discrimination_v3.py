"""Reject lossy integer encoding and broken availability-matched swaps."""
import unittest
import numpy as np
from .relation_discrimination_v3 import relation_features,donors_for


class ExactRelationTests(unittest.TestCase):
    def test_integer_and_unit_pair_information_survives(self):
        # Adjacent large int32 values must differ in the exact-offset-zero feature.
        current=np.array([[2080375424],[2080375425]],np.int64)
        candidate=np.array([2080375424,2080375424],np.int64)
        role=np.zeros((2,1),np.int8);available=np.ones((2,1,2),bool)
        result=relation_features(candidate,current,current,available,role)
        self.assertTrue(result[0,4]);self.assertFalse(result[1,4])
        # Same unpaired current/scheduled pools; pairing changes guarded evidence.
        current=np.array([[1,2],[1,2]],np.int64)
        scheduled=np.array([[1,3],[3,1]],np.int64)
        candidate=np.array([1,1],np.int64);role=np.zeros((2,2),np.int8)
        result=relation_features(candidate,current,scheduled,np.ones((2,2,2),bool),role)
        np.testing.assert_array_equal(result[0,:24],result[1,:24])
        self.assertFalse(result[0,24+4]);self.assertTrue(result[1,24+4])

    def test_swapping_deranges_only_nonsingletons_and_preserves_marginals(self):
        blocks=[np.array([0,2,4]),np.array([1,3]),np.array([5])]
        for seed in range(8):
            donor=donors_for(blocks,6,seed)
            self.assertEqual(donor[5],5)
            self.assertFalse((donor[:5]==np.arange(5)).any())
            for block in blocks:np.testing.assert_array_equal(np.sort(donor[block]),np.sort(block))


if __name__=='__main__':unittest.main()
