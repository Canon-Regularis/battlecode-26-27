import unittest
import numpy as np
import torch
from .filter import NeuralSemiMarkov,StateExecutionCondition


class SegmentFilterContracts(unittest.TestCase):
    def setUp(self):torch.manual_seed(3026)

    def test_forward_matches_explicit_state_age_enumeration(self):
        model=NeuralSemiMarkov(5,3,4).double();context=torch.randn(2,5,dtype=torch.float64)
        previous=torch.randn(2,3,4,dtype=torch.float64).flatten(1).log_softmax(1).reshape(2,3,4)
        p=model.predict(context,previous,torch.ones(2,dtype=torch.int64),torch.zeros(2,dtype=torch.bool))
        transition,end,stay=model.factors(context);expected=np.zeros((2,3,4))
        a=transition.detach().exp().numpy();h=end.detach().exp().numpy();old=previous.exp().numpy()
        for b in range(2):
            for state in range(3):
                for age in range(4):
                    for destination in range(3):expected[b,destination,0]+=old[b,state,age]*h[b,state,age]*a[b,state,destination]
                    if age<3:expected[b,state,age+1]+=old[b,state,age]*(1-h[b,state,age])
        np.testing.assert_allclose(p['logp'].detach().exp().numpy(),expected,rtol=1e-13,atol=1e-14)
        np.testing.assert_allclose(expected.sum((1,2)),1,rtol=0,atol=1e-14)

    def test_gap_and_unknown_prefix_do_not_assert_goal_survival(self):
        model=NeuralSemiMarkov(5,3,4).double();context=torch.randn(3,5,dtype=torch.float64)
        a=torch.randn(3,3,4,dtype=torch.float64).flatten(1).log_softmax(1).reshape(3,3,4)
        b=a.flip((1,2));gap=torch.tensor([1,7,1]);unknown=torch.tensor([False,False,True])
        pa=model.predict(context,a,gap,unknown);pb=model.predict(context,b,gap,unknown)
        torch.testing.assert_close(pa['logp'][1:],pb['logp'][1:],rtol=0,atol=0)
        torch.testing.assert_close(pa['logp'][1:],model.initial_logp(context)[1:],rtol=0,atol=0)
        self.assertFalse(torch.equal(pa['logp'][0],pb['logp'][0]))
        with self.assertRaises(TypeError):model.predict(context,a,gap,unknown,current_action=torch.tensor([1,2,3]))

    def test_sequence_likelihood_trains_duration_transitions_and_execution(self):
        model=NeuralSemiMarkov(5,3,4).double();executor=StateExecutionCondition(5,3,6).double()
        head=torch.nn.Linear(5,7).double();context=torch.randn(2,5,dtype=torch.float64)
        previous=model.initial_logp(context)
        total=0
        for step in range(3):
            prior=model.predict(context,previous,torch.ones(2,dtype=torch.int64),torch.tensor([step==0,False]))
            commands=head(executor(context)).log_softmax(-1)
            recorded=commands[torch.arange(2),:,torch.tensor([step,step+1])]
            loss,previous=model.observe(prior,recorded);total=total+loss.sum()
        parameters=dict(model.named_parameters())|{'executor.'+k:v for k,v in executor.named_parameters()}|{'head.'+k:v for k,v in head.named_parameters()}
        gradients=torch.autograd.grad(total,list(parameters.values()))
        for name,g in zip(parameters,gradients):
            self.assertTrue(bool(torch.isfinite(g).all()),name);self.assertGreater(float(g.norm()),1e-10,name)
        self.assertGreater(float((commands[:,0].exp()-commands[:,1].exp()).abs().max().detach()),1e-5)


if __name__=='__main__':unittest.main()
