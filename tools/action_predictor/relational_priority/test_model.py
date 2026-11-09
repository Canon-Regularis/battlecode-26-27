"""Probability, exact-integer, masking and trainable-boundary contracts."""
import copy
import math
import unittest
import numpy as np
import torch
from torch import nn

from ..priority_residual_modes import AnchoredPriorityModes
from ..order_information.relation_discrimination_v3 import relation_features as numpy_features
from .model import SignedPointCorrection,other_features,own_features,NAMES,RELATIONS


def fixture():
    original=nn.Linear(128,2)
    with torch.no_grad():original.weight.zero_();original.bias.copy_(torch.tensor([0.,-2.]))
    base=AnchoredPriorityModes(original,[-1,0,1,2],[1,2,3,2],[0,1],[2,1])
    values=torch.tensor([[0,1,0,1,0,1,0]],dtype=torch.int64)
    history=torch.zeros((1,16,2),dtype=torch.int64);history[0,-1]=torch.tensor([0,1])
    priorities=torch.tensor([[[0,1],[2,2]]],dtype=torch.int64)
    available=torch.ones((1,2,2),dtype=torch.bool);roles=torch.tensor([[0,1]],dtype=torch.int8)
    return base,dict(context=torch.zeros((1,128)),extra=torch.zeros((1,39)),values=values,history=history,
                     priorities=priorities,available=available,roles=roles)


