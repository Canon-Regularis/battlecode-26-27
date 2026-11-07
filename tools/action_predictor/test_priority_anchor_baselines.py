"""Fixed-prior normalization, causal arithmetic and missing-anchor correctness."""
import unittest
from unittest import mock
import numpy as np
import torch
from . import priority_anchor_baselines as b


class PriorityAnchorTests(unittest.TestCase):
    def family(self,name):return next(f for f in b.FAMILIES if f['name']==name)

    def test_normalization_including_analytic_tail(self):
        prior=b.prior_fit(np.array([-2,0,3],np.int64));target=np.arange(-100,101,dtype=np.int64)
        mass=np.exp(b.prior_log_mass(prior,target)).sum()
        scale=np.exp(np.clip(prior['log_scale_fp32'],-6,5));mean=prior['location_fp32']
        tail=1/(1+np.exp((100.5/100+mean)/scale))+1/(1+np.exp((100.5/100-mean)/scale))
        fallback=torch.tensor(prior['logits_fp32'],dtype=torch.float64).softmax(-1)[-1].item()
        self.assertAlmostEqual(mass+tail*fallback,1.,places=12)

    def test_signed_anchor_residual_can_forecast_unseen_absolute_value(self):
        values=np.array([[700,1,700,1,700,1,0],[-700,1,-700,1,-700,1,0]],np.int64)
        priors=b.fit_priors(values,np.array([-700,700],np.int64));family=self.family('current_minus_residual')
        probe=np.array([[701,1,701,1,701,1,0]],np.int64)
        self.assertEqual(b.forecast(family,priors,probe).tolist(),[-701])
        self.assertTrue(np.isfinite(b.log_mass(family,priors,probe,np.array([-701],np.int64))).all())
        positive=priors['current_plus_residual']
        self.assertEqual(positive['recorded_plus1400'],1);self.assertEqual(positive['recorded_minus1400'],1)

    def test_zero_value_distinguished_from_unavailable_anchor(self):
        train=np.array([[0,1,0,1,0,1,0]]*3,np.int64)
        priors=b.fit_priors(train,np.array([7,7,9],np.int64))
        probe=np.array([[0,1,0,1,0,1,0],[0,1,0,1,0,0,0]],np.int64)
        self.assertEqual(b.forecast(self.family('latest_plus_copy'),priors,probe).tolist(),[0,7])

    def test_copy_mode_stays_literal_and_full_support(self):
        prior=b.prior_fit(np.array([1400,1400,1400],np.int64),copy=True)
        self.assertEqual(b.prior_mode(prior),0)
        self.assertTrue(np.isfinite(b.prior_log_mass(prior,np.array([2**31-1,-2**31],np.int64))).all())

    def test_no_row_adjacency_and_deterministic_ties(self):
        values=np.array([[2,1,2,1,2,1,0],[3,1,3,1,3,1,0]],np.int64)
        priors=b.fit_priors(values,np.array([4,5],np.int64));family=self.family('current_plus_residual')
        original=b.forecast(family,priors,values)
        np.testing.assert_array_equal(b.forecast(family,priors,values[::-1]),original[::-1])
        self.assertEqual(b.prior_mode(b.prior_fit(np.array([-1,1],np.int64))),-1)

    def test_half_integer_fallback_tie_selects_smallest_global_mode(self):
        prior=b.prior_fit(np.r_[np.arange(-1000,-980),np.arange(1000,1020)])
        prior['location_fp32']=.375;prior['log_scale_fp32']=-6.
        mass=b.prior_log_mass(prior,np.array([37,38],np.int64))
        self.assertEqual(mass[0],mass[1])
        self.assertEqual(b.prior_mode(prior),37)

    def test_no_label_rounding_or_integer_overflow(self):
        with self.assertRaisesRegex(AssertionError,'never round'):b.integers(np.array([1.5]))
        with self.assertRaises(OverflowError):b.differences(np.array([2**63-1],np.int64),np.array([-1],np.int64))
        with self.assertRaisesRegex(AssertionError,'alignment'):b.differences(np.array([1,2]),np.array([1]))

    def test_evaluation_rejection_precedes_development_loading(self):
        with mock.patch.object(b,'verify_protocol',side_effect=AssertionError('forced rejection')),mock.patch.object(b,'gate') as gate:
            with self.assertRaisesRegex(AssertionError,'forced rejection'):b.evaluate()
            gate.assert_not_called()

if __name__=='__main__':unittest.main()
