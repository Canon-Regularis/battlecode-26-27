"""Distinct ranks, explanation marginalization and actual optimizer inclusion."""
import unittest
import torch
from .measurement import distinct_candidate_rank,target_credits
from ..priority_residual_modes import AnchoredPriorityModes


class TestMeasurement(unittest.TestCase):
    def test_rank_deduplicates_and_respects_integer_ties(self):
        candidates=torch.tensor([[1,1,2,3],[1,2,2,3]])
        logmass=torch.tensor([[-1.,-1.,-2.,-3.],[-2.,-2.,-2.,-3.]],dtype=torch.float64)
        target=torch.tensor([2,2])
        rank=distinct_candidate_rank(candidates,logmass,target,torch.tensor([-2.00000001,-2.00000001]))
        torch.testing.assert_close(rank,torch.tensor([2,2]))

    def test_equivalent_absolute_residual_explanations_remain_marginalized(self):
        original=torch.nn.Linear(128,2)
        model=AnchoredPriorityModes(original,[-3,2],[1,1],[-1,0],[1,1])
        with torch.no_grad():
            model.linear.weight.zero_();model.linear.bias.zero_()
        raw=model(torch.zeros(2,128),torch.zeros(2,39))
        values=torch.zeros(2,7,dtype=torch.int64)
        values[0,4]=-2;values[0,5]=1
        target=torch.tensor([2,2])
        total,credit=target_credits(model,raw,values,target)
        torch.testing.assert_close(total,model.log_mass(raw,target,values),rtol=1e-12,atol=1e-12)
        torch.testing.assert_close(credit.sum(-1),torch.ones(2,dtype=torch.float64),rtol=1e-12,atol=1e-12)
        self.assertGreater(float(credit[0,0].detach()),.4)
        self.assertGreater(float(credit[0,1].detach()),.4)
        self.assertEqual(float(credit[1,1].detach()),0)
        optimizer=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=0)
        parameters=list(model.parameters())
        self.assertEqual(len(parameters),2)
        self.assertEqual({id(p) for p in parameters},{id(p) for g in optimizer.param_groups for p in g['params']})
        # Explanation credits are a measurement, not the training objective.
        (-model.log_mass(raw,target,values).mean()).backward()
        for parameter in parameters:
            self.assertTrue(parameter.requires_grad)
            self.assertTrue(torch.isfinite(parameter.grad).all())


if __name__=='__main__':
    unittest.main()
