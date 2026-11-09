import unittest
import torch
from .goal_execution import GoalExecutor
from .universal_execution_fit import select,records


class UniversalExecutionTests(unittest.TestCase):
    def test_fallback_ignores_goal_and_starts_exact(self):
        torch.manual_seed(4);net=GoalExecutor(False);x=torch.randn(3,704);raw=torch.randn(3,9);g=torch.randn(3,9,8)
        self.assertTrue(torch.equal(net(x,g,raw),raw))
        with torch.no_grad():net.layers[-1].weight.fill_(.1)
        self.assertTrue(torch.equal(net(x,g,raw),net(x,g*100,raw)))

    def test_selection_preserves_nll_guard(self):
        cs=[dict(epoch=0,rows=100,correct=50,nll_sum=100.),dict(epoch=4,rows=100,correct=60,nll_sum=102.),dict(epoch=8,rows=100,correct=55,nll_sum=100.5)]
        self.assertEqual(select(cs)['epoch'],8)
        self.assertEqual(select(cs[:2])['epoch'],0)

    def test_population_includes_movement_without_future_goal(self):
        data={'movement_labels':torch.tensor([[-1,2,4],[8,-1,0]])};ids=[dict(key=str(i),group=str(i),fold=i,canonical=True) for i in range(2)]
        rows=records(data,ids);self.assertEqual([(r['window'],r['position'],r['label']) for r in rows],[(0,1,2),(0,2,4),(1,0,8),(1,2,0)])


if __name__=='__main__':unittest.main()
