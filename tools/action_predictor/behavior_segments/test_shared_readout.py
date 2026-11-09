import unittest
import torch
from .shared_readout_fit import Readout,objective


class SharedReadoutTests(unittest.TestCase):
    def test_only64_parameters_and_finite_gradient(self):
        n=Readout(torch.zeros(1,64));self.assertEqual(sum(x.numel() for x in n.parameters()),64);raw=n(torch.randn(2,9,64),torch.randn(2,9));loss=objective(raw,torch.tensor([1,2]),torch.ones(2,9,dtype=torch.bool),n.weight,torch.zeros_like(n.weight),dict(margin=.25,anchor=.1),True);loss.backward();self.assertTrue(torch.isfinite(n.weight.grad).all())

    def test_ranking_loss_and_singleton(self):
        raw=torch.tensor([[0.,1.,-1.]]);y=torch.tensor([0]);s=torch.ones_like(raw,dtype=torch.bool);w=torch.zeros(1,64);p=dict(margin=.25,anchor=.1)
        self.assertAlmostEqual(float(objective(raw,y,s,w,w,p,True)-objective(raw,y,s,w,w,p,False)),1.25,places=6)
        s[0,1:]=False;self.assertEqual(float(objective(raw,y,s,w,w,p,True)),0.)


if __name__=='__main__':unittest.main()
