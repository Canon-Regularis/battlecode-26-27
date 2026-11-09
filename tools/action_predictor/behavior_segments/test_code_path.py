import copy
import unittest
import torch
from . import model
from .code_path_movement import candidate_features,FEATURE_NAMES,PathCorrection,PathMovementPolicy
from .test_model import CausalPolicyTests


class CodePathTests(unittest.TestCase):
    def test_unknown_entities_and_targets_cannot_enter_inputs(self):
        w,r,k=CausalPolicyTests().fixture();current=w['steps'][0]['input']
        a=candidate_features(current,r)
        current['observation']['entities'].append(dict(entity=dict(kind=2,index=99),known=0,position=dict(x=2,y=1),health=999))
        current['current_command']=dict(destination=dict(x=2,y=1))
        self.assertTrue(torch.equal(a,candidate_features(current,r)))
        current['observation']['entities'][0]['known']=1
        self.assertFalse(torch.equal(a,candidate_features(current,r)))
        self.assertEqual(float(candidate_features(None,r).abs().sum()),0.)
        current['observation']['own'].pop('position')
        self.assertEqual(float(candidate_features(current,r).abs().sum()),0.)

    def test_static_path_progress_respects_obstacle_and_orientation(self):
        w,r,k=CausalPolicyTests().fixture();current=w['steps'][0]['input']
        current['observation']['own']['position']=dict(x=1,y=2)
        r['altars']=[dict(x=3,y=2)];r['blocked']=[2,7,12,17]
        features=candidate_features(current,r);channel=FEATURE_NAMES.index('altar/terrain_progress')
        # The wall at x2 ends at y3: south, toward the gap at y4, is useful.
        self.assertEqual(float(features[model.OFFSETS.index((0,1)),channel]),1.)
        self.assertEqual(float(features[model.OFFSETS.index((0,-1)),channel]),-1.)

    def test_zero_parity_code_conditioning_and_frozen_backbone(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k)
        geometry=torch.stack([candidate_features(s['input'],r) for s in w['steps']])
        base=model.SegmentPolicy(k);head=PathCorrection(torch.ones(8)/8);net=PathMovementPolicy(base,head)
        with torch.no_grad():original=base(**args);zero=net(**args,geometry=geometry)
        for name in ('goal','code','state','move'):self.assertTrue(torch.equal(original[name],zero[name]))
        old=copy.deepcopy(base.state_dict());support,labels=model.move_support(w)
        out=net(**args,geometry=geometry);loss=torch.nn.functional.cross_entropy(out['move'].masked_fill(~support,-1e9),labels);loss.backward()
        self.assertTrue(all(p.grad is None for p in base.parameters()))
        torch.optim.AdamW(head.parameters(),lr=.01).step()
        self.assertTrue(all(torch.equal(v,base.state_dict()[n]) for n,v in old.items()))
        with torch.no_grad():head.coefficients.weight.normal_(std=.1)
        states=torch.randn(4,48+9*len(FEATURE_NAMES));prob=torch.randn(4,8).softmax(-1);baseline=torch.zeros(4,9)
        self.assertFalse(torch.equal(head(states,prob,baseline),head(states,prob.roll(1,-1),baseline)))
        control=PathCorrection(torch.ones(8)/8,False);control.load_state_dict(head.state_dict())
        self.assertTrue(torch.equal(control(states,prob,baseline),control(states,prob.roll(1,-1),baseline)))


if __name__=='__main__':unittest.main()
