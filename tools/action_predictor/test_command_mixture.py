import unittest
import numpy as np
import torch
from .command_mixture import decode,log_mass,agreement,target_commands

class MixtureContract(unittest.TestCase):
    def test_duplicate_overlap_and_fallback_distribution(self):
        # Fallback total weight .8 must NOT veto point weight .2: Q(c)=.1.
        points=np.array([[[8,144,0],[8,144,0]]]);modes=np.array([[[10,-1,0]]]);w=np.log([[.8,.1,.1]])
        command,confidence,_=decode(w,points,np.log([[.1,.1]]),modes,np.log([[.2]]))
        np.testing.assert_array_equal(command,[[8,144,0]])
        match=agreement(points,target_commands(np.array([8]),np.array([144]),np.array([999])))
        lp=log_mass(torch.from_numpy(w),torch.from_numpy(match),torch.tensor([np.log(.1)]))
        self.assertAlmostEqual(float(lp[0]),float(confidence[0]),places=12)
        self.assertAlmostEqual(float(np.exp(confidence[0])),.28,places=12)
    def test_map_matches_exhaustive_finite_distribution(self):
        rng=np.random.default_rng(20261110)
        for _ in range(50):
            q=rng.dirichlet(np.ones(4));w=rng.dirichlet(np.ones(4));commands=np.array([[8,k,0] for k in range(4)]);ids=rng.integers(4,size=3);p=commands[ids][None]
            c,lp,_=decode(np.log(w[None]),p,np.log(q[ids][None]),commands[q.argmax()][None,None],np.log([[q.max()]]))
            full=w[0]*q
            for j,k in enumerate(ids):full[k]+=w[j+1]
            np.testing.assert_array_equal(c[0],commands[full.argmax()]);self.assertAlmostEqual(float(lp[0]),float(np.log(full.max())),places=12)

if __name__=='__main__':unittest.main()
