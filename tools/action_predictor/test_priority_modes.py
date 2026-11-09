"""Distribution, decoding and training/inference checks, not quality evidence."""
import unittest
from unittest import mock
import torch
from torch import nn
from .priority_modes import AbsolutePriorityModes,logistic_log_mass


class PriorityModeTests(unittest.TestCase):
    def head(self):return AbsolutePriorityModes(nn.Linear(128,2),[-1400,0,1400],[2,8,2])

    def test_rng_initialization_and_parameter_count(self):
        original=nn.Linear(128,2);state=torch.get_rng_state().clone()
        head=AbsolutePriorityModes(original,[-1,1],[4,6]);self.assertTrue(torch.equal(state,torch.get_rng_state()))
        self.assertEqual(sum(p.numel() for p in head.parameters()),(2+3)*168)
        x=torch.randn(4,128);f=torch.randn(4,39)
        torch.testing.assert_close(head(x,f)[:,-2:],original(x),atol=1e-6,rtol=1e-6)

    def test_normalization_with_analytic_tail_mass(self):
        head=self.head();raw=torch.zeros(1,6,dtype=torch.float64)
        integers=torch.arange(-2000,2001);repeated=raw.expand(len(integers),-1)
        mass=head.log_mass(repeated,integers).exp().sum()
        fallback=raw[:,:-2].softmax(-1)[0,-1]
        tail=2*torch.sigmoid(torch.tensor(-20.005,dtype=torch.float64))*fallback
        self.assertAlmostEqual(float(mass+tail),1.,places=12)

    def test_unseen_integer_has_finite_mass_and_can_win(self):
        head=self.head();raw=torch.zeros(1,6,dtype=torch.float64)
        raw[:,:-2]=-100;raw[:,3]=100;raw[:,-2]=5.47;raw[:,-1]=-6
        self.assertTrue(torch.isfinite(head.log_mass(raw,torch.tensor([547]))).all())
        self.assertEqual(int(head.integer(raw)[0]),547)
        self.assertTrue(torch.isfinite(head.log_mass(raw,torch.tensor([2**31-1]))).all())

    def test_decoder_matches_bruteforce_even_with_overlap(self):
        torch.manual_seed(42);head=AbsolutePriorityModes(nn.Linear(128,2),[-7,0,6],[1,2,1])
        raw=torch.randn(12,6,dtype=torch.float64);raw[:,-2]*=.05;raw[:,-1]=-4
        integers=torch.arange(-100,101);brute=[]
        for row in raw:
            logp=head.log_mass(row[None].expand(len(integers),-1),integers)
            brute.append(int(integers[logp.argmax()]))
        self.assertEqual(head.integer(raw).tolist(),brute)

    def test_gradient_for_unseen_and_known_values(self):
        head=self.head();x=torch.randn(2,128);f=torch.randn(2,39)
        loss=-head.log_mass(head(x,f),torch.tensor([547,1400])).sum()/256
        loss.backward();self.assertTrue(torch.isfinite(head.linear.weight.grad).all())
        self.assertGreater(float(head.linear.weight.grad.abs().sum()),0)

    def test_control_masks_recovered_inputs(self):
        head=self.head();head.use_inputs=False
        with torch.no_grad():head.linear.weight[:,128:].normal_()
        x=torch.randn(3,128);a=torch.randn(3,39)
        torch.testing.assert_close(head(x,a),head(x,a+100),atol=0,rtol=0)

    def test_fit_dependency_rejection_precedes_consumption(self):
        from . import priority_modes_fit as runner
        with mock.patch.object(runner,'verify_protocol',side_effect=AssertionError('forced rejection')),mock.patch.object(runner,'gate') as gate:
            with self.assertRaisesRegex(AssertionError,'forced rejection'):runner.fit()
            gate.assert_not_called()

    def test_roundtrip_dependency_rejection_precedes_consumption(self):
        from . import priority_modes_roundtrip as runner
        with mock.patch.object(runner,'verify_protocol',side_effect=AssertionError('forced rejection')),mock.patch.object(runner,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'forced rejection'):runner.run()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
