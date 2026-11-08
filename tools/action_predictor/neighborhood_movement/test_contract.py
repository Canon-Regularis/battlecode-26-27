import copy
import unittest
from unittest.mock import patch
import numpy as np
import torch
from .model import Policy,terrain_patch
from .engine import update_window
from ..history_horizon.model import Policy as BasePolicy
from ..history_horizon.test_contract import fixture
from ..history_horizon.data import input_batch,geometry,targets
from ..segment_policy.model import SPATIAL


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def setUp(self):torch.manual_seed(27)

    def pair(self):
        base=BasePolicy();models=[]
        for neighborhood in (False,True):
            torch.manual_seed(27);models.append(Policy(base.state_dict(),neighborhood))
        return base,*models

    def test_matched_parameters_zero_residual_and_full_mixed_family_parity(self):
        base,control,treatment=self.pair();data=fixture(30);raw=data['arrays'];raw['y']=np.arange(30)%15
        raw['py']=np.where(np.isin(raw['y'],SPATIAL),144,-1);ids=np.arange(30)
        for a,b in zip(control.state_dict().values(),treatment.state_dict().values()):self.assertTrue(torch.equal(a,b))
        self.assertEqual(sum(p.numel() for p in control.trainable_parameters()),5697)
        self.assertEqual(sum(p.numel() for p in control.parameters()),144989)
        step=base.begin(**input_batch(data,ids),state=base.empty(30),reset8=True);geo=geometry(data,ids);target=targets(data,ids)
        expected,post=base.observed(step,**geo,**target)
        for model in (control,treatment):
            actual,after=model.observed(step,**geo,**target)
            torch.testing.assert_close(actual,expected,rtol=0,atol=0)
            torch.testing.assert_close(after['hidden'],post['hidden'],rtol=0,atol=0)
            for family in SPATIAL:
                f=torch.full((30,),family)
                torch.testing.assert_close(model.spatial(step,**geo,family=f),base.spatial(step,**geo,family=f),rtol=0,atol=0)

    def test_patch_orientation_crop_mask_and_center_control(self):
        grid=torch.zeros(1,289,20);grid[:,:,3]=1;grid[0,143,4]=1
        treatment=terrain_patch(grid,True);control=terrain_patch(grid,False)
        self.assertEqual(float(treatment[0,144,12]),1.)
        self.assertEqual(float(control[0,144,9:18].sum()),0.)
        torch.testing.assert_close(treatment[:,:,18:],control[:,:,18:],rtol=0,atol=0)
        self.assertEqual(treatment[0,0,18:].tolist(),[0,0,0,0,1,1,0,1,1])
        grid[0,143,3]=0
        self.assertEqual(float(terrain_patch(grid,True)[0,144,12]),0.)

    def test_nonzero_residual_other_families_exact_and_normalized_fallback(self):
        base,_,model=self.pair();data=fixture(15);ids=np.arange(15);geo=geometry(data,ids)
        step=base.begin(**input_batch(data,ids),state=base.empty(15),reset8=True)
        with torch.no_grad():model.residual_readout.weight.fill_(.1);model.residual_readout.bias.fill_(.2)
        for empty in (False,True):
            if empty:geo['valid'][:]=False
            family=torch.arange(15);actual=model.spatial(step,**geo,family=family);expected=base.spatial(step,**geo,family=family)
            torch.testing.assert_close(actual[family!=8],expected[family!=8],rtol=0,atol=0)
            torch.testing.assert_close(actual.exp().sum(-1),torch.ones(15,dtype=torch.float64),rtol=0,atol=1e-8)
            if not empty:self.assertFalse(torch.equal(actual[8],expected[8]))

    def test_only_treatment_reads_neighbor_terrain(self):
        _,control,treatment=self.pair();context=torch.randn(1,128);grid=torch.zeros(1,289,20);grid[:,:,3]=1
        changed=grid.clone();changed[:,143,4]=1
        for model in (control,treatment):
            with torch.no_grad():model.residual_readout.weight.fill_(.1)
        with torch.no_grad():
            self.assertEqual(float(control.residual(context,grid)[0,144]),float(control.residual(context,changed)[0,144]))
            self.assertNotEqual(float(treatment.residual(context,grid)[0,144]),float(treatment.residual(context,changed)[0,144]))

    def test_updates_only_residual_and_never_inside_window(self):
        base,_,model=self.pair();data=fixture(64);rows=np.arange(64).reshape(32,2);observed=[]
        hook=model.residual_readout.register_forward_pre_hook(lambda layer,args:observed.append(layer.weight.detach().clone()))
        opt=torch.optim.AdamW(model.trainable_parameters(),lr=.0003,weight_decay=.01)
        for _ in range(2):
            observed.clear();_,records=update_window(model,data,rows,opt,'N01')
            self.assertEqual(len(observed),32)
            for v in observed:self.assertTrue(torch.equal(v,observed[0]))
            self.assertTrue(records[0]['active']);self.assertEqual(records[0]['rows'],64)
        hook.remove()
        for k,v in model.base_state().items():self.assertTrue(torch.equal(v,base.state_dict()[k]))
        for p in model.trainable_parameters():
            self.assertIsNotNone(p.grad);self.assertTrue(torch.isfinite(p.grad).all())
            self.assertGreater(float(p.grad.abs().sum()),0)
        self.assertEqual(len(opt.state),6)

    def test_no_movement_no_parameter_update(self):
        _,model,_=self.pair();data=fixture(32);data['arrays']['y'][:]=7;data['arrays']['py'][:]=-1
        before=copy.deepcopy(model.state_dict());opt=torch.optim.AdamW(model.trainable_parameters(),lr=.0003,weight_decay=.01)
        _,records=update_window(model,data,np.arange(32)[:,None],opt,'N00')
        self.assertFalse(records[0]['active']);self.assertFalse(opt.state)
        for k,v in model.state_dict().items():self.assertTrue(torch.equal(v,before[k]))

    def test_missing_review_precedes_optimizer(self):
        from .fit import run
        with patch('tools.action_predictor.neighborhood_movement.fit.preflight',side_effect=ValueError('review required')),patch('torch.optim.AdamW') as opt:
            with self.assertRaisesRegex(ValueError,'review required'):run('N00')
            opt.assert_not_called()


if __name__=='__main__':unittest.main()
