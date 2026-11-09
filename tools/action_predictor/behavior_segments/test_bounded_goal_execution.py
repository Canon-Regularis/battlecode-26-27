import unittest
import torch
from .goal_execution import GoalExecutor,goal_geometry
from .bounded_goal_execution import bounded_goal,BoundedGoalExecutor


class Tests(unittest.TestCase):
    def test_near_and_far_aligned_goals_have_same_local_features(self):
        current=dict(observation=dict(own=dict(position=dict(x=2,y=2))));route=dict(width=100,height=6,blocked=[])
        near=goal_geometry(current,route,(7,2));far=goal_geometry(current,route,(92,2));a,b=bounded_goal(near),bounded_goal(far)
        self.assertTrue(torch.equal(a,b));self.assertLessEqual(float(b.abs().max()),1.);self.assertEqual(float(bounded_goal(torch.zeros_like(near)).abs().sum()),0.)
        region=bounded_goal(goal_geometry(current,route,(7,2),4));self.assertEqual(float(region[5,4]),1.);self.assertEqual(float(region[3,4]),0.)

    def test_runtime_wrapper_matches_training_transform(self):
        torch.manual_seed(66001);raw=GoalExecutor(True);torch.manual_seed(66001);runtime=BoundedGoalExecutor(True)
        for k,v in raw.state_dict().items():self.assertTrue(torch.equal(v,runtime.state_dict()[k]))
        with torch.no_grad():raw.layers[-1].weight.normal_()
        runtime.load_state_dict(raw.state_dict());x=torch.randn(4,704);g=torch.randn(4,9,8);g[...,7]=1.;g[...,5].clamp_(-1,1);base=torch.randn(4,9)
        self.assertTrue(torch.equal(raw(x,bounded_goal(g),base),runtime(x,g,base)))
        raw(x,bounded_goal(g),base).sum().backward();self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in raw.parameters()))


if __name__=='__main__':unittest.main()
