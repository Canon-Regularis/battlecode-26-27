import unittest
import numpy as np
import torch
from torch import nn
from .priority_head import PriorityHead,quantized_grid

class PriorityHeadTests(unittest.TestCase):
    def test_initial_baseline_and_rng_and_parameter_count(self):
        torch.manual_seed(26);original=nn.Linear(128,2);state=torch.get_rng_state().clone()
        head=PriorityHead(original,True);self.assertTrue(torch.equal(state,torch.get_rng_state()))
        self.assertEqual(sum(p.numel() for p in head.parameters()),336)
        x=torch.randn(5,128);f=torch.randn(5,39)
        torch.testing.assert_close(head(x,f),original(x),rtol=1e-6,atol=1e-6)

    def test_control_cannot_use_recovered_values(self):
        head=PriorityHead(nn.Linear(128,2),False)
        with torch.no_grad():head.linear.weight[:,128:].normal_()
        x=torch.randn(4,128);a=torch.randn(4,39);b=a+100
        torch.testing.assert_close(head(x,a),head(x,b),rtol=0,atol=0)
        head.use_inputs=True
        self.assertGreater(float((head(x,a)-head(x,b)).abs().max().detach()),1.)

    def test_training_grid_precision(self):
        raw=np.full((289,20),.33333334,dtype=np.float32)
        expected=raw.astype(np.float16).astype(np.float32)
        np.testing.assert_array_equal(quantized_grid(raw),expected)
        self.assertFalse(np.array_equal(raw,expected))

if __name__=='__main__':unittest.main()
