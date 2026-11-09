import unittest
import torch
from .command_movement import command_step,command_window,CommandCorrection


class CommandMovementTests(unittest.TestCase):
    def test_signed_history_age_net_and_missing(self):
        empty,state=command_step([]);self.assertEqual(float(empty.abs().sum()),0)
        features,state=command_step([[1,0],[0,1]],state)
        self.assertEqual(features[7,1],1);self.assertEqual(features[8,5],1)
        self.assertAlmostEqual(float(features[8,7]),2**.5/2,places=6)
        aged,state=command_step([],state);self.assertEqual(aged[7,3],.5);self.assertEqual(float(aged[:,4:].abs().sum()),0)
        with self.assertRaises(ValueError):command_step(None,state)
        with self.assertRaises(ValueError):command_step([[3,0]],state)
        a=command_window([[],[[1,0]],[[0,1]]]);b=command_window([[],[[1,0]],[[-1,0]]])
        self.assertTrue(torch.equal(a[:2],b[:2]))

    def test_zero_head_parameter_counts_and_gradients(self):
        context=torch.randn(2,3,56);features=torch.randn(2,3,9,8);baseline=torch.randn(2,3,9)
        for hidden,count in [(0,456),(16,1048)]:
            head=CommandCorrection(hidden);self.assertEqual(sum(p.numel() for p in head.parameters()),count)
            out=head(context,features,baseline);self.assertTrue(torch.equal(out,baseline));out.square().mean().backward()
            self.assertTrue(any(p.grad is not None and p.grad.abs().sum()>0 for p in head.parameters()))


if __name__=='__main__':unittest.main()
