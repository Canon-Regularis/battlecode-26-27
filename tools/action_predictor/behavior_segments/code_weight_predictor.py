"""Opt-in fixed-architecture code predictor from the V46/V47/V48 weight search."""
import json
import torch
from .predictor import BehaviorPredictor
from .code_weight_regularized import ROOT,REPORT,WORK
from ..data import digest


class CodeWeightPredictor(BehaviorPredictor):
    def __init__(self):
        super().__init__('S01')
        result=json.loads((REPORT/'result.json').read_text());path=WORK/'selected.pt'
        if digest(path)!=result['bindings'][str(path.relative_to(ROOT))]:
            raise ValueError('Code-weight checkpoint changed')
        saved=torch.load(path,map_location='cpu',weights_only=False)
        if not saved['inference_only'] or saved['plan_sha256']!=digest(REPORT/'plan.json'):
            raise ValueError('Code-weight checkpoint provenance mismatch')
        self.net.load_state_dict(saved['model'])
        self.research_target_met=result['target_met']

    def predict(self,*args,**kwargs):
        value=super().predict(*args,**kwargs)
        value['research_code_accuracy_target_met']=self.research_target_met
        value['promoted']=False
        return value
