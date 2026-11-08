"""Sufficient witnesses must not mistake coefficient tradeoffs for impossibility."""
import unittest
import numpy as np
from .bounds import find_witness


class BoundContracts(unittest.TestCase):
    def test_strict_both_coefficient_dominance_is_a_witness(self):
        values=np.array([1,2]);features=np.array([[True,False],[True,False]])
        self.assertEqual(find_witness(values,features,np.log([1.,2.]),np.log([.1,.2]),0),(1,2))

    def test_opposing_coefficients_are_not_blocked_for_nonzero_features(self):
        values=np.array([1,2]);features=np.array([[True],[True]])
        self.assertEqual(find_witness(values,features,np.log([1.,2.]),np.log([.2,.1]),0),(-1,0))
        shift=-10.
        self.assertGreater(np.logaddexp(np.log(1.)+shift,np.log(.2)),
                           np.logaddexp(np.log(2.)+shift,np.log(.1)))

    def test_zero_features_fix_order_but_different_features_do_not(self):
        values=np.array([1,2]);zero=np.zeros((2,2),bool)
        self.assertEqual(find_witness(values,zero,np.log([1.,2.]),np.log([.2,.1]),0),(1,1))
        different=np.array([[False,False],[True,False]])
        self.assertEqual(find_witness(values,different,np.log([1.,2.]),np.log([.2,.1]),0),(-1,0))

    def test_underflowed_fallbacks_are_compared_in_log_space(self):
        values=np.array([1,2]);features=np.array([[True],[True]])
        # Both ordinary exp values underflow; the target fallback is still larger.
        self.assertEqual(find_witness(values,features,np.log([1.,2.]),np.array([-1000.,-2000.]),0),(-1,0))


if __name__=='__main__':unittest.main()
