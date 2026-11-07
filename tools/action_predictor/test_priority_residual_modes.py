"""Correct distribution/causal arithmetic, not evidence of prediction quality."""
import unittest
from unittest.mock import patch
import torch
from .priority_residual_modes import AnchoredPriorityModes


class ResidualModesTests(unittest.TestCase):
    def setUp(self):
        self.original=torch.nn.Linear(128,2)
        self.model=AnchoredPriorityModes(self.original,[-2,2],[1,1],[0,4],[1,1])
        self.values=torch.zeros((1,7),dtype=torch.int64)
        self.values[:,4]=-2;self.values[:,5]=1
        self.raw=torch.tensor([[0.,0.,0.,0.,-4.,0.,0.]],requires_grad=True)

    def test_duplicate_point_mass_and_loss_match_decoder(self):
        candidates,logp=self.model.candidate_log_masses(self.raw,self.values)
        for value in torch.unique(candidates):
            expected=self.model.log_mass(self.raw,value[None],self.values)
            torch.testing.assert_close(logp[candidates==value],expected.expand(int((candidates==value).sum())))
        self.assertEqual(int(self.model.integer(self.raw,self.values)[0]),2)

    def test_normalized_and_missing_mask(self):
        self.raw.data[:,-1]=-2
        targets=torch.arange(-1000,1001)
        for available in (0,1):
            self.values[:,5]=available
            if not available:self.values[:,4]=0
            logp=self.model.log_mass(self.raw.expand(len(targets),-1),targets,self.values.expand(len(targets),-1))
            self.assertAlmostEqual(float(logp.exp().sum().detach()),1.,places=10)

    def test_missing_ignores_masked_residual_logits(self):
        self.values.zero_()
        before=self.model.log_mass(self.raw,torch.tensor([2]),self.values)
        changed=self.raw.detach().clone();changed[:,2:4]=1000
        torch.testing.assert_close(before,self.model.log_mass(changed,torch.tensor([2]),self.values))

    def test_unseen_shift_and_negative_anchor(self):
        self.values[:,4]=-784
        self.raw.data[:,:5]=torch.tensor([[-10.,-10.,10.,-10.,-10.]])
        self.assertEqual(int(self.model.integer(self.raw,self.values)[0]),784)
        self.assertNotIn(784,self.model.absolute.tolist())

    def test_gradient_and_signed_tail(self):
        loss=-self.model.log_mass(self.raw,torch.tensor([-(2**31)]),self.values).sum()
        self.assertTrue(bool(torch.isfinite(loss)))
        loss.backward();self.assertTrue(bool(torch.isfinite(self.raw.grad).all()))

    def test_global_argmax_matches_brute(self):
        generator=torch.Generator().manual_seed(175)
        for _ in range(25):
            raw=torch.randn((1,7),generator=generator);raw[:,-2:]*=.01
            targets=torch.arange(-40,41)
            logp=self.model.log_mass(raw.expand(len(targets),-1),targets,self.values.expand(len(targets),-1))
            self.assertEqual(int(self.model.integer(raw,self.values)[0]),int(targets[logp.argmax()]))

    def test_rng_preservation_and_frozen_start(self):
        state=torch.get_rng_state()
        model=AnchoredPriorityModes(self.original,[-2,2],[1,1],[0,4],[1,1])
        self.assertTrue(torch.equal(state,torch.get_rng_state()))
        torch.testing.assert_close(model.linear.weight[-2:,:128],self.original.weight)
        self.assertEqual(int(torch.count_nonzero(model.linear.weight[:-2])),0)

    def test_exact_input_integer_domain(self):
        self.values[:,4]=-(2**31)
        self.model.integer(self.raw,self.values)
        self.values[:,4]=2**31
        with self.assertRaises(AssertionError):self.model.integer(self.raw,self.values)

    def test_fit_rejection_precedes_consumption(self):
        from . import priority_residual_fit as entry
        with patch.object(entry,'verify_protocol',side_effect=AssertionError('reject')),patch.object(entry,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'reject'):entry.fit()
            load.assert_not_called()

    def test_roundtrip_rejection_precedes_consumption(self):
        from . import priority_residual_roundtrip as entry
        with patch.object(entry,'verify_protocol',side_effect=AssertionError('reject')),patch.object(entry,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'reject'):entry.run()
            load.assert_not_called()


if __name__=='__main__':unittest.main()
