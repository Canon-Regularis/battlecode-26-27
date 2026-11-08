import unittest
import numpy as np
import torch
from .weight_inspection import stats,distribution,diagnostics,margin_components


class WeightInspectionTests(unittest.TestCase):
    def test_support_normalization_fallback_and_special(self):
        tile=torch.tensor([[2.,1.,0.],[2.,1.,0.]])
        special=torch.tensor([[1.,-1.],[1.,-1.]])
        valid=torch.ones(2,3,dtype=torch.bool)
        support=torch.tensor([[True,True,False],[False,False,False]])
        lp=distribution(tile,special,valid,support)
        torch.testing.assert_close(lp.exp().sum(-1),torch.ones(2,dtype=torch.double))
        torch.testing.assert_close(lp[1],torch.cat((tile,special),-1)[1].log_softmax(-1).double().log_softmax(-1))
        self.assertAlmostEqual(float(lp[0,0]-lp[0,1]),1.,places=6)
        self.assertTrue(torch.isfinite(lp).all())

    def test_additive_margin_and_initial_bias_cancellation(self):
        dynamic=torch.tensor([[.2,.9,-.3]])
        initial=torch.tensor([2.,-1.,.2]);update=torch.tensor([-.03,.02,0.])
        valid=torch.ones(1,3,dtype=torch.bool);special=torch.zeros(1,2)
        lp=distribution(dynamic+initial+update,special,valid,valid)
        expected=(dynamic[0,0]-dynamic[0,1])+(initial[0]-initial[1])+(update[0]-update[1])
        self.assertAlmostEqual(float(lp[0,0]-lp[0,1]),float(expected),places=6)
        changed=distribution(dynamic+initial+update-initial,special,valid,valid)
        self.assertEqual(int(lp.argmax(1)),0);self.assertEqual(int(changed.argmax(1)),1)

    def test_statistics_and_strata(self):
        self.assertEqual(stats([1.,2.,3.])['median'],2.)
        with self.assertRaises(ValueError):stats([float('nan')])
        p=torch.tensor([[.8,.2],[.3,.7]],dtype=torch.double).log()
        r=diagnostics(p,np.array([0,0]),np.array([3,2]))
        self.assertEqual(r['change']['conditional_correct'],1)
        self.assertEqual(r['continue']['conditional_correct'],0)

    def test_overlapping_cohort_names_do_not_mix(self):
        pair={}
        for cohort,n in [('strongest_wrong',3),('strongest_wrong_nonrepeat',2)]:
            for name in ('baseline_margin','dynamic_margin','initial_bias_margin','learned_bias_update_margin','N01_correction_margin'):
                pair[cohort+'_'+name]=np.arange(n,dtype=float)
        r=margin_components(pair,'strongest_wrong',np.array([True,False,True]))
        self.assertEqual(len(r),5)
        self.assertEqual(r['baseline_margin']['n'],2)


if __name__=='__main__':unittest.main()
