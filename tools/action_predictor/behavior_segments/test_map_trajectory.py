import unittest
import torch
from torch import nn
from types import SimpleNamespace
from .map_trajectory_weights import MapTrajectory
from .map_trajectory_fit import choose


class Fake(nn.Module):
    def __init__(self):
        super().__init__();self.maps=nn.Linear(2,2);self.code=nn.Linear(2,2);self.embeddings=nn.Parameter(torch.ones(2,2));self.query=nn.Linear(2,2);self.goal=nn.Linear(2,1);self.movement=nn.Linear(4,9)
    def forward(self,x):
        h=self.maps(x);c=self.code(h);return dict(code=c,move=self.movement(torch.cat((h,c.softmax(-1)@self.embeddings),-1)))


class Correction(nn.Module):
    def __init__(self):super().__init__();self.bias=nn.Parameter(torch.zeros(9))
    def forward(self,a,b,move):return move+self.bias


class Tests(unittest.TestCase):
    def test_freezing_and_raw_gradient(self):
        net=MapTrajectory(SimpleNamespace(backbone=Fake(),correction=Correction(),heading=Correction(),commands=Correction()))
        args=dict(x=torch.randn(3,2),geometry=torch.randn(3,9,2),heading=torch.randn(3,9,4),command_heading=torch.randn(3,9,8));out=net(args);out['move'].square().mean().backward()
        for name,p in net.backbone.named_parameters():
            if name.startswith(('code.','embeddings','query.','goal.')):self.assertIsNone(p.grad)
            else:self.assertIsNotNone(p.grad);self.assertTrue(torch.isfinite(p.grad).all())
        self.assertEqual(out['move'].shape,(3,9))

    def test_selection_protects_code_and_activity(self):
        a=dict(epoch=0,combined=10,nll=1.,code_correct=20,code_rows=20,active=2,available=10,utility_sum=1.)
        cs=[a,dict(a,epoch=1,combined=12,active=0),dict(a,epoch=2,combined=15,code_correct=0)]
        self.assertEqual(choose(cs,dict(code_accuracy_allowance=.01,minimum_activation=.1)),a)


if __name__=='__main__':unittest.main()
