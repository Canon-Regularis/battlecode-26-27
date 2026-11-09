"""Opt-in code-conditioned movement prediction; caller still chooses command family."""
import torch
from .expanded_code_predictor import ExpandedCodePredictor
from . import code_movement_fit as fit, model


class CodeMovementPredictor(ExpandedCodePredictor):
    def __init__(self, arm='predicted'):
        if arm not in fit.ARMS: raise ValueError('Unknown movement arm')
        super().__init__()
        result = fit.read(fit.REPORT/'result.json'); fit.check(result)
        plan = fit.read(fit.REPORT/'plan.json'); fit.check(plan)
        self.net = fit.policy(arm, plan, self.plan)

    @torch.no_grad()
    def predict(self, current, route, round_number, previous=None, previous_mask=None, state=None):
        captured = []
        handle = self.net.register_forward_hook(lambda module, args, output: captured.append(output['move'][0]))
        try:
            value = super().predict(current, route, round_number, previous, previous_mask, state)
        finally:
            handle.remove()
        step = dict(observed=current is not None, input=current, movement=None)
        support, _ = model.move_support(dict(steps=[step]))
        value['conditional_movement'] = None
        value['movement_probabilities'] = None
        if support.any():
            probabilities = captured[0].masked_fill(~support[0], -1e9).softmax(-1)
            offset = model.OFFSETS[int(probabilities.argmax())]
            origin = current['observation']['own']['position']
            value['conditional_movement'] = (origin['x']+offset[0], origin['y']+offset[1])
            value['movement_probabilities'] = probabilities.tolist()
        value['movement_scope'] = 'Destination conditional on choosing move; this does not select a command family.'
        return value