class CorrectionTests(unittest.TestCase):
    def test_zero_initialization_preserves_raw_probabilities_rng_and_base(self):
        base,args=fixture();before=copy.deepcopy(base.state_dict());rng=torch.get_rng_state().clone()
        model=SignedPointCorrection(base)
        torch.testing.assert_close(torch.get_rng_state(),rng,rtol=0,atol=0)
        old=base(args['context'],args['extra']);new=model(**args)
        torch.testing.assert_close(new,old,rtol=0,atol=0)
        torch.testing.assert_close(model.integer(new,args['values']),base.integer(old,args['values']),rtol=0,atol=0)
        for key,value in before.items():torch.testing.assert_close(base.state_dict()[key],value,rtol=0,atol=0)
        self.assertEqual([(name,p.numel()) for name,p in model.named_parameters() if p.requires_grad],[('weights',72)])

    def test_mixture_normalization_and_global_map_after_signed_corrections(self):
        base,args=fixture();model=SignedPointCorrection(base)
        with torch.no_grad():model.weights.copy_(torch.linspace(-.4,.5,72))
        raw=model(**args)
        old=base(args['context'],args['extra'])
        torch.testing.assert_close(raw[:,model.point_count:],old[:,model.point_count:],rtol=0,atol=0)
        integers=torch.arange(-512,513,dtype=torch.int64)
        expanded=raw.repeat(len(integers),1);values=args['values'].repeat(len(integers),1)
        probability=model.log_mass(expanded,integers,values).exp()
        self.assertAlmostEqual(float(probability.sum().detach()),1.,places=12)
        self.assertEqual(int(integers[probability.argmax()]),int(model.integer(raw,args['values'])[0]))
        # Independent direct-CDF arithmetic at a duplicate point.
        points,mix=model.components(raw,args['values']);value=0
        location=float(raw[0,-2].detach());scale=math.exp(max(-6,min(5,float(raw[0,-1].detach()))))
        sigmoid=lambda z:1/(1+math.exp(-z))
        mass=sigmoid((value/100+.005-location)/scale)-sigmoid((value/100-.005-location)/scale)
        expected=float(mix[0,:-1].exp()[points[0]==value].sum().detach())+float(mix[0,-1].exp().detach())*mass
        observed=float(model.log_mass(raw,torch.tensor([value]),args['values']).exp()[0].detach())
        self.assertAlmostEqual(observed,expected,places=13)

    def test_only_correction_receives_gradients_and_matches_finite_difference(self):
        base,args=fixture();model=SignedPointCorrection(base)
        target=torch.tensor([0],dtype=torch.int64)
        loss=-model.log_mass(model(**args),target,args['values']).sum();loss.backward()
        self.assertTrue(torch.count_nonzero(model.weights.grad)>0)
        self.assertTrue(all(p.grad is None for p in model.base.parameters()))
        column=int(model.weights.grad.abs().argmax());analytic=float(model.weights.grad[column]);epsilon=.001
        with torch.no_grad():
            model.weights[column]=epsilon
            positive=float(-model.log_mass(model(**args),target,args['values'])[0])
            model.weights[column]=-epsilon
            negative=float(-model.log_mass(model(**args),target,args['values'])[0])
            model.weights.zero_()
        self.assertAlmostEqual((positive-negative)/(2*epsilon),analytic,delta=2e-4)

    def test_torch_features_match_independent_numpy_integer_predicates(self):
        points=torch.tensor([[-1,0,1,2],[2080375424,2080375425,-2147483648,2147483647]],dtype=torch.int64)
        priorities=torch.tensor([[[0,1],[2,2]],[[2080375424,2080375425],[-2147483648,-2147483648]]],dtype=torch.int64)
        available=torch.ones((2,2,2),dtype=torch.bool);roles=torch.tensor([[0,1],[0,1]],dtype=torch.int8)
        actual=other_features(points,priorities,available,roles).numpy()
        for column in range(points.shape[1]):
            expected=numpy_features(points[:,column].numpy(),priorities[:,:,0].numpy(),
                priorities[:,:,1].numpy(),available.numpy(),roles.numpy())
            np.testing.assert_array_equal(actual[:,column],expected)
        self.assertNotEqual(actual[1,0,4],actual[1,1,4])
        torch.testing.assert_close(other_features(points,priorities.flip(1),available.flip(1),roles.flip(1)),
                                  torch.from_numpy(actual),rtol=0,atol=0)

    def test_unavailable_poison_empty_units_and_known_zero_history(self):
        base,args=fixture();model=SignedPointCorrection(base)
        points,_=base.components(base(args['context'],args['extra']),args['values'])
        unavailable=torch.zeros_like(args['available'])
        poison=torch.full_like(args['priorities'],2**63-1)
        self.assertFalse(other_features(points,poison,unavailable,args['roles']).any())
        self.assertFalse(other_features(points,poison[:,:0],unavailable[:,:0],args['roles'][:,:0]).any())
        own=own_features(torch.tensor([[0]],dtype=torch.int64),args['values'],args['history'])
        self.assertTrue(own[0,0,22])
        args['history'].zero_()
        self.assertFalse(own_features(torch.tensor([[0]],dtype=torch.int64),args['values'],args['history'])[0,0,22])

    def test_same_integer_explanations_share_features_and_invalid_residuals_masked(self):
        base,args=fixture();model=SignedPointCorrection(base)
        points,_=base.components(base(args['context'],args['extra']),args['values'])
        f=model.features(points,args['values'],args['history'],args['priorities'],args['available'],args['roles'])
        self.assertEqual(int((points[0]==0).sum()),2)
        torch.testing.assert_close(f[0,points[0]==0][0],f[0,points[0]==0][1],rtol=0,atol=0)
        args['values'][:,4:6]=0
        f=model.features(points,args['values'],args['history'],args['priorities'],args['available'],args['roles'])
        self.assertFalse(f[:,len(model.absolute):].any())

    def test_common_active_mask_has_identical_trainable_interface(self):
        base,args=fixture();active=torch.zeros(72,dtype=torch.bool);active[[0,7,25,50]]=True
        a=SignedPointCorrection(base,active);b=SignedPointCorrection(base,active)
        self.assertEqual(a.weights.numel(),4)
        torch.testing.assert_close(a(**args),b(**args),rtol=0,atol=0)
        self.assertEqual([name for name,p in a.named_parameters() if p.requires_grad],['weights'])
        with self.assertRaisesRegex(ValueError,'Empty/invalid'):SignedPointCorrection(base,torch.zeros(72,dtype=torch.bool))


if __name__=='__main__':unittest.main()
