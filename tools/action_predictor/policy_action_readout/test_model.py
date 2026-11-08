"""No-update probability, decoder, gradient and input-boundary contracts."""
import unittest
import numpy as np
import torch
from .model import ActionBeliefCorrection,command_mode_scores,decode,observed_nll


class ReadoutContracts(unittest.TestCase):
    def test_zero_initialization_and_nonzero_differentiable_learning(self):
        torch.manual_seed(9183)
        original=torch.randn(5,15,dtype=torch.float64).log_softmax(-1)
        features=torch.tensor([[1.,2.,-1.],[2.,-3.,1.],[-2.,.5,2.],[3.,1.,.25],[-1.,2.,3.]])
        model=ActionBeliefCorrection(3);lp=model(original,features)
        torch.testing.assert_close(lp,original,rtol=0,atol=1e-15)
        y=torch.tensor([1,9,8,14,5]);loss=observed_nll(lp,y,torch.tensor([-.1,-2.,-.3,-4.,-.5])).mean()
        gradient=torch.autograd.grad(loss,model.correction.weight)[0]
        expected=((lp.detach().exp()-torch.nn.functional.one_hot(y,15))[:,:,None]*features.double()[:,None]).mean(0)
        torch.testing.assert_close(gradient,expected,rtol=1e-13,atol=1e-14)
        self.assertGreater(float(gradient.norm()),.1)
        self.assertTrue(bool((model.correction.weight==0).all()))

    def test_joint_argmax_matches_independent_enumeration(self):
        rng=np.random.default_rng(38190)
        family=rng.uniform(.1,1,(4,15));family/=family.sum(1,keepdims=True)
        conditional=rng.uniform(.01,1,(4,15,7));conditional/=conditional.sum(-1,keepdims=True)
        # Different shapes make marginal-family routing demonstrably inadequate.
        family[0]=.1/14;family[0,9]=.9
        conditional[0,9]=1/7;conditional[0,8]=[.98,.005,.003,.003,.003,.003,.003]
        family[0,8]=.15;family[0]/=family[0].sum()
        mode=conditional.argmax(-1);mode_lp=np.log(conditional.max(-1))
        coordinates=torch.from_numpy(mode.astype(np.int64));priority=torch.tensor([55,-1,901,3])
        p=decode(torch.from_numpy(np.log(family)),torch.from_numpy(mode_lp),coordinates,priority)
        joint=family[:,:,None]*conditional
        flat=joint.reshape(4,-1).argmax(-1);expected_type=flat//7;expected_argument=flat%7
        np.testing.assert_array_equal(p['prediction'].numpy(),expected_type)
        np.testing.assert_array_equal(p['proposed_coordinate'].numpy(),expected_argument)
        for i in range(4):self.assertAlmostEqual(float(p['mode_logp'][i]),np.log(joint.reshape(4,-1)[i,flat[i]]),places=13)
        self.assertNotEqual(int(p['prediction'][0]),int(family[0].argmax()))
        self.assertFalse(np.allclose(np.exp(command_mode_scores(torch.from_numpy(np.log(family)),torch.from_numpy(mode_lp)).numpy()).sum(1),1))
        y=np.array([9,8,3,14]);arg=np.array([2,6,1,4]);rows=np.arange(4)
        observed=observed_nll(torch.from_numpy(np.log(family)),torch.from_numpy(y),torch.from_numpy(np.log(conditional[rows,y,arg])))
        np.testing.assert_allclose(observed.numpy(),-np.log(joint[rows,y,arg]),rtol=0,atol=1e-13)

    def test_normalization_fixed_conditionals_and_no_answer_decoder_argument(self):
        model=ActionBeliefCorrection(2)
        with torch.no_grad():model.correction.weight.copy_(torch.arange(30,dtype=torch.float64).reshape(15,2)/20)
        baseline=torch.arange(45,dtype=torch.float64).reshape(3,15).log_softmax(-1)
        features=torch.tensor([[1.,-2.],[3.,1.],[-1.,2.]])
        lp=model(baseline,features)
        expected=baseline.numpy()+features.double().numpy()@model.correction.weight.detach().numpy().T
        expected-=np.log(np.exp(expected).sum(1,keepdims=True))
        np.testing.assert_allclose(lp.detach().numpy(),expected,rtol=0,atol=1e-13)
        torch.testing.assert_close(lp.exp().sum(1),torch.ones(3,dtype=torch.float64),rtol=0,atol=1e-14)
        conditional=torch.full((3,15),-.7,dtype=torch.float64)
        copy=conditional.clone();coords=torch.arange(45).reshape(3,15);priority=torch.tensor([1,2,3])
        decode(lp,conditional,coords,priority)
        torch.testing.assert_close(conditional,copy,rtol=0,atol=0)
        with self.assertRaises(TypeError):decode(lp,conditional,coords,priority,recorded_family=torch.ones(3,dtype=torch.int64))
        with self.assertRaises(ValueError):model(baseline,torch.full((3,2),float('nan')))


if __name__=='__main__':unittest.main()
