import unittest
import numpy as np
from .natural_evaluation import natural_gaps


class TestNaturalGaps(unittest.TestCase):
    def example(self,y):
        g=np.zeros((4,18),np.float32);g[:,0]=np.log1p([4,2,1,4])/8;g[0,2]=1
        g[0,3+7]=np.log1p(3)/8;g[1,3+10]=np.log1p(1)/8;g[3,3+8]=np.log1p(3)/8
        return natural_gaps(np.arange(4),g,y,np.array([1,2,2,5]),np.array([1,0,1,1],bool))
    def test_true_root_gaps_and_intervening_actions(self):
        ids,g=self.example(np.array([2,3,4,7]));np.testing.assert_array_equal(ids,[0,2,3])
        np.testing.assert_allclose(np.expm1(g[:,0]*8),[4,3,4],atol=1e-5)
        counts=np.rint(np.expm1(g[:,3:]*8)).astype(int)
        self.assertEqual(counts[1,10],1);self.assertEqual(counts[1,3],1);self.assertEqual(counts[2,8],3)
    def test_current_answer_does_not_enter_its_own_transition(self):
        _,a=self.example(np.array([2,3,4,7]));_,b=self.example(np.array([2,3,9,7]))
        np.testing.assert_array_equal(a[1],b[1])
    def test_earlier_removed_action_can_change_later_counts(self):
        _,a=self.example(np.array([2,3,4,7]));_,b=self.example(np.array([2,9,4,7]))
        self.assertFalse(np.array_equal(a[1],b[1]));np.testing.assert_array_equal(a[0],b[0])


if __name__=='__main__':unittest.main()
