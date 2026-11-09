import copy,unittest
import torch
from .strategic_waypoint import labels,WaypointHead,reachable_goal,features


class WaypointTests(unittest.TestCase):
    def fixture(self):
        steps=[dict(observed=True,input=dict(observation=dict(own=dict(position=dict(x=i,y=1))))) for i in range(10)]
        return dict(steps=steps),[[]]+[[[1,0]] for _ in range(9)]

    def test_future_labels_censored_at_window_and_relocations(self):
        w,h=self.fixture();r=labels(w,h);self.assertEqual(len(r),2);self.assertEqual(r[0]['offset'],[8,0])
        w['steps'][4]['input']['observation']['own']['position']['x']=20;self.assertEqual(labels(w,h),[])
        w,h=self.fixture();w['steps'][4]['observed']=False;self.assertEqual(len(labels(w,h)),2)
        w['steps'][8]['observed']=False;self.assertEqual(len(labels(w,h)),1)

    def test_head_identity_start_and_reachable_projection(self):
        net=WaypointHead();x=torch.randn(3,704);self.assertTrue(torch.equal(net(x),torch.zeros(3,2)))
        net(x).sum().backward();self.assertTrue(torch.isfinite(net.layers[-1].weight.grad).all())
        r=dict(width=4,height=4,blocked=[5]);self.assertNotEqual(reachable_goal((0,0),(1,1),r),(1,1))
        self.assertEqual(reachable_goal((0,0),(100,100),r),(3,3))


if __name__=='__main__':unittest.main()
