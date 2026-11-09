import unittest
import torch
from .objective_policy import choose,utility,ObjectiveHead,movement


class ObjectiveTests(unittest.TestCase):
    def test_retain_switch_abandon_and_invalidation(self):
        rows=[dict(key='a'),dict(key='b')]
        self.assertEqual(choose(rows,[.5,.6],'a')[1:],[ 'a','retain'] if False else ('a','retain'))
        self.assertEqual(choose(rows,[.1,.8],'a')[1:],('b','switch'))
        self.assertEqual(choose(rows,[-.1,-.2],'a')[1:],(None,'abstain'))
        self.assertEqual(choose(rows,[.1,.8],'missing')[1:],('b','switch'))
        self.assertEqual(choose([],[],'a')[1:],(None,'unavailable'))

    def test_future_utility_is_separate_from_prediction_and_support(self):
        route=dict(width=5,height=5,blocked=[]);candidate=dict(goal=(4,0),radius=0)
        self.assertEqual(utility(candidate,[(0,0),(1,0),(2,0)],route),1)
        self.assertEqual(utility(candidate,[(2,0),(1,0),(0,0)],route),-1)
        current=dict(observation=dict(own=dict(position=dict(x=0,y=0))),supplement=dict(movement=[dict(x=1,y=0)]))
        self.assertEqual(movement(candidate,current,route,[1.]*9),5)
        net=ObjectiveHead();x=torch.randn(2,68);loss=(net(x)-torch.tensor([1.,-1.])).square().mean();loss.backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters()))


if __name__=='__main__':unittest.main()
