import unittest
import torch
from .planner_readout_fit import Readout,pack,loss,export
from .objective_policy import ObjectiveHead


class ReadoutTests(unittest.TestCase):
    def test_gradient_support_and_only_readout_updated(self):
        before=ObjectiveHead().state_dict();net=Readout(before)
        r=dict(label=2,baseline=3,hidden=torch.randn(2,64),routes=[2,4],candidates=[dict(key='a'),dict(key='b')],utilities={'a':1.,'b':-1.})
        d=pack([r],[0]);l=loss(net,d,dict(temperature=4.,utility_weight=.1));l.backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in net.parameters()));torch.optim.AdamW(net.parameters(),lr=.01).step();after=export(net,before)
        self.assertTrue(torch.equal(before['net.0.weight'],after['net.0.weight']));self.assertFalse(torch.equal(before['net.2.weight'],after['net.2.weight']))
        r=dict(r,hidden=torch.zeros(0,64),routes=[],candidates=[],utilities=None);d=pack([r],[0]);self.assertTrue(torch.isfinite(loss(net,d,dict(temperature=4.,utility_weight=.1))))


if __name__=='__main__':unittest.main()
