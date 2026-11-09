import unittest
import torch
from .crossfit_goals import RawGoalSelector,training_head,selected_head,head_exclusions,selector_features


class CrossfitGoalTests(unittest.TestCase):
    def test_nested_exclusion_and_size_matched_control(self):
        for outer in [0,1,2,3,None]:
            for group in range(4):
                a=head_exclusions(selected_head(outer,group,True));b=head_exclusions(selected_head(outer,group,False));self.assertEqual(len(a),len(b))
                if outer is not None:self.assertIn(outer,a);self.assertIn(outer,b)
                if outer==group:self.assertEqual(a,b)
                else:self.assertIn(group,a);self.assertNotIn(group,b)

    def test_rejects_outer_training_and_learned_context(self):
        with self.assertRaises(ValueError):training_head(1,1,True)
        with self.assertRaises(ValueError):selector_features(torch.zeros(704),[0.]*12)
        self.assertEqual(selector_features(torch.zeros(648),[0.]*12).shape,(660,))

    def test_no_learned_encoder_and_finite_backward(self):
        net=RawGoalSelector();self.assertEqual(set(net.state_dict()),{'net.0.weight','net.0.bias','net.2.weight','net.2.bias'});x=torch.randn(5,660);y=net(x);self.assertTrue((y.abs()<=1).all());y.square().mean().backward();self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters()))


if __name__=='__main__':unittest.main()
