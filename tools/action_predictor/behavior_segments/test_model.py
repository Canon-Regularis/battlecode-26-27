import copy,unittest
import numpy as np
import torch
from . import model
from .data import FEATURES
from .study import endpoint_labels,loss_terms,targets
from ..goal_position import model as gm


class CausalPolicyTests(unittest.TestCase):
    def fixture(self):
        row=dict(observation=dict(own=dict(entity=dict(kind=1,index=0),known=15,team=0,position=dict(x=1,y=1),health=100),entities=[]),
            supplement=dict(own=dict(health=100),movement=[dict(x=2,y=1)],pre='1:0'))
        route=dict(width=5,height=5,blocked=[],spawns=[dict(minX=0,maxX=1,minY=0,maxY=1),dict(minX=4,maxX=5,minY=4,maxY=5)],altars=[dict(x=3,y=3)],submit_range=1)
        steps=[dict(observed=True,input=copy.deepcopy(row),previous=[0.]*len(FEATURES),previous_mask=[0.]*len(FEATURES),
            behavior=[0.]*len(FEATURES),behavior_mask=[1.]*len(FEATURES),round=i+1,movement=[1,0],event=f'{i+2}:0') for i in range(4)]
        w=dict(steps=steps);keys=gm.schema([row]);return w,route,keys

    def test_future_and_target_perturbation_cannot_change_prefix(self):
        w,r,k=self.fixture();torch.manual_seed(3);net=model.SegmentPolicy(k).eval();a,_=model.encode_window(w,r,k)
        with torch.no_grad():original=net(**a)
        w['steps'][3]['input']['observation']['own']['health']=1
        w['steps'][3]['previous'][0]=99
        for s in w['steps']:s['behavior']=[99.]*len(FEATURES);s['movement']=[-1,0]
        b,_=model.encode_window(w,r,k)
        with torch.no_grad():changed=net(**b)
        for name in ('goal','move','code'):torch.testing.assert_close(original[name][:3],changed[name][:3])

    def test_streaming_state_matches_batch(self):
        w,r,k=self.fixture();net=model.SegmentPolicy(k).eval();a,_=model.encode_window(w,r,k)
        def part(start,end):return {name:({s:v[start:end] for s,v in value.items()} if name=='batch' else value[start:end]) for name,value in a.items()}
        with torch.no_grad():whole=net(**a);first=net(**part(0,2));last=net(**part(2,4),state=first['state'])
        for name in ('goal','move','code'):torch.testing.assert_close(whole[name][2:],last[name],atol=1e-6,rtol=1e-5)

    def test_endpoint_censoring_and_missing_masks(self):
        w,r,k=self.fixture();goals,counts=endpoint_labels(w,[0,0,1,1],r)
        self.assertEqual(goals,[[1,1],[1,1],None,None]);self.assertEqual(counts['right_censored_turns'],2)
        w['steps'][2]['observed']=False
        goals,_=endpoint_labels(w,[0,0,1,1],r);self.assertEqual(goals,[None]*4)
        args,_=model.encode_window(w,r,k);self.assertEqual(float(args['batch']['grid'][2].abs().sum()),0)

    def test_supported_likelihood_and_finite_training_gradients(self):
        w,r,k=self.fixture();a,_=model.encode_window(w,r,k);net=model.SegmentPolicy(k);output=net(**a)
        support,movement,goals=targets(w,[[2,1],[2,1],None,None],5)
        terms=loss_terms(output,support,movement,goals,torch.tensor([0,0,1,1]),a['observed'])
        loss=terms[0]+.2*terms[1]+.2*terms[2];loss.backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters()))
        probabilities=output['move'].masked_fill(~support,-1e9).softmax(-1)
        self.assertTrue(torch.all(probabilities[~support]==0))
        torch.testing.assert_close(probabilities.sum(-1),torch.ones(4))


if __name__=='__main__':unittest.main()
