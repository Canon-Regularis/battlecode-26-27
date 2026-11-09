import copy
import unittest
import numpy as np
from .schema import encode,FIELDS


class OrderSchemaTests(unittest.TestCase):
    def fixture(self):
        return dict(own=dict(current=5,scheduled=7,current_available=True,scheduled_available=True),others=[
            dict(known=True,role='ally',current=-3,current_available=True,scheduled=9,scheduled_available=True),
            dict(known=True,role='ally',current=5,current_available=True,scheduled=12345,scheduled_available=False),
            dict(known=True,role='enemy',current=6,current_available=True,scheduled=7,scheduled_available=True)])

    def test_exact_relations_and_masks(self):
        x=encode(self.fixture())
        self.assertEqual(len(FIELDS),32)
        np.testing.assert_array_equal(x[:8],[1,2,-8,0,-4,.5,.5,0])
        np.testing.assert_array_equal(x[8:16],[1,1,2,2,2,0,0,1])
        np.testing.assert_array_equal(x[16:24],[1,1,1,1,1,0,0,1])
        np.testing.assert_array_equal(x[24:],[1,1,0,0,0,0,1,0])

    def test_unknown_values_and_identity_do_not_enter_features(self):
        row=self.fixture();before=encode(row)
        row['others'].append(dict(known=False,role='enemy',current=2147483647,current_available=True,
                                 scheduled=-2147483648,scheduled_available=True,entity_index=999999))
        row['target']=123456789
        np.testing.assert_array_equal(encode(row),before)
        row['others'].reverse()
        np.testing.assert_array_equal(encode(row),before)

    def test_missing_reference_explicit(self):
        row=copy.deepcopy(self.fixture())
        row['own']['current_available']=False;row['own']['current']=None
        x=encode(row)
        np.testing.assert_array_equal(x[:8],[0,2,0,0,0,0,0,0])


if __name__=='__main__':unittest.main()
