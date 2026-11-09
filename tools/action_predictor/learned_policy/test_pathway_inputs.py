"""Projection intervention algebra and missing-position contracts, no optimizer."""
import unittest
import torch
from torch import nn
from .pathway_inputs import features,contrast,CONTRASTS


class TestContrasts(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(20261108)
        self.model=nn.Module();self.model.goal_condition=nn.Linear(5,128)
        self.inputs=dict(position=torch.tensor([[.2,.4],[0.,0.]]),position_known=torch.tensor([True,False]))
        self.step=dict(world=torch.randn(2,4,2),known=torch.ones(2,4,dtype=torch.bool),
            logscale=torch.randn(2,4,2),logprior=torch.randn(2,4).log_softmax(-1))
        self.f=features(self.step,self.inputs);self.latent=torch.randn(2,4,128)
        self.step['context']=self.latent+self.model.goal_condition(self.f)
        self.ref=dict(geometry_known=self.f[0,:,:2].numpy(),
            uncertainty_by_position_known=torch.stack((self.f[1,:,2:4],self.f[0,:,2:4])).numpy(),
            availability=self.f[:,:,4].mean(0).numpy())

    def test_matches_independent_replaced_feature_forward(self):
        for name in CONTRASTS:
            f=self.f.clone();bias=self.model.goal_condition.bias
            if name in ('geometry_mean','all_means'):
                f[0,:,:2]=torch.tensor(self.ref['geometry_known']);f[1,:,:2]=0
            if name in ('uncertainty_mean','all_means'):
                f[:,:,2:4]=torch.tensor(self.ref['uncertainty_by_position_known'])[[1,0]]
            if name in ('availability_mean','all_means'):f[:,:,4]=torch.tensor(self.ref['availability'])[None]
            expected=self.latent+self.model.goal_condition(f)
            if name=='bias_off':expected=expected-bias
            if name=='projection_off':expected=self.latent
            result=contrast(self.model,self.step,self.inputs,self.ref,name)
            torch.testing.assert_close(result['context'],expected,rtol=1e-6,atol=1e-6)
            for key in ('world','known','logprior','logscale'):self.assertIs(result[key],self.step[key])

    def test_unknown_position_geometry_and_actual_flags_preserved(self):
        original=self.step['context'].clone()
        ref=dict(self.ref,geometry_known=torch.full((4,2),123.).numpy())
        result=contrast(self.model,self.step,self.inputs,ref,'geometry_mean')
        torch.testing.assert_close(result['context'][1],original[1],rtol=0,atol=0)
        torch.testing.assert_close(self.step['context'],original,rtol=0,atol=0)
        self.assertEqual(self.inputs['position_known'].tolist(),[True,False])

    def test_mean_preservation_and_identity(self):
        result=contrast(self.model,self.step,self.inputs,self.ref,'all_means')
        torch.testing.assert_close(result['context'].mean(0),self.step['context'].mean(0),rtol=1e-6,atol=1e-6)
        identity=contrast(self.model,self.step,self.inputs,self.ref,'identity')
        self.assertIs(identity['context'],self.step['context'])
        for key in self.step:self.assertIs(identity[key],self.step[key])


if __name__=='__main__':unittest.main()
