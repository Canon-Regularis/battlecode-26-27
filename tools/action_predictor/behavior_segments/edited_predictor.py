"""Explicit opt-in loader for the unpromoted V44 inference-only weight edit."""
import json
import torch
from .predictor import BehaviorPredictor
from .weight_edit import REPORT,WORK
from .data import ROOT
from ..data import digest


class EditedBehaviorPredictor(BehaviorPredictor):
    def __init__(self):
        super().__init__('S01')
        result=json.loads((REPORT/'result.json').read_text());path=WORK/(result['selected']+'.pt')
        if digest(path)!=result['bindings'][str(path.relative_to(ROOT))]:raise ValueError('Edited checkpoint changed')
        saved=torch.load(path,map_location='cpu',weights_only=False)
        if not saved['inference_only'] or saved['plan_sha256']!=digest(REPORT/'plan.json'):raise ValueError('Edited checkpoint provenance mismatch')
        self.net.load_state_dict(saved['model']);self.edit=result['selected'];self.all_guards_passed=result['passed']
