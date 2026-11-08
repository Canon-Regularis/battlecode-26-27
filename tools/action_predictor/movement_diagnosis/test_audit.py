import unittest
import numpy as np
from .audit import decomposition,discrimination


class Diagnostic(unittest.TestCase):
    def test_exact_loss_partition_and_forced_alternative_is_not_accuracy(self):
        p=np.full((2,291),1e-9);p[:,0]=.6;p[:,1]=.3;p[:,2]=.1;p/=p.sum(1,keepdims=True)
        d=decomposition(np.log(p),np.array([0,1]),np.array([0,0]))
        np.testing.assert_allclose(d['coordinate_nll'],d['group_nll']+d['within_group_nll'])
        self.assertAlmostEqual(d['within_group_nll'][0],0)
        self.assertEqual(d['conditional_mode'].tolist(),[0,0])
        self.assertEqual(d['forced_nonrepeat_mode'].tolist(),[1,1])
        self.assertEqual(d['gold_rank'].tolist(),[1,2])
        self.assertEqual(d['gold_rank_without_repeat'][1],1)

    def test_auc_ties_bins_and_endpoint(self):
        p=np.array([0.,.5,.5,1.]);y=np.array([False,True,False,True]);d=discrimination(p,y)
        self.assertAlmostEqual(d['AUC'],.875)
        self.assertEqual(sum(b['rows'] for b in d['reliability']),4)
        self.assertEqual(d['reliability'][5]['rows'],2)
        self.assertEqual(d['reliability'][9]['rows'],1)
        self.assertIsNone(discrimination(p,np.ones(4,bool))['AUC'])

    def test_invalid_normalization_and_special_gold_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unnormalized'):decomposition(np.zeros((1,291)),np.array([1]),np.array([0]))
        with self.assertRaisesRegex(ValueError,'Known tiles'):decomposition(np.full((1,291),-np.log(291)),np.array([290]),np.array([0]))


if __name__=='__main__':unittest.main()
