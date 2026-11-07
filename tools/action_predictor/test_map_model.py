import unittest
import copy
from pathlib import Path
import tempfile

import numpy as np
import torch

from .map_model import MapJointModel
from .reliable_model import JointModel
from .spatial_data import raster, MapInputs
from .spatial_train import infer as spatial_infer
from .reliable_train import infer as baseline_infer
from .map_predictor import MapPredictor
from .test_predictor import observation
from .data import features
from .rich_data import extra_features
from .reliable_train import LABELS


class MapTests(unittest.TestCase):
    def test_saved_predictor_uses_only_pre_inputs_and_rejects_future_history(self):
        torch.set_num_threads(1)
        obs=observation()
        route=dict(width=12,height=12,blocked=[],altars=[],
                   spawns=[dict(minX=0,minY=0,maxX=2,maxY=2),dict(minX=10,minY=10,maxX=12,maxY=12)])
        public=dict(route=route,walls=[],holes=[],bushes=[],camps=[])
        supplement=dict(pre='0:0',own=dict(gold=0),restrictions=0,can_shop=False,
                        can_shop_consumables=False,movement=[dict(x=5,y=4)])
        basic,_=features(obs);extra,_=extra_features(obs,supplement,route,0)
        n=len(basic)+len(extra);config=dict(history=16,rich=True,spatial=True,constrain=True)
        model=MapJointModel(n,len(LABELS)+9,len(LABELS),config)
        with torch.no_grad():
            model.action.weight.zero_();model.action.bias.fill_(-100);model.action.bias[LABELS.index('move')]=100
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.pt'
            torch.save(dict(state_dict=model.state_dict(),labels=LABELS,config=config,
                            mean=torch.zeros(n),std=torch.ones(n),architecture='public-map-cnn-gru-v1'),path)
            predictor=MapPredictor(path)
            first=predictor.predict(obs,supplement,public,0,'0:0')
            self.assertEqual(first['action'],'move')
            self.assertEqual(first['parameter']['position'],dict(x=5,y=4))
            hidden=copy.deepcopy(obs)
            hidden['entities'].append(dict(known=0,entity=dict(kind=1,index=99),team=1,position=dict(x=5,y=5),health=100))
            self.assertEqual(first,predictor.predict(hidden,supplement,public|dict(future_camp_state='dead'),0,'0:0'))
            predictor.observe('3:0',dict(kind=8,actor=dict(kind=1,index=0)),0)
            with self.assertRaisesRegex(ValueError,'Future'):
                predictor.predict(obs,supplement,public,0,'0:0')

    def test_scoring_matches_existing_model_at_initialization(self):
        torch.set_num_threads(1)
        config=dict(history=16,rich=True,spatial=True,constrain=True)
        torch.manual_seed(26);base=JointModel(7,24,15,config)
        torch.manual_seed(26);model=MapJointModel(7,24,15,config)
        data=dict(x=torch.randn(32,7),history=torch.randn(32,32,24),grid=torch.rand(32,289,20),
                  valid=torch.ones(32,289,dtype=torch.bool),y=torch.arange(32)%15,
                  py=torch.arange(32)%289,priority=torch.zeros(32),rules=torch.ones(32,5)*8)
        arrays=dict(atlas=np.ones((1,8,50,50),np.uint8),global_atlas=np.ones((1,8,32,32),np.float32),
                    sizes=np.array([[28,28]]),train_map_id=np.zeros(32,np.int64),
                    train_xy=np.ones((32,2),np.int64)*14,train_known=np.ones(32,bool))
        expected=baseline_infer(base,data)
        actual=spatial_infer(model,data,MapInputs(arrays,'train'))
        self.assertEqual(expected.keys(),actual.keys())
        for key in expected:
            np.testing.assert_allclose(expected[key],actual[key],rtol=1e-6,atol=2e-6,err_msg=key)

    def test_public_raster_ignores_hidden_state_and_respects_team(self):
        data = dict(route=dict(width=5, height=4, altars=[dict(x=3, y=2)],
                    spawns=[dict(minX=0,minY=0,maxX=1,maxY=1),dict(minX=4,minY=3,maxX=5,maxY=4)]),
                    walls=[6], holes=[7], bushes=[8], camps=[dict(x=2,y=2)])
        a = raster(data, 0)
        b = raster(data | dict(hidden_enemy_position=[4, 4], future_camp_state='dead'), 0)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(a[1,1,1], 1)
        self.assertEqual(a[2,1,2], 1)
        self.assertEqual(a[3,1,3], 1)
        self.assertEqual(a[4,2,3], 1)
        self.assertEqual(a[7,2,2], 1)
        other = raster(data, 1)
        np.testing.assert_array_equal(a[5], other[6])
        np.testing.assert_array_equal(a[6], other[5])

    def test_local_window_alignment_edges_and_unknown_actor(self):
        atlas = np.zeros((1,8,27,27), np.uint8)
        atlas[0,0,11:16,11:16] = 1
        atlas[0,1,11+2,11+3] = 1
        arrays = dict(atlas=atlas, global_atlas=np.zeros((1,8,32,32),np.float32),
                      sizes=np.array([[5,5]]), train_map_id=np.array([0,0]),
                      train_xy=np.array([[0,0],[0,0]]), train_known=np.array([True,False]))
        local, global_map = MapInputs(arrays,'train').batch(torch.arange(2))
        self.assertEqual(tuple(local.shape),(2,8,23,23))
        self.assertEqual(local[0,0,11,11],1)
        self.assertEqual(local[0,0,10,11],0)
        self.assertEqual(local[0,1,13,14],1)
        self.assertEqual(local[1].sum(),0)
        self.assertEqual(global_map[0,8,0,0],1)
        self.assertEqual(global_map[1,8].sum(),0)

    def test_initial_model_and_shuffle_match_baseline(self):
        torch.set_num_threads(1)
        config = dict(history=16, rich=True, spatial=True, constrain=True)
        torch.manual_seed(26)
        base = JointModel(7,24,15,config)
        state = torch.get_rng_state().clone()
        torch.manual_seed(26)
        model = MapJointModel(7,24,15,config)
        self.assertTrue(torch.equal(state,torch.get_rng_state()))
        x=torch.randn(3,7); history=torch.randn(3,32,24)
        grid=torch.randn(3,289,20); grid[:,:,5]=1
        valid=torch.ones(3,289,dtype=torch.bool); family=torch.tensor([8,8,8]); rules=torch.ones(3,5)*8
        a,context=base(x,history)
        b,new_context,spatial=model(x,history,torch.rand(3,8,23,23),torch.rand(3,9,32,32))
        self.assertEqual(tuple(spatial.shape),(3,289,8))
        torch.testing.assert_close(a,b,rtol=0,atol=0)
        torch.testing.assert_close(base.parameter_logits(context,grid,valid,family,rules),
                                   model.parameter_logits(new_context,grid,valid,family,rules,spatial),rtol=1e-6,atol=1e-6)
        optimizer=torch.optim.AdamW(model.parameters(),lr=.001)
        for _ in range(3):
            optimizer.zero_grad()
            logits,c,s=model(x,history,torch.rand(3,8,23,23),torch.rand(3,9,32,32))
            loss=-logits.log_softmax(-1)[:,8].mean()-model.parameter_logits(c,grid,valid,family,rules,s)[:,140].mean()
            loss.backward();optimizer.step()
        self.assertGreater(float(model.local_map[0].weight.grad.abs().sum()),0)
        self.assertGreater(float(model.global_map[0].weight.grad.abs().sum()),0)


if __name__ == '__main__':
    unittest.main()
