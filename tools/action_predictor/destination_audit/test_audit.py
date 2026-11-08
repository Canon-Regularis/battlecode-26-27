import copy
import unittest
import numpy as np
import torch
from .audit import rivals,entity_trace,neighborhood,GROUPS
from ..data import features
from ..rich_data import candidate_grid
from ..reliable_model import JointModel


def entity(index,x,attack_range):
    return dict(entity=dict(kind=1,index=index),known=1,position=dict(x=x,y=0),
        team=1,health=100,maxHealth=100,attackRange=attack_range,type=0,cooldowns=[0,0])


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_rival_excludes_gold_and_repeat_but_retains_specials_and_ties(self):
        logp=np.zeros((2,291));logp[0,5]=10;logp[0,6]=9;logp[0,289]=8
        chosen,margin=rivals(logp,np.array([5,1]),np.array([6,0]))
        np.testing.assert_array_equal(chosen,[289,2]);np.testing.assert_array_equal(margin,[-2,0])

    def test_nearest_three_distinguishes_preserved_and_omitted_ranges(self):
        obs=dict(own=dict(team=0,position=dict(x=0,y=0)),entities=[entity(i,x,0) for i,x in enumerate((1,2,3,10))])
        result=entity_trace(obs,np.array([1,0]),np.array([10,0]))['enemy']
        self.assertTrue(result['nearest_entities_differ'])
        self.assertFalse(result['nearest_union_fully_in_current_top3'])
        self.assertTrue(result['represented_range_boundary_diff']);self.assertTrue(result['omitted_range_boundary_diff'])
        obs['entities'][-1]['known']=0
        result=entity_trace(obs,np.array([1,0]),np.array([10,0]))['enemy']
        self.assertEqual(result['living_known'],3);self.assertFalse(result['omitted_range_boundary_diff'])

    def test_nearest_sets_preserve_ties_and_empty_categories(self):
        obs=dict(own=dict(team=0,position=dict(x=0,y=0)),entities=[entity(1,-1,2),entity(2,1,2)])
        out=entity_trace(obs,np.array([0,0]),np.array([0,1]))
        self.assertFalse(out['enemy']['nearest_entities_differ']);self.assertTrue(out['enemy']['nearest_distance_equal'])
        self.assertFalse(out['camp']['available'])

    def test_neighborhood_keeps_boundary_and_obstacle_patterns_separate(self):
        route=dict(width=3,height=3,blocked=[0])
        self.assertEqual(neighborhood(route,np.array([1,1])),[1,0,0,0,0,0,0,0])
        corner=neighborhood(route,np.array([0,0]));self.assertEqual(corner.count(2),5)
        self.assertEqual(corner.count(1),0)

    def test_entity_attribute_omission_is_an_encoding_fact_not_full_input_collision(self):
        obs=dict(own=dict(team=0,position=dict(x=0,y=0)),entities=[entity(1,1,2)])
        changed=copy.deepcopy(obs);changed['entities'][0]['type']=5;changed['entities'][0]['cooldowns']=[8,9]
        np.testing.assert_array_equal(features(obs)[0],features(changed)[0])
        route=dict(width=20,height=20,blocked=[],spawns=[dict(minX=0,maxX=1,minY=0,maxY=1)]*2,altars=[])
        a=candidate_grid(obs,dict(movement=[]),route,None)[0]
        b=candidate_grid(changed,dict(movement=[]),route,None)[0]
        np.testing.assert_array_equal(a,b)
        # Relative coordinates still distinguish every destination.
        self.assertEqual(len(np.unique(a[:,:2],axis=0)),289)

    def test_pointwise_supported_pair_odds_ignore_other_grid_cells(self):
        torch.manual_seed(27)
        model=JointModel(253,24,15,dict(history=16,spatial=True,constrain=True))
        context=torch.randn(2,128);grid=torch.randn(2,289,20);grid[:,:,5]=1
        valid=torch.ones(2,289,dtype=torch.bool);family=torch.full((2,),8)
        rules=torch.ones(2,5);g,r=43,244
        changed=grid.clone();others=torch.ones(289,dtype=torch.bool);others[[g,r]]=False
        changed[:,others,:]+=7;changed[:,others,5]=0
        with torch.no_grad():
            a=model.parameter_logits(context,grid,valid,family,rules)
            b=model.parameter_logits(context,changed,valid,family,rules)
            torch.testing.assert_close(a[:,g]-a[:,r],b[:,g]-b[:,r],rtol=0,atol=2e-6)
            torch.testing.assert_close(model.candidate(grid)[:,[g,r]],model.candidate(changed)[:,[g,r]],rtol=0,atol=0)
        self.assertNotIn(0,GROUPS['task_channels']);self.assertNotIn(1,GROUPS['task_channels'])


if __name__=='__main__':unittest.main()
