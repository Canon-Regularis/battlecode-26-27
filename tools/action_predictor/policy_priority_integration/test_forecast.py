import unittest
import numpy as np
from .forecast import choose,padded


class ForecastContracts(unittest.TestCase):
    def test_joint_competition_and_required_family_coordinate(self):
        scores=np.full((3,15),-100.);coords=np.arange(45).reshape(3,15)
        scores[0,8]=-1;scores[0,9]=-.5;scores[1,8]=-.2;scores[1,9]=-2
        scores[2,3]=scores[2,9]=-.7
        p=choose(scores,coords,np.array([401,-22,3]))
        np.testing.assert_array_equal(p['prediction'],[9,8,3])
        np.testing.assert_array_equal(p['proposed_coordinate'],[9,23,33])
        np.testing.assert_array_equal(p['priority'],[401,-22,3])
        np.testing.assert_array_equal(scores[0,9],-.5)

    def test_ragged_pairs_and_unknown_masks(self):
        offsets=np.array([0,0,2,3]);values=np.array([[0,4],[8,9],[-3,0]],np.int64)
        available=np.array([[False,True],[True,True],[True,False]])
        roles=np.array([0,1,0],np.int8)
        p,a,r=padded(offsets,values,available,roles,0,3)
        np.testing.assert_array_equal(p[1].numpy(),values[:2]);self.assertFalse(bool(a[0].any()))
        np.testing.assert_array_equal(r[0].numpy(),[-1,-1]);self.assertFalse(bool(a[2,0,1]))


if __name__=='__main__':unittest.main()
