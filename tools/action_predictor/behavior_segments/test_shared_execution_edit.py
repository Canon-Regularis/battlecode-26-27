import unittest
import torch
from .shared_goal_execution import SharedGoalExecutor
from .shared_execution_edit import edit


class SharedWeightEditTests(unittest.TestCase):
    def test_only_requested_weights_change(self):
        torch.manual_seed(4);net=SharedGoalExecutor()
        with torch.no_grad():net.layers[-1].weight.normal_()
        original={k:v.clone() for k,v in net.state_dict().items()};changed=edit(original,.5,.75)
        self.assertTrue(torch.equal(changed['layers.0.weight'][:,:128],original['layers.0.weight'][:,:128]));self.assertTrue(torch.equal(changed['layers.0.weight'][:,128:],original['layers.0.weight'][:,128:]*.5));self.assertTrue(torch.equal(changed['layers.2.weight'],original['layers.2.weight']*.75))
        for k in ('layers.0.bias','layers.2.bias'):self.assertTrue(torch.equal(changed[k],original[k]))
        self.assertTrue(all(torch.equal(original[k],v) for k,v in net.state_dict().items()))

    def test_no_disabling_or_negative_weights(self):
        state=SharedGoalExecutor().state_dict()
        for g,o in [(0,1),(1,0),(-1,1)]:
            with self.assertRaises(ValueError):edit(state,g,o)

    def test_output_scaling_is_exact_residual_scaling(self):
        torch.manual_seed(8);net=SharedGoalExecutor();x=torch.randn(4,704);g=torch.randn(4,9,9);g[...,7]=1;raw=torch.randn(4,9)
        with torch.no_grad():net.layers[-1].weight.normal_();net.layers[-1].bias.zero_()
        old=net(x,g,raw);net.load_state_dict(edit(net.state_dict(),1,.5));self.assertTrue(torch.allclose(net(x,g,raw),raw+.5*(old-raw),atol=1e-6))


if __name__=='__main__':unittest.main()
