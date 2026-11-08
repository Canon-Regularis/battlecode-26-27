import copy
import unittest
from unittest.mock import patch
import numpy as np
import torch
from .data import select
from .engine import update_window
from .assessment import comparison
from ..history_horizon.test_contract import fixture
from ..history_horizon.model import Policy
from ..history_horizon.engine import train_window


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def setUp(self):torch.manual_seed(91)

    def test_selection_order_and_targets_cannot_change_selection(self):
        candidates=[dict(group=g,identity=g+str(i),source_ids=list(range(i*32,(i+1)*32)),target=i)
                    for g in ('a','b','c','d') for i in range(9)]
        original=select(candidates,13);changed=copy.deepcopy(candidates[::-1])
        for c in changed:c['target']=-1000;c['loss']=999
        self.assertEqual([c['identity'] for c in original],[c['identity'] for c in select(changed,13)])
        counts=[sum(c['group']==g for c in original) for g in ('a','b','c','d')]
        self.assertEqual(sorted(counts),[3,3,3,4])
        with self.assertRaisesRegex(ValueError,'no resampling'):select(candidates,37)

    def test_control_is_exact_original_accumulation(self):
        data=fixture(1024);rows=np.arange(1024).reshape(32,32);m=Policy();reference=copy.deepcopy(m)
        opt=torch.optim.AdamW(m.parameters(),lr=.0003,weight_decay=.01)
        refopt=torch.optim.AdamW(reference.parameters(),lr=.0003,weight_decay=.01)
        total,records=update_window(m,data,rows,opt,'U00')
        refopt.zero_grad(set_to_none=True)
        _,expected,n=train_window(reference,data,rows,reference.empty(32),'A')
        torch.nn.utils.clip_grad_norm_(reference.parameters(),5,error_if_nonfinite=True);refopt.step()
        self.assertEqual(n,1024);self.assertEqual(total,expected)
        self.assertEqual([r['rows'] for r in records],[1024])
        for a,b in zip(m.parameters(),reference.parameters()):self.assertTrue(torch.equal(a,b))

    def test_treatment_updates_before_next_forward_and_detaches(self):
        data=fixture(1024);rows=np.arange(1024).reshape(32,32);m=Policy();weights=[]
        hook=m.execution.current[0].register_forward_pre_hook(lambda layer,args:weights.append(layer.weight.detach().clone()))
        opt=torch.optim.AdamW(m.parameters(),lr=.0003,weight_decay=.01)
        _,records=update_window(m,data,rows,opt,'U01');hook.remove()
        self.assertEqual([r['rows'] for r in records],[256]*4)
        self.assertEqual(len(weights),32)
        for start in (0,8,16,24):
            for t in range(start+1,start+8):self.assertTrue(torch.equal(weights[start],weights[t]))
        for t in (8,16,24):self.assertFalse(torch.equal(weights[t-1],weights[t]))
        self.assertEqual(float(opt.state[m.execution.action.weight]['step']),4)
        self.assertTrue(all(np.isfinite(r['preclip_norm']) for r in records))

    def test_padded_batch_rejected_before_update(self):
        m=Policy();opt=torch.optim.AdamW(m.parameters());rows=np.full((32,32),-1)
        with self.assertRaisesRegex(ValueError,'Full32by32'):update_window(m,fixture(1),rows,opt,'U00')
        self.assertFalse(opt.state)

    def test_single_group_likelihood_gain_fails_leave_one_out(self):
        d=fixture(128);raw=d['arrays'];d['group']=np.arange(128)//32
        control=dict(prediction=raw['y'].copy(),coordinate=np.zeros(128,np.int64),
            proposed_coordinate=np.zeros(128,np.int64),priority=raw['priority'].copy(),
            nll=np.ones(128)*3,move_coordinate_nll=np.ones(128)*2)
        treatment=copy.deepcopy(control);treatment['coordinate'][:]=144;treatment['proposed_coordinate'][:]=144
        treatment['nll']-=.2
        change=raw['direction']==3;treatment['move_coordinate_nll'][change&(d['group']==0)]-=.8
        result=comparison(d,treatment,control)
        self.assertTrue(result['allocation_checks']['complete_change_gain'])
        self.assertTrue(result['allocation_checks']['change_coordinate_nll'])
        self.assertFalse(result['allocation_checks']['change_nll_leave_one_group_out'])

    def test_prefit_failure_precedes_optimizer_creation(self):
        from .fit import run
        with patch('tools.action_predictor.cadence_probe.fit.preflight',side_effect=ValueError('review missing')),patch('torch.optim.AdamW') as opt:
            with self.assertRaisesRegex(ValueError,'review missing'):run('U00')
            opt.assert_not_called()


if __name__=='__main__':unittest.main()
