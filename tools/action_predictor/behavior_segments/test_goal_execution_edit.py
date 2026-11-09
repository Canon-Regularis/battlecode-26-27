import unittest
import torch
from .goal_execution import GoalExecutor
from .goal_execution_edit import edit,choose


class Tests(unittest.TestCase):
    def test_weight_edit_equals_input_and_output_calibration(self):
        torch.manual_seed(1);a=GoalExecutor();b=GoalExecutor()
        with torch.no_grad():a.layers[-1].weight.normal_();a.layers[-1].bias.fill_(.2)
        b.load_state_dict(edit(a.state_dict(),.25,True,.75));x=torch.randn(5,704);g=torch.randn(5,9,8);raw=torch.randn(5,9);adjusted=g.clone();adjusted[...,:5]*=.25;adjusted[...,6]=0
        self.assertTrue(torch.allclose(b(x,g,raw),raw+.75*(a(x,adjusted,raw)-raw),atol=2e-6))
        self.assertTrue(torch.equal(a.layers[0].weight[:,:128],b.layers[0].weight[:,:128]));self.assertTrue(torch.equal(a.layers[0].weight[:,133],b.layers[0].weight[:,133]));self.assertTrue(torch.equal(a.layers[0].bias,b.layers[0].bias))

    def test_selection_preserves_goal_execution_and_nll(self):
        base=dict(setting=dict(distance_scale=1.,zero_radius=False,output_scale=1.),correct=10,rows=20,nll_sum=10.,diagnostic_correct=18,diagnostic_rows=20,edit_squared_norm=0.)
        other=dict(base,setting=dict(distance_scale=.1,zero_radius=True,output_scale=.5),correct=15,diagnostic_correct=10,edit_squared_norm=1.)
        self.assertEqual(choose([base,other],dict(diagnostic_allowance=.02,causal_nll_allowance=.01)),base)


if __name__=='__main__':unittest.main()
