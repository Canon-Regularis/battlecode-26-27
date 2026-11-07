"""Sequence/filter/decoder contract checks, not evidence of learned quality."""
import unittest
import torch
import numpy as np
from .model import GoalPolicy
from .data import chunks
from .actor import PolicyActor
from .execution import Command,Execution
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt

class TestPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):rt.setup(20261114);cls.teacher,_=load_base()
    def inputs(self,n=2):
        g=torch.zeros(n,18);g[:,0]=np.log(2)/8;g[:,2]=1
        return dict(x=torch.zeros(n,253),history=torch.zeros(n,32,24),observations=torch.zeros(n,16,253),history_gaps=torch.zeros(n,16,5),transition_gap=g,position=torch.zeros(n,2),position_known=torch.ones(n,dtype=torch.bool),entities=torch.zeros(n,1,119),entity_mask=torch.ones(n,1,dtype=torch.bool),public_tokens=torch.zeros(n,1,8),public_mask=torch.ones(n,1,dtype=torch.bool))
    def test_initial_state_does_not_inherit_another_actor(self):
        m=GoalPolicy(self.teacher,True).eval();a=m.empty(2);b=m.empty(2);b['belief'][:,0]=.9;b['world']+=10;b['known'][:]=True
        x=m.begin(**self.inputs(),state=a);y=m.begin(**self.inputs(),state=b)
        torch.testing.assert_close(x['logprior'],y['logprior']);torch.testing.assert_close(x['world'],y['world'])
    def test_full_distribution_matches_observed_loss(self):
        m=GoalPolicy(self.teacher,True).eval();s=m.begin(**self.inputs(),state=m.empty(2));grid=torch.zeros(2,289,20);grid[:,:,5]=1;valid=torch.ones(2,289,dtype=torch.bool);rules=torch.tensor([[2,2,2,16,16.]]).repeat(2,1);loss,state=m.observed(s,grid,valid,rules,torch.tensor([8,9]),torch.tensor([144,-1]),torch.tensor([0,.2]));p=m.decode(s,grid,valid,rules,torch.zeros(2,dtype=torch.long),torch.full((2,),-.2));expected=torch.stack((-p['type_logp'][0,8]-p['parameter_logp'][8][0,144],-p['type_logp'][1,9]+.2));torch.testing.assert_close(loss,expected);torch.testing.assert_close(p['type_logp'].exp().sum(1),torch.ones(2));torch.testing.assert_close(state['belief'].sum(1),torch.ones(2))
    def test_chunks_preserve_order_without_cross_actor_stitch(self):
        streams=[np.array([4,1,8]),np.array([0,2]),np.array([7,5,6,3])];seen=[]
        for rows in chunks(streams,batch_size=2,unroll=2):seen.extend(rows[rows>=0].tolist())
        self.assertEqual(sorted(seen),list(range(9)))
        for stream in streams:self.assertEqual([i for i in seen if i in stream],stream.tolist())
    def test_actual_outcome_updates_only_after_execute(self):
        calls=[]
        class Model:
            def eval(self):return self
            def empty(self,n):return {'belief':torch.tensor([[1.]])}
            def observed(self,step,**kwargs):calls.append(int(kwargs['y'][0]));return torch.zeros(1),{'belief':torch.tensor([[2.]])}
        a=PolicyActor(Model(),'game/actor');c=Command('move',(1,2));a.pending=dict(command=c,step={},geometry={},coordinate=146,priority_log_mass=None);self.assertEqual(calls,[]);a.commit(Execution(c,'blocked',False));self.assertEqual(calls,[3]);self.assertEqual(a.state['belief'].item(),2)
    def test_rejected_proposal_is_not_a_demonstration(self):
        class Model:
            def eval(self):return self
            def empty(self,n):return {'belief':torch.tensor([[1.]])}
        a=PolicyActor(Model(),'game/actor');a.pending={'command':Command('shop')};a.reject();self.assertEqual(a.state['belief'].item(),1);self.assertIsNone(a.pending)

if __name__=='__main__':unittest.main()
