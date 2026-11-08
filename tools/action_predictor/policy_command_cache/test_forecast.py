"""Independent all-command mixture checks, including nonselected families."""
import unittest
import numpy as np
import torch
from .forecast import family_forecast
from ..learned_policy.model import SPATIAL


class Fixture:
    def __init__(self,types,space):self.type_array=types;self.space_array=space
    def types(self,step):return torch.from_numpy(np.log(self.type_array))
    def spatial_log_probs(self,step,grid,valid,rules,family):
        if not bool((family==family[0]).all()):raise ValueError('Fixture expects one requested family')
        return torch.from_numpy(np.log(self.space_array[int(family[0])]))


class ForecastContracts(unittest.TestCase):
    def test_all_family_modes_match_independent_enumeration_without_answers(self):
        rng=np.random.default_rng(98211)
        types=rng.uniform(.1,1,(3,4,15));types/=types.sum(-1,keepdims=True)
        priors=rng.uniform(.1,1,(3,4));priors/=priors.sum(-1,keepdims=True)
        space={family:rng.uniform(.001,1,(3,4,291)) for family in SPATIAL}
        for p in space.values():p/=p.sum(-1,keepdims=True)
        # Distinct, intentionally unequal component geometry in every family.
        fixture=Fixture(types,space)
        priority=np.array([-77,12,54],np.int64);priority_mass=np.array([.3,.8,.6])
        step={'logprior':torch.from_numpy(np.log(priors)),'context':torch.zeros((3,4,128))}
        args=dict(grid=torch.zeros((3,1)),valid=torch.ones((3,1),dtype=torch.bool),rules=torch.zeros((3,1)),
                  priority_mode=torch.from_numpy(priority),priority_mode_logp=torch.from_numpy(np.log(priority_mass)))
        p=family_forecast(fixture,step,**args)
        marginal=(priors[:,:,None]*types).sum(1)
        modes=marginal.copy();coordinates=np.full((3,15),-1,np.int64)
        for family in SPATIAL:
            mass=(priors[:,:,None]*types[:,:,family,None]*space[family]).sum(1)
            coordinates[:,family]=mass.argmax(-1);modes[:,family]=mass.max(-1)
        modes[:,9]*=priority_mass
        choice=modes.argmax(-1)
        np.testing.assert_allclose(p['type_logp'],np.log(marginal),rtol=0,atol=1e-12)
        np.testing.assert_allclose(p['mode_joint_logp'],np.log(modes),rtol=0,atol=1e-12)
        np.testing.assert_array_equal(p['family_coordinate'],coordinates)
        np.testing.assert_array_equal(p['prediction'],choice)
        np.testing.assert_array_equal(p['proposed_coordinate'],coordinates[np.arange(3),choice])
        np.testing.assert_array_equal(p['priority'],priority)
        self.assertFalse(any(value.requires_grad for value in p.values()))
        with self.assertRaises(TypeError):family_forecast(fixture,step,**args,y=torch.zeros(3,dtype=torch.int64))

    def test_ties_keep_existing_family_and_coordinate_order(self):
        types=np.ones((1,1,15))/15
        space={family:np.ones((1,1,291))/291 for family in SPATIAL}
        p=family_forecast(Fixture(types,space),{'logprior':torch.zeros((1,1))},
            torch.zeros((1,1)),torch.ones((1,1),dtype=torch.bool),torch.zeros((1,1)),
            torch.tensor([1]),torch.zeros(1))
        self.assertEqual(int(p['prediction'][0]),0)
        for family in SPATIAL:self.assertEqual(int(p['family_coordinate'][0,family]),0)
        self.assertEqual(int(p['proposed_coordinate'][0]),-1)


if __name__=='__main__':unittest.main()
