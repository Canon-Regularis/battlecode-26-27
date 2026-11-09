import copy,unittest
import torch
from .heading_movement import heading_step,heading_window,HeadingCorrection,HeadingPolicy
from .test_joint_movement import JointMovementTests
from .joint_movement_weights import inference


class HeadingTests(unittest.TestCase):
    def current(self,x,y,actor=1):return dict(observation=dict(own=dict(entity=actor,position=None if x is None else dict(x=x,y=y))))

    def test_causality_missing_dead_actor_and_round_reset(self):
        zero,state=heading_step(self.current(2,2),10);self.assertEqual(float(zero.abs().sum()),0)
        missing,next_state=heading_step(None,11,state);self.assertEqual(next_state,state)
        features,next_state=heading_step(self.current(3,2),12,next_state)
        self.assertEqual(features[5].tolist(),[1,1,.5,.5]);self.assertEqual(features[3,0],-1)
        self.assertEqual(float(heading_step(self.current(4,2,2),13,next_state)[0].abs().sum()),0)
        self.assertEqual(float(heading_step(self.current(4,2),12,next_state)[0].abs().sum()),0)
        self.assertIsNone(heading_step(self.current(None,None),13,next_state)[1])
        w=dict(steps=[dict(input=self.current(2,2),observed=True,round=1,movement=[1,0]),dict(input=self.current(3,2),observed=True,round=2,movement=[-1,0])])
        changed=copy.deepcopy(w);changed['steps'][0]['movement']=[-1,0];changed['steps'][1]['movement']=[0,1]
        self.assertTrue(torch.equal(heading_window(w),heading_window(changed)))
        changed['steps'][-1]['input']=self.current(30,20)
        self.assertTrue(torch.equal(heading_window(w)[:-1],heading_window(changed)[:-1]))

    def test_zero_initial_parity_and_nonzero_gradients(self):
        net,item,args=JointMovementTests().fixture();parent=inference(copy.deepcopy(net));features=torch.randn(len(args['observed']),9,4)
        for hidden,count in [(0,228),(16,980)]:
            head=HeadingCorrection(hidden);policy=HeadingPolicy(copy.deepcopy(parent),head)
            self.assertEqual(sum(p.numel() for p in head.parameters()),count)
            before=parent(**args);after=policy(**args,heading=features)
            for k in ('move','code','goal'):self.assertTrue(torch.equal(before[k],after[k]))
            after['move'].square().mean().backward()
            self.assertTrue(all(p.grad is None for p in policy.parent.parameters()))
            self.assertTrue(any(p.grad is not None and p.grad.abs().sum()>0 for p in head.parameters()))


if __name__=='__main__':unittest.main()
