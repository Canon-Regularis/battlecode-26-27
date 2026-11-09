import time
import unittest
import numpy as np
import torch
from .code_head_calibration import compose,solve


class CodeHeadCalibrationTests(unittest.TestCase):
    def test_composition_and_preservation(self):
        torch.manual_seed(3)
        state={'code.weight':torch.randn(8,48),'code.bias':torch.randn(8),'untouched':torch.randn(4)}
        a=np.eye(8)+np.random.default_rng(1).normal(0,.1,(8,8));b=np.arange(8)/10
        edited=compose(state,a,b);hidden=torch.randn(12,48)
        expected=(hidden.double()@state['code.weight'].double().T+state['code.bias'].double())@torch.tensor(a).T+torch.tensor(b)
        actual=hidden@edited['code.weight'].T+edited['code.bias']
        torch.testing.assert_close(actual.double(),expected,atol=3e-6,rtol=1e-5)
        self.assertTrue(torch.equal(state['untouched'],edited['untouched']))
        identity=compose(state,np.eye(8),np.zeros(8))
        self.assertTrue(all(torch.equal(v,identity[k]) for k,v in state.items()))

    def test_solver_preserves_absent_class_rows(self):
        rng=np.random.default_rng(8);y=np.tile([0,2],20);x=rng.normal(0,.1,(40,8));x[np.arange(40),y]+=2;x[:,0]+=3
        a,b,trace=solve(x,y,.01,time.perf_counter()+30)
        self.assertTrue(np.isfinite(a).all() and np.isfinite(b).all())
        np.testing.assert_array_equal(a[[1,3,4,5,6,7]],np.eye(8)[[1,3,4,5,6,7]])
        np.testing.assert_array_equal(b[[1,3,4,5,6,7]],np.zeros(6))
        self.assertLess(trace['objectives'][-1],trace['objectives'][0])


if __name__=='__main__':unittest.main()
