import unittest
import numpy as np
from .movement_bias_edit import calibrate,statistics,choose


class MovementBiasTests(unittest.TestCase):
    def test_bounded_search_and_support(self):
        logits=np.zeros((4,9),np.float32);logits[:,0]=.1;labels=np.full(4,1);support=np.zeros((4,9),bool);support[:,:2]=True
        bias,trace=calibrate(logits,labels,support,.3,dict(passes=2,step=.1))
        self.assertLessEqual(float(abs(bias).max()),.300001)
        self.assertEqual(statistics(logits,labels,support,bias)['correct'],4)
        logits[:,8]=100
        self.assertEqual(statistics(logits,labels,support,bias)['correct'],4)

    def test_identity_is_eligible_and_preserved(self):
        bias,trace=calibrate(np.zeros((1,9)),np.zeros(1,int),np.ones((1,9),bool),0,dict(passes=2,step=.1))
        self.assertEqual(bias.tolist(),[0.]*9);self.assertEqual(trace,[])
        baseline=dict(bound=0,correct=3,nll=1.);edited=dict(bound=.1,correct=3,nll=1.)
        self.assertEqual(choose([edited,baseline]),baseline)


if __name__=='__main__':unittest.main()
