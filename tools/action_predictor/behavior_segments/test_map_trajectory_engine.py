"""Common-denominator accumulation matches a direct full-batch update."""
import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from . import map_trajectory_fit as fit


class Tiny(nn.Module):
    def __init__(self):super().__init__();self.move=nn.Linear(3,9);self.code=nn.Linear(3,2)
    def forward(self,args):return dict(move=self.move(args['x']),code=self.code(args['x']))


class Tests(unittest.TestCase):
    def test_unequal_window_denominators_match_one_adam_update(self):
        torch.manual_seed(64002);actual=Tiny();expected=copy.deepcopy(actual)
        args=[dict(x=torch.randn(3,3),observed=torch.tensor([1.,1.,0.])),dict(x=torch.randn(3,3),observed=torch.tensor([1.,0.,1.]))]
        labels=torch.tensor([[1,2,-1],[-1,-1,3]])
        env=dict(windows=[dict(steps=[dict(observed=bool(o)) for o in a['observed']]) for a in args],data=dict(movement_labels=labels,support=torch.ones(2,3,9,dtype=torch.bool)),teacher=torch.full((2,3,2),.5))
        p=dict(trainable_parameters=sum(x.numel() for x in actual.parameters()),learning_rate=.0003,weight_decay=.01,clip=5.,seed=64001,batch_windows=8,coefficient=.7)
        opt=torch.optim.AdamW(expected.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay']);opt.zero_grad()
        for i in np.random.default_rng(p['seed']).permutation([0,1]):
            out=expected(args[i]);m=labels[i]>=0;o=args[i]['observed'].bool()
            loss=F.cross_entropy(out['move'][m],labels[i][m],reduction='sum')/3+.7*F.kl_div(out['code'][o].log_softmax(-1),env['teacher'][i][o],reduction='sum')/4
            loss.backward()
        torch.nn.utils.clip_grad_norm_(expected.parameters(),5.);opt.step()
        with tempfile.TemporaryDirectory() as directory,patch.object(fit,'encoded',side_effect=lambda env,i:args[i]):
            _,trace=fit.train(actual,env,np.array([0,1]),p,1,Path(directory)/'run',time.perf_counter()+60)
            self.assertEqual(trace[0]['denominators'],[[3,4]]);self.assertEqual(trace[0]['updates'],1)
            for k,v in actual.state_dict().items():self.assertTrue(torch.equal(v,expected.state_dict()[k]),k)


if __name__=='__main__':unittest.main()
