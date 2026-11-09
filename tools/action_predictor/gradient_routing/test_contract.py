import copy
import unittest
from unittest.mock import patch
import numpy as np
import torch
from .engine import observed_parts,gradients,combine,update_window,trim_rows
from .assessment import comparison
from ..history_horizon.test_contract import fixture
from ..history_horizon.model import Policy
from ..history_horizon.engine import train_window
from ..history_horizon.data import input_batch,geometry,targets
from ..segment_policy.model import SPATIAL


def mixed(n):
    data=fixture(n);raw=data['arrays'];raw['y']=np.arange(n)%15
    raw['py']=np.where(np.isin(raw['y'],SPATIAL),144,-1)
    raw['priority']=np.arange(n)*13-500
    return data


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def setUp(self):torch.manual_seed(27)

    def test_partition_matches_original_likelihood_and_assimilation(self):
        data=mixed(45);model=Policy();ids=np.arange(45)
        step=model.begin(**input_batch(data,ids),state=model.empty(45),reset8=True)
        target=targets(data,ids);geo=geometry(data,ids)
        expected,post=model.observed(step,**geo,**target)
        actual,parts,newpost=observed_parts(model,step,geo,target,torch.from_numpy(data['arrays']['direction']))
        torch.testing.assert_close(actual,expected,rtol=0,atol=0)
        torch.testing.assert_close(sum(v for v in parts if v is not None),actual.sum(),rtol=1e-14,atol=1e-12)
        for k in post:torch.testing.assert_close(post[k],newpost[k],rtol=0,atol=0)

    def test_simultaneous_projection_uses_original_vectors_and_rest(self):
        d=torch.tensor([1.,0.]);c=torch.tensor([-1.,1.]);r=torch.tensor([.1,.2])
        value,record=combine([d,c,r],True)
        torch.testing.assert_close(value,torch.tensor([.6,1.7]),atol=1e-7,rtol=0)
        self.assertTrue(record['conflict']);self.assertTrue(record['projected'])
        torch.testing.assert_close(d,torch.tensor([1.,0.]));torch.testing.assert_close(c,torch.tensor([-1.,1.]))
        ordinary,_=combine([d,c,r],False);torch.testing.assert_close(ordinary,d+c+r,rtol=0,atol=0)

    def test_no_conflict_zero_and_opposing_gradients(self):
        d=torch.tensor([1.,2.]);r=torch.tensor([.1,-.4])
        for c in (d.clone(),torch.zeros(2)):
            routed,record=combine([d,c,r],True)
            torch.testing.assert_close(routed,d+c+r,rtol=0,atol=0);self.assertFalse(record['projected'])
        routed,_=combine([d,-d,r],True);torch.testing.assert_close(routed,r)

    def test_control_gradient_and_optimizer_match_ordinary_backprop(self):
        data=mixed(64);rows=np.arange(64).reshape(32,2)
        model=Policy();reference=copy.deepcopy(model)
        opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
        refopt=torch.optim.AdamW(reference.parameters(),lr=.0003,weight_decay=.01)
        total,records=update_window(model,data,rows,opt,'R00')
        _,expected,n=train_window(reference,data,rows,reference.empty(2),'A')
        self.assertAlmostEqual(total,expected,places=9);self.assertEqual(n,64)
        self.assertEqual([r['rows'] for r in records],[64])
        for p,q in zip(model.parameters(),reference.parameters()):
            self.assertEqual(p.grad is None,q.grad is None)
            if p.grad is not None:torch.testing.assert_close(p.grad,q.grad,rtol=1e-4,atol=2e-7)
        torch.nn.utils.clip_grad_norm_(reference.parameters(),5,error_if_nonfinite=True);refopt.step()
        for p,q in zip(model.parameters(),reference.parameters()):
            torch.testing.assert_close(p,q,rtol=0,atol=2e-6)

    def test_empty_strata_and_wholly_unused_parameters(self):
        data=fixture(32);data['arrays']['y'][:]=7;data['arrays']['py'][:]=-1
        model=Policy();vectors,used,_,_=gradients(model,data,np.arange(32)[:,None])
        self.assertEqual(int(torch.count_nonzero(vectors[0])),0);self.assertEqual(int(torch.count_nonzero(vectors[1])),0)
        names=[name for name,_ in model.named_parameters()]
        self.assertFalse(used[names.index('execution.priority.weight')])
        self.assertFalse(used[names.index('execution.query.weight')])

    def test_no_update_inside_window_and_one_final_update(self):
        data=fixture(64);rows=np.arange(64).reshape(32,2);model=Policy();weights=[]
        hook=model.execution.current[0].register_forward_pre_hook(lambda layer,args:weights.append(layer.weight.detach().clone()))
        opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
        _,records=update_window(model,data,rows,opt,'R01');hook.remove()
        self.assertEqual(len(weights),32)
        for value in weights:self.assertTrue(torch.equal(value,weights[0]))
        self.assertFalse(torch.equal(weights[0],model.execution.current[0].weight))
        self.assertEqual(float(opt.state[model.execution.action.weight]['step']),1)
        self.assertEqual(len(records),1)

    def test_partial_final_batch_and_invalid_padding(self):
        rows=np.full((32,32),-1);rows[:,:29]=np.arange(928).reshape(32,29)
        self.assertEqual(trim_rows(rows).size,928)
        rows[1,0]=-1
        with self.assertRaisesRegex(ValueError,'Partial'):trim_rows(rows)
        with self.assertRaisesRegex(ValueError,'empty'):trim_rows(np.full((32,32),-1))

    def test_guard_uses_complete_targeting_and_fails_absent_category(self):
        data=mixed(128);raw=data['arrays'];data['group']=np.arange(128)//32
        base=dict(prediction=raw['y'].copy(),coordinate=raw['py'].copy(),proposed_coordinate=raw['py'].copy(),
            priority=raw['priority'].copy(),nll=np.full(128,3.),move_coordinate_nll=np.full(128,2.),
            move_within_group_nll=np.full(128,1.))
        treatment=copy.deepcopy(base);treatment['prediction'][raw['y']==6]=12
        result=comparison(data,treatment,base)
        self.assertTrue(result['allocation_checks']['cast_1_conditional'])
        self.assertFalse(result['allocation_checks']['cast_1_complete'])
        raw['y'][raw['y']==6]=12
        result=comparison(data,treatment,base)
        self.assertFalse(result['allocation_checks']['cast_1_conditional'])

    def test_prefit_failure_precedes_optimizer_creation(self):
        from .fit import run
        with patch('tools.action_predictor.gradient_routing.fit.preflight',side_effect=ValueError('review missing')),patch('torch.optim.AdamW') as opt:
            with self.assertRaisesRegex(ValueError,'review missing'):run('R00')
            opt.assert_not_called()

    def test_final_comparison_budget_boundary_prevents_publication(self):
        from .fit import checked_elapsed,publish_result
        # An earlier evaluation check passes; final comparison/hash work then
        # reaches or exceeds the cap, including time spent in the first arm.
        for final_time in (7200.,7200.25):
            with patch('tools.action_predictor.gradient_routing.fit.time.perf_counter',side_effect=[7199.,final_time]),patch('tools.action_predictor.gradient_routing.fit.immutable_json') as write:
                self.assertEqual(checked_elapsed(100.,100.),7099.)
                with self.assertRaisesRegex(RuntimeError,'budget exhausted'):
                    publish_result('unused.json',{},100.,100.)
                write.assert_not_called()
        with patch('tools.action_predictor.gradient_routing.fit.time.perf_counter',return_value=7199.5) as clock,patch('tools.action_predictor.gradient_routing.fit.immutable_json') as write:
            publish_result('unused.json',dict(arm='R01'),100.,100.)
            clock.assert_called_once()
            write.assert_called_once_with('unused.json',dict(arm='R01',seconds=7099.5))


if __name__=='__main__':unittest.main()
