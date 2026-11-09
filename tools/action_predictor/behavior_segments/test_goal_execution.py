import copy,unittest
import torch
from .goal_execution import GoalExecutor,goal_geometry,local_features
from .strategic_waypoint import labels


class Tests(unittest.TestCase):
    def test_matching_initialization_identity_and_goal_mask(self):
        torch.manual_seed(1);a=GoalExecutor(True);torch.manual_seed(1);b=GoalExecutor(False)
        for k,v in a.state_dict().items():self.assertTrue(torch.equal(v,b.state_dict()[k]))
        x=torch.randn(3,704);g=torch.randn(3,9,8);base=torch.randn(3,9)
        self.assertTrue(torch.equal(a(x,g,base),base));self.assertTrue(torch.equal(b(x,g,base),base))
        with torch.no_grad():a.layers[-1].weight.fill_(.1);b.layers[-1].weight.fill_(.1)
        self.assertTrue(torch.equal(b(x,g,base),b(x,g+2,base)));self.assertFalse(torch.equal(a(x,g,base),a(x,g+2,base)))
        self.assertEqual(local_features(x).shape,(3,9,128));self.assertEqual(sum(p.numel() for p in a.parameters()),8833)
        g.requires_grad_();a(x,g,base).sum().backward();self.assertTrue(torch.isfinite(g.grad).all());self.assertGreater(float(g.grad.abs().sum()),0.)

    def test_goal_geometry_current_only_and_support(self):
        current=dict(observation=dict(own=dict(position=dict(x=2,y=2))));route=dict(width=6,height=6,blocked=[])
        east=goal_geometry(current,route,(5,2));west=goal_geometry(current,route,(0,2))
        self.assertGreater(float(east[5,5]),float(east[3,5]));self.assertLess(float(west[5,5]),float(west[3,5]))
        changed=copy.deepcopy(current);changed['future_command']=[9,9];self.assertTrue(torch.equal(east,goal_geometry(changed,route,(5,2))))
        self.assertIsNone(goal_geometry(current,route,(10,2)));self.assertIsNone(goal_geometry(None,route,(5,2)))
        logits=torch.randn(9);support=torch.zeros(9,dtype=torch.bool);support[[4,5]]=True;prob=logits.masked_fill(~support,-1e9).softmax(-1)
        self.assertAlmostEqual(float(prob.sum()),1.,places=6);self.assertEqual(float(prob[~support].sum()),0.)

    def test_hindsight_labels_reject_relocations_and_censor(self):
        steps=[dict(observed=True,input=dict(observation=dict(own=dict(position=dict(x=i,y=1))))) for i in range(10)];w=dict(steps=steps);h=[[]]+[[[1,0]] for _ in range(9)]
        self.assertEqual(len(labels(w,h,2)),8);self.assertEqual(len(labels(w,h,8)),2)
        w['steps'][4]['input']['observation']['own']['position']=None;self.assertEqual(len(labels(w,h,8)),0)


if __name__=='__main__':unittest.main()
