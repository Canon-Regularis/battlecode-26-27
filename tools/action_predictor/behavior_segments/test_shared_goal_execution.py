import unittest
import torch
from .shared_goal_execution import SharedGoalExecutor,optional_goal


class SharedExecutionTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(70001);self.net=SharedGoalExecutor();self.x=torch.randn(4,704);self.raw=torch.randn(4,9);self.goal=torch.randn(4,9,9);self.goal[...,7]=1

    def test_initial_parity_both_goal_states(self):
        self.assertTrue(torch.equal(self.net(self.x,self.goal,self.raw),self.raw));self.assertTrue(torch.equal(self.net(self.x,torch.zeros_like(self.goal),self.raw),self.raw))
        self.assertEqual(sum(p.numel() for p in self.net.parameters()),8897)

    def test_absent_goal_masks_stale_values_but_executor_still_runs(self):
        with torch.no_grad():self.net.layers[-1].weight.fill_(.1)
        stale=self.goal.clone();stale[...,7]=0
        value=self.net(self.x,stale,self.raw);self.assertTrue(torch.equal(value,self.net(self.x,torch.zeros_like(stale),self.raw)));self.assertFalse(torch.equal(value,self.raw))
        self.assertTrue(torch.equal(optional_goal(None,None,None),torch.zeros(9,9)))

    def test_blind_ignores_all_goal_fields(self):
        self.net.conditioned=False
        with torch.no_grad():self.net.layers[-1].weight.fill_(.1)
        self.assertTrue(torch.equal(self.net(self.x,self.goal,self.raw),self.net(self.x,torch.zeros_like(self.goal),self.raw)))

    def test_shared_weights_receive_both_strata_and_goal_gradient(self):
        with torch.no_grad():self.net.layers[-1].weight.fill_(.1)
        for g in (self.goal,torch.zeros_like(self.goal)):
            self.net.zero_grad();loss=torch.nn.functional.cross_entropy(self.net(self.x,g,self.raw),torch.tensor([0,1,2,3]));loss.backward();grad=self.net.layers[0].weight.grad
            self.assertTrue(torch.isfinite(grad).all());self.assertGreater(float(grad[:,:128].abs().sum()),0)
            if g[...,7].sum():self.assertGreater(float(grad[:,128:].abs().sum()),0)
            else:self.assertEqual(float(grad[:,128:].abs().sum()),0)


if __name__=='__main__':unittest.main()
