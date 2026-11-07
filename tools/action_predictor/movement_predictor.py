"""Complete causal P05 predictor with separately trained movement parameters."""
import torch
from .priority_residual_predictor import PriorityResidualPredictor
from .movement_mixture import MovementMixture
from .more_replays import sha

class MovementMixturePredictor(PriorityResidualPredictor):
    def __init__(self,baseline,normalization,vocabulary,priority_checkpoint,checkpoint,expected_sha256,actor=None):
        assert sha(checkpoint)==expected_sha256
        super().__init__(baseline,normalization,vocabulary,priority_checkpoint,actor)
        saved=torch.load(checkpoint,weights_only=True,map_location='cpu')
        assert saved['labels']==self.labels and torch.equal(saved['mean'],self.mean) and torch.equal(saved['std'],self.std)
        self.movement=MovementMixture(self.model,saved['specialized']);self.movement.load_state_dict(saved['state_dict']);self.movement.eval()

    @torch.no_grad()
    def distributions(self,inputs):
        logits,context=self.model(inputs['x'],inputs['history']);family=logits.argmax(-1)
        parameters=self.model.parameter_logits(context,inputs['grid'],inputs['valid'],family,inputs['rules']).log_softmax(-1)
        selected=(family==8)|(family==3);gate=None;available=None
        if selected.any():
            params,gate,available=self.movement(inputs['x'][selected],inputs['history'][selected],inputs['grid'][selected],inputs['valid'][selected],family[selected],inputs['rules'][selected],context[selected]);parameters[selected]=params
        return dict(action=logits.softmax(-1),coordinate=parameters.exp(),priority_raw=self.head(context,inputs['extra']),context=context,continuation_gate=gate,prior_offset_available=available)
