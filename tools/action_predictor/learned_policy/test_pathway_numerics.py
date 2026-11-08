"""Stable conditional-mixture arithmetic checked against direct double sums."""
import unittest
import numpy as np
import torch
from .pathway_numerics import conditional64


class TestConditional(unittest.TestCase):
    def test_matches_direct_normalized_probability_mixture(self):
        torch.manual_seed(20261108)
        step={'logprior':torch.randn(3,4).log_softmax(-1)}
        types=torch.randn(3,4,15).log_softmax(-1);heads=torch.randn(3,4,291).log_softmax(-1)
        class Model:
            def types(self,step):return types
        lp,mass=conditional64(Model(),step,heads,8)
        p=np.exp(step['logprior'].numpy().astype(float));p/=p.sum(1,keepdims=True)
        t=np.exp(types.numpy().astype(float));t/=t.sum(2,keepdims=True)
        h=np.exp(heads.numpy().astype(float));h/=h.sum(2,keepdims=True)
        weight=p*t[:,:,8];weight/=weight.sum(1,keepdims=True)
        expected=(weight[:,:,None]*h).sum(1)
        np.testing.assert_allclose(lp.exp().numpy(),expected,rtol=1e-13,atol=1e-15)
        np.testing.assert_allclose(lp.exp().sum(1).numpy(),np.ones(3),rtol=0,atol=1e-13)
        np.testing.assert_allclose(mass.exp().numpy(),(p*t[:,:,8]).sum(1),rtol=1e-13,atol=1e-15)


if __name__=='__main__':unittest.main()
