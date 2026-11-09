import unittest
import torch
from .planner_readout_fit import Readout,pack
from .planner_margin_fit import loss


class Tests(unittest.TestCase):
    def test_correct_candidate_gets_positive_gradient_update(self):
        net=Readout({'net.2.weight':torch.zeros(1,64),'net.2.bias':torch.zeros(1)})
        hidden=torch.zeros(2,64);hidden[0,0]=1;hidden[1,0]=-1
        rows=[dict(routes=[1,2],baseline=2,label=1,hidden=hidden,candidates=[dict(key='a'),dict(key='b')],utilities=None)]
        d=pack(rows,[0]);value=loss(net,d,dict(margin=.2,utility_weight=.1));self.assertAlmostEqual(float(value),.2,places=6);value.backward()
        self.assertLess(float(net.output.weight.grad[0,0]),0.)
        with torch.no_grad():net.output.weight-=.1*net.output.weight.grad
        self.assertLess(float(loss(net,d,dict(margin=.2,utility_weight=.1))),.2)

    def test_uncovered_and_all_correct_have_no_movement_gradient(self):
        for label in (1,2):
            net=Readout({'net.2.weight':torch.zeros(1,64),'net.2.bias':torch.zeros(1)})
            row=dict(routes=[2],baseline=2,label=label,hidden=torch.ones(1,64),candidates=[dict(key='a')],utilities=None)
            v=loss(net,pack([row],[0]),dict(margin=.2,utility_weight=.1));v.backward();self.assertEqual(float(v),0.);self.assertEqual(float(net.output.weight.grad.abs().sum()),0.)


if __name__=='__main__':unittest.main()
