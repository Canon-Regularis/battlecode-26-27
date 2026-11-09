import unittest
import torch
from .planner_weight_edit import edit,simulate
from .objective_policy import ObjectiveHead


class WeightEditTests(unittest.TestCase):
    def test_only_output_weights_change_and_scores_match(self):
        net=ObjectiveHead();before={k:v.clone() for k,v in net.state_dict().items()};x=torch.randn(7,68);hidden=net.net[1](net.net[0](x));raw=net.net[2](hidden)
        changed=edit(before,.5,-.25);net.load_state_dict(changed)
        torch.testing.assert_close(net(x),torch.tanh(.5*raw-.25).flatten())
        for k,v in before.items():
            if not k.startswith('net.2.'):self.assertTrue(torch.equal(changed[k],v))
        identity=edit(before,1.,0.);self.assertTrue(all(torch.equal(v,identity[k]) for k,v in before.items()))

    def test_disabled_control_preserves_direct_predictions(self):
        net=ObjectiveHead();bank=dict(weights=net.state_dict(),records=[dict(key='w',label=2,baseline=2,candidates=[dict(key='g')],routes=[5],hidden=torch.zeros(1,64),utilities={'g':1.})])
        s=simulate(bank,disabled=True);self.assertEqual(s['correct'],1);self.assertEqual(s['active'],0);self.assertEqual(s['utility_sum'],0)


if __name__=='__main__':unittest.main()
