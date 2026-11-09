"""Explicit experimental loader for the V45 balanced code-head checkpoint."""
import json
import torch
from .predictor import BehaviorPredictor
from .rare_code_edit import ROOT, REPORT, WORK
from ..data import digest


class RareCodePredictor(BehaviorPredictor):
    def __init__(self):
        super().__init__('S01')
        result = json.loads((REPORT/'result.json').read_text())
        path = WORK/'selected.pt'
        if digest(path) != result['bindings'][str(path.relative_to(ROOT))]:
            raise ValueError('Rare-code checkpoint changed')
        saved = torch.load(path, map_location='cpu', weights_only=False)
        if not saved['inference_only'] or saved['plan_sha256'] != digest(REPORT/'plan.json'):
            raise ValueError('Rare-code checkpoint provenance mismatch')
        self.net.load_state_dict(saved['model'])
        self.supported_codes = saved['supported_codes']
        self.all_guards_passed = result['passed']

    def predict(self, *args, **kwargs):
        result = super().predict(*args, **kwargs)
        result['supported_codes'] = self.supported_codes
        result['all_guards_passed'] = self.all_guards_passed
        return result
