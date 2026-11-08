import copy
import unittest
from unittest.mock import patch
import numpy as np
import torch
from .model import Policy
from .data import INPUTS,normalize,input_batch,geometry,targets,chunks
from .engine import train_window,infer,selectors,take,put,detach
from .assessment import windows,summarize,paired
from ..segment_policy.model import SPATIAL
from ..reliable_model import priority_log_mass


def fixture(n=40):
    rng=np.random.default_rng(13)
    raw=dict(x=rng.normal(size=(n,253)).astype(np.float32),
        history=np.zeros((n,16,24),np.float32),observations=rng.normal(size=(n,16,253)).astype(np.float32),
        history_gaps=np.zeros((n,16,5),np.float32),priority_inputs=np.zeros((n,7),np.int64),
        root_gap=np.ones(n,np.int64),actor_start=np.zeros(n,bool),
        grid=rng.normal(size=(n,289,20)).astype(np.float16),valid=np.ones((n,289),bool),
        rules=np.tile([8,8,8,31,31],(n,1)).astype(np.float32),
        y=np.full(n,8,np.int64),py=np.full(n,144,np.int64),priority=np.zeros(n,np.int64),
        direction=np.tile([2,3],(n+1)//2)[:n],round=np.arange(n)//4)
    raw['actor_start'][0]=True;raw['grid'][:,:,5]=1
    raw['history_gaps'][:,:,0:2]=1
    return dict(arrays=raw,sequences=[np.arange(n)],group=np.arange(n)//max(1,n//2))


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def setUp(self):torch.manual_seed(23)

    def test_shared_initialization_and_forward_detachment_invariance(self):
        data=fixture();models=[]
        for _ in range(3):torch.manual_seed(23);models.append(Policy())
        for a,b in zip(models,models[1:]):
            for x,y in zip(a.parameters(),b.parameters()):self.assertTrue(torch.equal(x,y))
        b=infer(models[1],data,'B',True);c=infer(models[2],data,'C',True)
        for key in b:np.testing.assert_array_equal(b[key],c[key])
        a=infer(models[0],data,'A',True)
        np.testing.assert_array_equal(a['nll'][:8],b['nll'][:8])
        self.assertGreater(np.max(np.abs(a['nll'][8:]-b['nll'][8:])),1e-7)

    def test_full_likelihood_decoder_and_spatial_normalization(self):
        data=fixture(15);raw=data['arrays'];raw['y']=np.arange(15)
        raw['py']=np.where(np.isin(raw['y'],SPATIAL),144,-1)
        model=Policy();ids=np.arange(15);geo=geometry(data,ids)
        step=model.begin(**input_batch(data,ids),state=model.empty(15),reset8=False)
        p=model.decode(step,**geo)
        gold_loss,_=model.observed(step,**geo,**targets(data,ids))
        for i,y in enumerate(raw['y']):
            expected=p['type_logp'][i,y]
            if y in SPATIAL:expected=expected+p['parameter_logp'][int(y)][i,144]
            if y==9:expected=expected+priority_log_mass(model.execution.priority(step['context'][i:i+1]).double(),torch.zeros(1))[0]
            self.assertAlmostEqual(float(gold_loss[i].detach()),-float(expected.detach()),places=9)
        loss,_=model.observed(step,**geo,y=p['prediction'],py=p['proposed_coordinate'],priority=p['priority'])
        torch.testing.assert_close(loss,-p['family_mode_logp'].max(-1).values,atol=1e-8,rtol=0)
        for lp in p['parameter_logp'].values():torch.testing.assert_close(lp.exp().sum(-1),torch.ones(15,dtype=torch.float64))
        raw['valid'][:]=False;geo=geometry(data,ids)
        empty=model.spatial(step,**geo,family=torch.arange(15))
        self.assertTrue(torch.isfinite(empty).all())
        torch.testing.assert_close(empty.exp().sum(-1),torch.ones(15,dtype=torch.float64))

    def test_prediction_precedes_current_command_and_excludes_metadata(self):
        model=Policy();data=fixture(1);ids=np.array([0]);first=input_batch(data,ids)
        step=model.begin(**first,state=model.empty(1),reset8=False)
        before=model.decode(step,**geometry(data,ids))['family_mode_logp'].clone()
        _,post1=model.observed(step,**geometry(data,ids),**targets(data,ids))
        data['arrays'].update(y=np.array([9]),py=np.array([-1]),priority=np.array([987654]),
            direction=np.array([999]),actor=np.array([99]),ordinal=np.array([123]),event=np.array([456]))
        self.assertEqual(set(input_batch(data,ids)),set(INPUTS))
        for key in first:torch.testing.assert_close(first[key],input_batch(data,ids)[key])
        _,post2=model.observed(step,**geometry(data,ids),**targets(data,ids))
        torch.testing.assert_close(before,model.decode(step,**geometry(data,ids))['family_mode_logp'])
        self.assertFalse(torch.equal(post1['hidden'],post2['hidden']))

    def test_genuine_gap_actor_and_periodic_resets(self):
        model=Policy();data=fixture(4);raw=data['arrays'];raw['actor_start'][:]=[False,True,False,False]
        raw['root_gap'][:]=[1,1,2,1]
        state=dict(hidden=torch.randn(4,28),age=torch.tensor([7,3,4,8]))
        for arm,expected in [(False,[False,True,True,False]),(True,[False,True,True,True])]:
            step=model.begin(**input_batch(data,np.arange(4)),state=state,reset8=arm)
            self.assertEqual(step['reset'].tolist(),expected)
            self.assertTrue((step['hidden'][step['reset']]==0).all())
            torch.testing.assert_close(step['hidden'][~step['reset']],state['hidden'][~step['reset']])

    def test_normalization_remasks_and_sanitizes_without_erasing_commands(self):
        raw=fixture(2)['arrays'];raw['observations'][:]=0;raw['history_gaps'][:,:,1]=0
        raw['history'][:,:,9]=1;raw['history'][:,:,16:18]=7
        raw['history'][1,:,9]=0;raw['history'][1,:,8]=1
        result=normalize(raw,np.ones(253,np.float32)*5,np.ones(253,np.float32)*2)
        self.assertTrue((result['observations']==0).all())
        self.assertTrue((result['history'][0,:,16:18]==0).all())
        self.assertTrue((result['history'][1,:,16:18]==7).all())
        self.assertTrue((result['history'][0,:,9]==1).all())
        model=Policy();data=dict(arrays=result);ids=np.arange(2)
        torch.nn.init.normal_(model.history_projection.weight,std=.1)
        with torch.no_grad():
            step=model.begin(**input_batch(data,ids),state=model.empty(2),reset8=False)
            # Even a nonzero encoder bias cannot encode missing observations.
            model.observation[0].bias.add_(100)
            changed=model.begin(**input_batch(data,ids),state=model.empty(2),reset8=False)
        torch.testing.assert_close(step['context'],changed['context'])

    def test_gradient_horizons_and_forward_memory(self):
        class Probe(Policy):
            def __init__(self):super().__init__();self.posts=[]
            def observed(self,*args,**kwargs):
                loss,post=super().observed(*args,**kwargs)
                post['hidden'].retain_grad();self.posts.append(post['hidden'])
                return loss,post
        data=fixture(16);rows=np.arange(16).reshape(16,1)
        for arm in ('A','B','C'):
            torch.manual_seed(23);model=Probe();train_window(model,data,rows,model.empty(1),arm)
            self.assertIsNotNone(model.posts[0].grad)
            if arm=='C':self.assertGreater(float(model.posts[7].grad.norm()),0)
            else:self.assertIsNone(model.posts[7].grad)
            self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()))

    def test_accumulation_uses_one_shared_denominator(self):
        data=fixture(13);rows=np.full((10,2),-1,np.int64);rows[:,0]=np.arange(10);rows[:3,1]=np.arange(10,13)
        data['arrays']['actor_start'][10]=True
        model=Policy();reference=copy.deepcopy(model)
        _,total,n=train_window(model,data,rows,model.empty(2),'B');self.assertEqual(n,13)
        state=reference.empty(2);losses=[]
        for t,row in enumerate(rows):
            active=torch.from_numpy(np.flatnonzero(row>=0));ids=row[row>=0]
            step=reference.begin(**input_batch(data,ids),state=take(state,active),reset8=False)
            loss,post=reference.observed(step,**geometry(data,ids),**targets(data,ids))
            losses.append(loss.sum());state=put(state,active,post)
            if (t+1)%8==0:state=detach(state)
        expected=torch.stack(losses).sum()/13;expected.backward()
        self.assertAlmostEqual(total/13,float(expected.detach()),places=10)
        for a,b in zip(model.parameters(),reference.parameters()):
            if a.grad is None:self.assertIsNone(b.grad)
            else:torch.testing.assert_close(a.grad,b.grad,atol=1e-6,rtol=1e-5)

    def test_sampling_windows_and_selection_denominators(self):
        data=fixture(40);data['arrays']['root_gap'][17]=3
        expected=np.r_[np.arange(16),np.arange(17,33)].reshape(2,16)
        np.testing.assert_array_equal(windows(data,16),expected)
        self.assertEqual(windows(data,32).shape,(0,32))
        sequences=[np.arange(5),np.arange(5,47),np.arange(47,50)]
        schedules=[list(chunks(sequences,np.random.default_rng(7),batch_size=2,unroll=32)) for _ in range(3)]
        for schedule in schedules:
            flattened=np.concatenate([r[r>=0] for r in schedule]);np.testing.assert_array_equal(np.sort(flattened),np.arange(50))
            for a,b in zip(schedule,schedules[0]):np.testing.assert_array_equal(a,b)
        p=dict(nll=np.arange(40,dtype=float));value=selectors(data,p)
        self.assertEqual(value,dict(movement=19.5,full=19.5))

    def test_strict_metrics_and_paired_regressions(self):
        data=fixture(40);raw=data['arrays'];raw['y'][:4]=[11,8,9,2];raw['py'][:4]=[-1,290,-1,144]
        p=dict(prediction=raw['y'].copy(),coordinate=raw['py'].copy(),proposed_coordinate=raw['py'].copy(),
            priority=raw['priority'].copy(),nll=np.ones(40))
        value=summarize(data,p);self.assertEqual(value['categories']['all']['complete'],38)
        self.assertEqual(value['strict_unassessed_shops'],1)
        q=copy.deepcopy(p);q['coordinate'][3]=100
        report=paired(data,q,p);self.assertEqual(report['metrics']['attack_conditional']['delta'],-1)
        self.assertFalse(report['allocation_checks']['attack'])
        self.assertEqual(report['metrics']['all_regressions'],1)

    def test_fit_rejects_before_optimizer_when_review_fails(self):
        from .fit import run
        with patch('tools.action_predictor.history_horizon.fit.preflight',side_effect=ValueError('unreviewed')), \
             patch('torch.optim.AdamW') as optimizer:
            with self.assertRaisesRegex(ValueError,'unreviewed'):run('A')
            optimizer.assert_not_called()


if __name__=='__main__':unittest.main()
