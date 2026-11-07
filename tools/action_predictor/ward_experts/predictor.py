"""Read-only PRE-to-command ward expert serving; no recorded answers supplied."""
import numpy as np
import torch
from .features import build,INDICES
from .model import Placement,Typing,placement_modes
from .fit import inputs
from .integration import type_distribution,commands
from ..proposal_predictor import load_proposal_predictor
from ..command_mixture import FallbackDistribution
from ..consistent_data import base_features
from ..observation_data import compact_supplement,encode
from ..data import digest

class WardPredictor:
    def __init__(self,actor,placement=None,typing=None):
        self.frozen=load_proposal_predictor(actor).frozen;self.experts={}
        for supplied in (placement,typing):
            if supplied is None:continue
            path,expected=supplied;assert digest(path)==expected;saved=torch.load(path,weights_only=False,map_location='cpu');identifier=saved['identifier'];model=Placement(saved['counts']) if identifier.startswith('P') else Typing(saved['prior']);model.load_state_dict(saved['state']);model.eval();self.experts[identifier[0]]=(model,saved)
    def observe(self,event,step,round_number):self.frozen.observe(event,step,round_number)
    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,pre,priority_state,personal_wards=None):
        s=compact_supplement(supplement);raw=self.frozen.inputs(observation,s,route,round_number,pre,priority_state);q=FallbackDistribution(self.frozen,raw);modes,joint=q.modes();old=q.types;wardlp=q.spatial[14];oldmode=wardlp.argmax(-1);oldmodeLP=wardlp[torch.arange(len(oldmode)),oldmode]
        extra,rich,mask=build(observation,s,route,raw['history'][0].numpy(),personal_wards);global_=np.r_[q.context[0].numpy(),base_features(encode(observation,s,route,round_number),raw['history'][0].numpy()),extra];tile=np.column_stack((raw['grid'][0,INDICES].numpy(),rich)).astype(np.float16);data={'global':global_[None],'tile':tile[None],'mask':mask[None]};coordinate=None;parameterLP=None;logit=None
        for kind,(model,saved) in self.experts.items():
            x,t,m=inputs(data,slice(None),saved['mean'],saved['std'],saved['identifier'])
            if kind=='P':coordinate,parameterLP=placement_modes(model(x,t,m),m,wardlp[:,INDICES],oldmode,oldmodeLP)
            else:logit=model(x)
        types=type_distribution(old,logit);primary,secondary=commands(types.numpy(),old.numpy(),modes,joint,coordinate.numpy() if coordinate is not None else None,parameterLP.numpy() if parameterLP is not None else None)
        return dict(primary=primary,joint_MAP=secondary,ward_coordinate=int(coordinate[0]) if coordinate is not None else int(oldmode[0]),ward_probability=float(types[0,14].exp()),global_features=global_,tile_features=tile,candidate_mask=mask,probability_representation='normalized_observed_type_and_parameters;shop_arguments_unassessed',full_engine_legality='unassessed')
