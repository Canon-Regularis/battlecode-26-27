import copy,inspect,unittest
import numpy as np
import torch
from .movement_mixture import MovementMixture,previous_direction
from .reliable_model import JointModel
from .targets import OFFSETS

class MovementMixtureTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(26);torch.set_num_threads(4)
        self.base=JointModel(253,24,15,dict(history=16,rich=True,spatial=True,constrain=True))
        self.x=torch.randn(4,253);self.h=torch.randn(4,32,24);self.grid=torch.zeros(4,289,20)
        self.grid[:,:,:2]=torch.as_tensor(OFFSETS/8).float();self.grid[:,:,3]=1;self.grid[:,:,5]=1
        self.grid[0,145,18]=1;self.grid[1,127,18]=1;self.grid[3,144,18]=1
        self.valid=torch.ones(4,289,dtype=torch.bool);self.family=torch.tensor([8,8,8,3]);self.rules=torch.zeros(4,5)

    def inputs(self):return self.x,self.h,self.grid,self.valid,self.family,self.rules

    def test_prior_is_only_last_recorded_offset_and_missing_explicit(self):
        offset,available,matching=previous_direction(self.grid)
        self.assertEqual(available.tolist(),[True,True,False,True]);self.assertEqual(offset[0].tolist(),[1,0]);self.assertTrue(matching[0,145]);self.assertFalse(matching[0,144]);self.assertEqual(offset[2].tolist(),[0,0])
        bad=self.grid.clone();bad[0,146,18]=1
        with self.assertRaises(ValueError):previous_direction(bad)

    def test_initial_distribution_matches_teacher_both_arms(self):
        with torch.no_grad():
            _,context=self.base(self.x,self.h);expected=self.base.parameter_logits(context,self.grid,self.valid,self.family,self.rules).softmax(-1)
            for specialized in (False,True):
                model=MovementMixture(copy.deepcopy(self.base),specialized).eval();lp,_,_=model(*self.inputs())
                torch.testing.assert_close(lp.exp(),expected,rtol=0,atol=2e-6)
                torch.testing.assert_close(lp.exp().sum(-1),torch.ones(4),rtol=0,atol=1e-6)
                self.assertTrue(torch.isfinite(lp).all())

    def test_missing_history_and_blocked_not_partitioned(self):
        a=MovementMixture(copy.deepcopy(self.base),False);b=MovementMixture(copy.deepcopy(self.base),True);b.load_state_dict(a.state_dict())
        with torch.no_grad():
            a.change.query.weight.add_(.05);b.change.query.weight.copy_(a.change.query.weight)
            first,_,_=a(*self.inputs());second,_,_=b(*self.inputs())
        torch.testing.assert_close(first[2:],second[2:],rtol=0,atol=1e-7)

    def test_finite_gradients_and_frozen_teacher(self):
        model=MovementMixture(copy.deepcopy(self.base),True);before={k:v.clone() for k,v in model.teacher.state_dict().items()}
        lp,gate,_=model(*self.inputs());loss=-lp[torch.arange(4),torch.tensor([145,0,288,144])].mean()+.05*torch.nn.functional.binary_cross_entropy_with_logits(gate[:2],torch.tensor([1.,0.]));loss.backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
        self.assertIsNone(model.teacher.current[0].weight.grad)
        self.assertIsNotNone(model.change.current[0].weight.grad);self.assertIsNotNone(model.continuation.current[0].weight.grad)
        for k,v in model.teacher.state_dict().items():self.assertTrue(torch.equal(v,before[k]))

    def test_no_next_direction_argument(self):
        names=list(inspect.signature(MovementMixture.forward).parameters)
        self.assertEqual(names,['self','x','history','grid','valid','family','rules','teacher_context'])

if __name__=='__main__':unittest.main()
