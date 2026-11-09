import itertools,unittest
import numpy as np
from .segmentation import decode,ranges,fit,assign
from .data import descriptor,FEATURES


class SegmentationTests(unittest.TestCase):
    def test_dynamic_program_matches_exhaustive_search(self):
        rng=np.random.default_rng(2);cost=rng.random((6,3));penalty=.3
        labels,value=decode(cost,penalty,2);best=np.inf
        for candidate in itertools.product(range(3),repeat=6):
            segments=list(ranges(candidate))
            if any(b-a<2 for a,b,k in segments):continue
            v=sum(cost[i,k] for i,k in enumerate(candidate))+penalty*(len(segments)-1)
            best=min(best,v)
        self.assertAlmostEqual(value,best)
        self.assertTrue(all(b-a>=2 for a,b,k in ranges(labels)))

    def test_incidental_outlier_does_not_force_boundary(self):
        cost=np.array([[0.,4.]]*10);cost[4]=[1,0]
        labels,_=decode(cost,2,2);self.assertEqual(len(list(ranges(labels))),1)

    def test_recovers_sustained_change(self):
        cost=np.array([[0.,8.]]*5+[[8.,0.]]*5)
        labels,_=decode(cost,2,2);self.assertEqual(labels.tolist(),[0]*5+[1]*5)

    def test_fit_objective_does_not_increase(self):
        y=np.array([[-2.,0.]]*8+[[2.,1.]]*8);m=np.ones_like(y)
        trained=fit([(y,m),(y[::-1],m)],k=2,iterations=5,penalty=.2)
        self.assertTrue(np.all(np.diff([t['objective'] for t in trained['trace']])<=1e-9))
        self.assertEqual(len(list(ranges(assign(y,m,trained)))),2)

    def test_missing_outcome_does_not_become_zero_change(self):
        rs=[dict(family='ward',step={})]
        y,m=descriptor(rs,None,None,dict(altars=[]))
        self.assertEqual(len(y),len(FEATURES));self.assertEqual(m[-6:],[0.]*6)
        self.assertGreater(y[9],0)


if __name__=='__main__':unittest.main()
