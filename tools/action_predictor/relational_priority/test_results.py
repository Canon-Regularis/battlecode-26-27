"""Guard null support and paired whole-group, rather than absolute, comparisons."""
import unittest
import numpy as np
from .results import score,paired,calibration


def archive(integer,nll,confidence):
    n=len(integer)
    return dict(integer=np.asarray(integer,np.int64),nll=np.full(n,nll),mode_probability=np.full(n,confidence),
                rank=np.ones(n),credit=np.tile(np.array([[.4,.4,.2]]),(n,1)))


class ResultContracts(unittest.TestCase):
    def test_mode_calibration_is_conditional_and_handles_empty_support(self):
        p=archive([0,1],.5,.8);target=np.array([0,1]);mask=np.ones(2,bool)
        result=calibration(p,target,mask)
        self.assertAlmostEqual(result['ECE'],.2)
        self.assertAlmostEqual(result['mode_correctness_Brier'],.04)
        self.assertEqual(sum(row['rows'] for row in result['bins']),2)
        self.assertIsNone(calibration(p,target,~mask)['ECE'])
        self.assertIsNone(score(p,target,~mask)['accuracy'])
        self.assertIsNone(paired(p,p,target,np.array([1,2]),~mask)['accuracy_difference'])

    def test_paired_counts_and_group_resampling_keep_row_denominators(self):
        before=archive([0,0,2,0],1.,.5);after=archive([0,1,2,3],.5,.8)
        result=paired(after,before,np.arange(4),np.array([1,1,1,2]),np.ones(4,bool))
        self.assertEqual(result['rescues'],2);self.assertEqual(result['regressions'],0)
        self.assertEqual(result['net'],2);self.assertEqual(result['accuracy_difference'],.5)
        np.testing.assert_allclose(result['paired_accuracy_interval'],[1/3,1.])
        np.testing.assert_allclose(result['paired_NLL_interval'],[-.5,-.5])


if __name__=='__main__':unittest.main()
