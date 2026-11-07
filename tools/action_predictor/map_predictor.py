"""Replay-oriented map/GRU inference from supplied bot-visible PRE inputs only."""
import numpy as np
import torch
import torch.nn.functional as F

from .reliable_predictor import ReliablePredictor
from .map_model import MapJointModel
from .spatial_data import raster, MapInputs
from .data import features
from .rich_data import extra_features, history_vector, candidate_grid, SPATIAL
from .targets import OFFSETS, point
from .audit import cursor


def single_map_inputs(public_map, team, position):
    image = raster(public_map, team)
    h, w = image.shape[1:]
    tensor = torch.from_numpy(image).float()[None]
    coarse = F.adaptive_avg_pool2d(tensor, (32, 32))
    coarse[:, 4:] = F.adaptive_max_pool2d(tensor[:, 4:], (32, 32))
    known = point(position)
    arrays = dict(atlas=np.pad(image, ((0,0),(11,11),(11,11)))[None],
        global_atlas=coarse.numpy(), sizes=np.array([[w,h]], dtype=np.int16),
        train_map_id=np.array([0]), train_xy=np.array([[position['x'],position['y']] if known else [0,0]]),
        train_known=np.array([known]))
    return MapInputs(arrays, 'train').batch(torch.tensor([0]))


class MapPredictor(ReliablePredictor):
    """Call observe only for actual past actions; predict never executes an action.

    public_map follows public_map.cjs's static terrain/objective schema. All other
    inputs use the existing recorded personal-observation schema. New instance per
    actor/game. This wrapper does not integrate with or alter the deployed bot.
    """
    def __init__(self, checkpoint, actor=None):
        saved = torch.load(checkpoint, weights_only=True, map_location='cpu')
        if saved.get('architecture') != 'public-map-cnn-gru-v1':
            raise ValueError('Use the matching predictor for this checkpoint architecture')
        self.labels=saved['labels'];self.config=saved['config'];self.mean=saved['mean'];self.std=saved['std']
        self.model=MapJointModel(len(self.mean),len(self.labels)+9,len(self.labels),self.config)
        self.model.load_state_dict(saved['state_dict']);self.model.eval()
        self.actor=actor;self.events=[];self.last_move=None

    @torch.no_grad()
    def predict(self, observation, supplement, public_map, round_number, pre_cursor):
        if supplement['pre'] != pre_cursor:
            raise ValueError('Supplement must match the current PRE cursor')
        actor=observation['own']['entity']['index']
        if self.actor is None:self.actor=actor
        if self.actor != actor:raise ValueError('Do not mix actors in one predictor')
        if self.events and self.events[-1][0] > cursor(pre_cursor):
            raise ValueError('Future observed actions cannot enter a prediction')
        route=public_map['route']
        basic,_=features(observation);extra,_=extra_features(observation,supplement,route,round_number)
        x=np.concatenate((basic,extra))
        history=np.zeros((32,len(self.labels)+9),dtype=np.float32)
        for i,event in enumerate(self.events):
            at=32-len(self.events)+i
            history[at]=history_vector(event,round_number,observation['own'].get('position'),self.labels)
            if self.labels[event[1]] not in SPATIAL+['end']:
                history[at,len(self.labels)+1:len(self.labels)+3]=0
        last=None
        if self.last_move:
            step=self.last_move
            last=np.array([step['to']['x']-step['from']['x'],step['to']['y']-step['from']['y']])
        grid,valid,_=candidate_grid(observation,supplement,route,last)
        own=observation['own'];local,global_map=single_map_inputs(public_map,own['team'],own.get('position'))
        logits,context,spatial=self.model(((torch.from_numpy(x)-self.mean)/self.std)[None],
                                         torch.from_numpy(history)[None],local,global_map)
        probability=logits[0].softmax(-1);family=int(probability.argmax());name=self.labels[family]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,probability.tolist())),parameter=None,
                    full_engine_legality='unassessed')
        if name in SPATIAL:
            props=own.get('abilityProps',[{},{}])
            rules=torch.tensor([[own.get('attackRange',0),props[0].get('range',0),props[1].get('range',0),
                                 props[0].get('target',0),props[1].get('target',0)]],dtype=torch.float32)
            # Match the frozen dataset's float16 storage and float32 model input.
            p=self.model.parameter_logits(context,torch.from_numpy(grid.astype(np.float16)).float()[None],torch.from_numpy(valid)[None],
                                          torch.tensor([family]),rules,spatial)[0].softmax(-1)
            index=int(p.argmax());position=own.get('position')
            if index<289 and point(position):
                result['parameter']=dict(position=dict(x=position['x']+int(OFFSETS[index,0]),
                                                      y=position['y']+int(OFFSETS[index,1])),conditional_probability=float(p[index]))
            else:result['parameter']=dict(unassessed=True,reason='Outside coordinate window or unknown own position')
        elif name=='priority':
            result['parameter']=dict(priority=int((self.model.priority(context)[0,0]*100).round()))
        elif name=='shop':
            result['parameter']=dict(unassessed=True,reason='Original item/count unavailable in recorded roots')
        return result
