import unittest
import numpy as np
import torch
from .model import placement_target,placement_modes
from .features import INDICES
from .integration import type_distribution,loss_overlay,commands

class ProbabilityContract(unittest.TestCase):
    def test_placement_matches_full_distribution_and_preserves_unsupported(self):
        rng=np.random.default_rng(20261112);q=rng.dirichlet(np.ones(291));r=rng.dirichlet(np.ones(25));full=.0001*q;full[INDICES]+=.9999*r
        lp=torch.from_numpy(np.log(r))[None];mask=torch.ones((1,25),dtype=torch.bool);mode=int(q.argmax());c,m=placement_modes(lp,mask,torch.from_numpy(np.log(q[INDICES]))[None],torch.tensor([mode]),torch.tensor([np.log(q[mode])]))
        self.assertEqual(int(c[0]),int(full.argmax()));self.assertAlmostEqual(float(m[0]),float(np.log(full.max())),places=12)
        targets=np.arange(291);actual=placement_target(lp.expand(291,-1),mask.expand(291,-1),targets,torch.from_numpy(np.log(q)));np.testing.assert_allclose(actual.numpy(),np.log(full),atol=1e-12,rtol=0)
        empty=torch.zeros_like(mask);c,_=placement_modes(lp,empty,torch.from_numpy(np.log(q[INDICES]))[None],torch.tensor([mode]),torch.tensor([np.log(q[mode])]))
        self.assertEqual(int(c[0]),mode)
    def test_type_normalization_and_no_opaque_fallback(self):
        old=torch.arange(1,16,dtype=torch.float64)[None].log_softmax(-1);new=type_distribution(old,torch.tensor([1.2]));self.assertAlmostEqual(float(new.exp().sum()),1,places=12)
        for target in (2,14):
            y=torch.tensor([target]);nll=loss_overlay(-old[:,target]+.7,old,new,y)
            self.assertAlmostEqual(float(nll[0]),float(-new[0,target]+.7),places=12)
        modes=np.zeros((1,15,3),np.int64);modes[0,:,0]=np.arange(15);modes[:,:,1]=-1;joint=old.numpy()-2
        a,_=commands(old.numpy(),old.numpy(),modes,joint,np.array([144]),np.array([0.]));self.assertEqual(int(a['prediction'][0]),int(old.argmax(-1)[0]))

if __name__=='__main__':unittest.main()
