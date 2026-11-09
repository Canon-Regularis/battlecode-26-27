import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from .reliable_model import JointModel
from .observation_model import ObservationHistoryModel
from .observation_predictor import ObservationPredictor
from .observation_data import encode,safe_observation
from .observation_metrics import compare,point_metrics
from .reliable_train import LABELS,summarize


def fixture():
    obs=dict(perspective=dict(team=0,champion=0),own=dict(entity=dict(kind=1,index=0),team=0,type=0,known=15,
             position=dict(x=4,y=4),health=800,maxHealth=1000,alive=True,gems=0,items=[]),entities=[])
    route=dict(width=20,height=20,blocked=[],altars=[],spawns=[dict(minX=0,minY=0,maxX=2,maxY=2),dict(minX=18,minY=18,maxX=20,maxY=20)])
    supplement=dict(pre='1:0',own=dict(gold=0),movement=[dict(x=5,y=4)],restrictions=0,can_shop=False,can_shop_consumables=False)
    return obs,supplement,route


class ObservationTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_retained_initialization_heads_and_shuffle_stream(self):
        config=dict(history=16,rich=True,spatial=True,constrain=True,observations=True)
        torch.manual_seed(26);base=JointModel(253,24,15,config);rng=torch.get_rng_state().clone()
        torch.manual_seed(26);model=ObservationHistoryModel(253,24,15,config)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertEqual(sum(p.numel() for p in base.parameters()),104160)
        self.assertEqual(sum(p.numel() for p in model.parameters()),119392)
        self.assertIs(type(model).parameter_logits,JointModel.parameter_logits)
        for key,value in base.state_dict().items():
            if key=='history.weight_ih_l0':torch.testing.assert_close(value,model.state_dict()[key][:,:24])
            else:torch.testing.assert_close(value,model.state_dict()[key])
        x=torch.randn(4,253);actions=torch.randn(4,32,24);obs=torch.randn(4,16,253);gaps=torch.rand(4,16,5)
        expected,_=base(x,actions);actual,_=model(x,actions,obs,gaps)
        torch.testing.assert_close(expected,actual,rtol=2e-6,atol=2e-6)

    def test_observation_content_control_and_missing_mask(self):
        config=dict(history=16,rich=True,spatial=True,constrain=True,observations=False)
        model=ObservationHistoryModel(8,24,15,config)
        with torch.no_grad():model.history.weight_ih_l0[:,24:].normal_(0,.1)
        x=torch.randn(3,8);actions=torch.randn(3,32,24);a=torch.randn(3,16,8);b=a+10;gaps=torch.ones(3,16,5)
        torch.testing.assert_close(model(x,actions,a,gaps)[0],model(x,actions,b,gaps)[0],rtol=0,atol=0)
        model.config=model.config|dict(observations=True)
        self.assertGreater(float((model(x,actions,a,gaps)[0]-model(x,actions,b,gaps)[0]).abs().max().detach()),1e-5)
        gaps[:,:,1]=0
        torch.testing.assert_close(model(x,actions,a,gaps)[0],model(x,actions,b,gaps)[0],rtol=0,atol=0)

    def test_personal_visibility_and_perspective(self):
        obs,supplement,_=fixture();safe_observation(obs,0,0,supplement)
        hidden=copy.deepcopy(obs);hidden['entities']=[dict(entity=dict(kind=1,index=4),team=1,known=0,position=dict(x=6,y=6))]
        with self.assertRaises(AssertionError):safe_observation(hidden,0,0,supplement)
        with self.assertRaises(AssertionError):safe_observation(obs,1,0,supplement)

    def predictor(self,path):
        obs,supplement,route=fixture();n=len(encode(obs,supplement,route,1))
        config=dict(history=16,rich=True,spatial=True,constrain=True,observations=True)
        model=ObservationHistoryModel(n,len(LABELS)+9,len(LABELS),config)
        torch.save(dict(state_dict=model.state_dict(),config=config,labels=LABELS,mean=torch.zeros(n),std=torch.ones(n),
                        architecture='personal-observation-history-gru-v1'),path)
        return ObservationPredictor(path,actor=0)

    def test_causal_roundtrip_gaps_missing_and_snapshot_lifetime(self):
        obs,supplement,route=fixture()
        step=dict(actor=dict(kind=1,index=0),kind=4,**{'from':dict(x=4,y=4),'to':dict(x=5,y=4)})
        with tempfile.TemporaryDirectory() as directory:
            predictor=self.predictor(Path(directory)/'model.pt')
            predictor.observe(obs,supplement,route,1,'turnA','1:0','2:0',step)
            current=copy.deepcopy(obs);current['own']['position']=dict(x=5,y=4);now=supplement|dict(pre='5:0')
            before=predictor.inputs(current,now,route,4,'turnB','5:0')
            self.assertEqual(before[3][0,-1].tolist(),[1.,1.,np.float32(.03),1.,np.float32(.03)])
            obs['own']['position']['x']=999;step['to']['x']=999
            after=predictor.inputs(current,now,route,4,'turnB','5:0')
            for a,b in zip(before,after):torch.testing.assert_close(a,b,rtol=0,atol=0)
            predictor.observe(None,None,route,4,'turnB','3:0','4:0',dict(kind=8,actor=dict(kind=1,index=0)))
            values=predictor.inputs(current,now,route,4,'turnB','5:0')
            self.assertEqual(values[3][0,-1,:2].tolist(),[1.,0.])
            prediction=predictor.predict(current,now,route,4,'turnB','5:0')
            self.assertEqual(prediction['present_history'],2);self.assertEqual(prediction['available_history'],1)
            self.assertAlmostEqual(sum(prediction['action_probabilities'].values()),1.,places=6)
            predictor.observe(None,None,route,4,'turnB','6:0','7:0',dict(kind=8,actor=dict(kind=1,index=0)))
            with self.assertRaisesRegex(ValueError,'Future'):
                predictor.predict(current,now,route,4,'turnB','5:0')

    def test_cursor_distances_are_not_neural_time_inputs(self):
        obs,supplement,route=fixture();step=dict(kind=8,actor=dict(kind=1,index=0))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.pt';a=self.predictor(path);b=ObservationPredictor(path,actor=0)
            a.observe(obs,supplement,route,1,'a','1:0','2:0',step)
            b.observe(obs,supplement|dict(pre='10001:0'),route,1,'a','10001:0','10002:0',step)
            left=a.inputs(obs,supplement|dict(pre='3:0'),route,2,'b','3:0')
            right=b.inputs(obs,supplement|dict(pre='10003:0'),route,2,'b','10003:0')
            for x,y in zip(left,right):torch.testing.assert_close(x,y,rtol=0,atol=0)

    def test_sparse_context_group_uncertainty_retains_zero_support_groups(self):
        n=10;y=np.full(n,LABELS.index('move'));raw=dict(y=y,py=np.full(n,144),priority=np.zeros(n),
            group=np.repeat(np.arange(5),2),pos_known=np.ones(n,bool))
        pred=dict(prediction=y.copy(),coordinate=raw['py'].copy(),priority=np.zeros(n),
                  top5=np.tile(np.arange(144,149),(n,1)),nll=np.ones(n))
        aux=dict(available=np.full(n,16),direction=np.array([3,3]+[2]*8),near_obstacle=np.ones(n,bool),
                 visible_change=np.ones(n),gaps=np.ones((n,16,5)))
        result=compare(raw,pred,pred,aux)
        ci=result['direction_change']['paired_intervals']['move_exact']
        self.assertEqual(ci['low'],0.);self.assertEqual(ci['high'],0.)
        self.assertGreater(ci['valid_draws'],0);self.assertLess(ci['valid_draws'],2000)
        self.assertEqual(result['direction_change']['observations']['group_support'],{'0':2,'1':0,'2':0,'3':0,'4':0})
        self.assertEqual(result['overall']['observations']['rows'],10)

    def test_joint_accounting_matches_frozen_scorer_including_unknown_shops(self):
        y=np.array([8,9,11,8,8]);n=len(y)
        raw=dict(y=y,py=np.array([144,-1,-1,145,144]),priority=np.zeros(n),group=np.array([0,0,1,1,1]),
                 move_mask=np.ones((n,289),bool),hp_alive=np.ones(n,bool),channel=np.zeros(n),flags=np.full(n,1026),
                 restrictions=np.zeros(n,dtype=int),ability_ready=np.ones((n,2),bool),ward_charges=np.ones(n),
                 gems=np.ones(n),shop=np.ones(n,bool))
        pred=dict(prediction=y.copy(),coordinate=np.array([144,144,144,144,144]),priority=np.zeros(n),
                  proposed_coordinate=np.full(n,144),top5=np.tile(np.arange(144,149),(n,1)),nll=np.ones(n))
        existing=summarize(raw,pred);new=point_metrics(raw,pred,np.ones(n,bool))
        self.assertAlmostEqual(existing['strict_full_command_accuracy'],new['joint_accuracy'])
        self.assertAlmostEqual(existing['macro_f1'],new['macro_f1'],places=6)
        self.assertEqual(existing['parameters']['move']['exact_accuracy'],new['parameters']['move']['exact_accuracy'])
        self.assertEqual(sum(new['per_action_support'].values()),n)


if __name__=='__main__':unittest.main()
