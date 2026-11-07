"""Causal adapter from frozen G00/P05 to repaired proposals; no selector fit."""
import torch
from .proposal_generator import generate,SPATIAL
from .observation_data import compact_supplement
from .audit import cursor

class ProposalPredictor:
    """Supplies candidates for a future selector; never reuses A00 slot weights.

    construct with the reviewed MovementMixturePredictor (G00 + P05). observe
    every actual earlier own root, then propose at matching PRE. No game actions.
    """
    def __init__(self,frozen_predictor):self.frozen=frozen_predictor
    def observe(self,event,step,round_number):self.frozen.observe(event,step,round_number)

    @torch.no_grad()
    def arguments(self,inputs):
        model=self.frozen.model;logits,context=model(inputs['x'],inputs['history']);encoded=self.frozen.movement.encode(inputs['x'],inputs['history'],context);coords={}
        if len(logits)!=1:raise ValueError('One personal PRE per proposal bundle')
        for action in SPATIAL:
            code=self.frozen.labels.index(action);family=torch.full((len(logits),),code,dtype=torch.int64)
            if action in ('move','blocked'):lp=self.frozen.movement.parameter_log_probs(encoded,inputs['grid'],inputs['valid'],family,inputs['rules'])[0]
            else:lp=model.parameter_logits(context,inputs['grid'],inputs['valid'],family,inputs['rules'])
            coords[action]=int(lp[0].argmax())
        # Crucially independent of logits.argmax(): P05 is called for every PRE,
        # including missing position and a non-priority G00 action forecast.
        priority_raw=self.frozen.head(context,inputs['extra']);priority=int(self.frozen.head.integer(priority_raw,inputs['priority_values'])[0])
        return dict(coordinates=coords,priority=priority,prefer_blocked=bool(logits[0,3]>logits[0,8]))

    def propose(self,observation,supplement,route,round_number,pre_cursor,priority_state,personal_targets=None):
        if self.frozen.events and self.frozen.events[-1][0]>cursor(pre_cursor):raise ValueError('Future own-action history')
        inputs=self.frozen.inputs(observation,compact_supplement(supplement),route,round_number,pre_cursor,priority_state);conditional=self.arguments(inputs)
        bundle=generate(observation,supplement,route,inputs['history'][0].numpy(),conditional,personal_targets)
        return dict(bundle,conditional_arguments=conditional,selection='unfitted; historical A00 checkpoint is not compatible with repaired proposal schema')

def load_proposal_predictor(actor=None):
    """Load the existing reviewed G00 + P05 models; create no new checkpoint."""
    import json
    from .priority_fit_v3 import ROOT,BASE,context_directory
    from .priority_residual_fit import VOCAB
    from .movement_predictor import MovementMixturePredictor
    from .data import digest
    reports=ROOT/'tools/action_predictor/experiments'
    g=json.loads((reports/'v9/G00.json').read_text());p=json.loads((reports/'v8/P05.json').read_text());m=json.loads((reports/'v5/M01.json').read_text())
    baseline=BASE/'runs/M01/model.pt';priority=BASE.parent/'v8/runs/P05/model.pt'
    assert digest(baseline)==m['checkpoint_sha256'] and digest(priority)==p['checkpoint_sha256']
    return ProposalPredictor(MovementMixturePredictor(baseline,context_directory()/'extra-normalization.npz',json.loads(VOCAB.read_text()),priority,BASE.parent/'v9/runs/G00/model.pt',g['checkpoint_sha256'],actor))
