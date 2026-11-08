import unittest
import numpy as np
from .schema_asinh import encode
from . import test_schema


class CompressedSchemaTests(unittest.TestCase):
    def test_independent_expected_transform_and_exact_order(self):
        row=test_schema.OrderSchemaTests().fixture()
        x=encode(row)
        expected=np.array([np.arcsinh(-8),0,np.arcsinh(-8)/2],dtype=np.float32)
        np.testing.assert_array_equal(x[2:5],expected)
        np.testing.assert_array_equal(x[5:8],[.5,.5,0])

    def test_extremes_remain_finite_and_unknowns_excluded(self):
        row=test_schema.OrderSchemaTests().fixture()
        row['others'][0]['current']=-2147483648
        row['others'][1]['current']=2147483647
        x=encode(row)
        self.assertTrue(np.isfinite(x).all())
        self.assertLess(float(np.abs(x[2:5]).max()),23)
        row['others'].append(dict(known=False,role='ally',current=12,current_available=True,
                                 scheduled=12,scheduled_available=True))
        np.testing.assert_array_equal(encode(row),x)


if __name__=='__main__':unittest.main()
