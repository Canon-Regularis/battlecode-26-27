"""Causal offline action classifier over the retained M01/P05 parameter paths."""
import torch
from .priority_residual_predictor import PriorityResidualPredictor
from .action_priority_head import ActionPriorityHead,classifier_features,routed_coordinates
from .more_replays import sha

class ActionPriorityPredictor(PriorityResidualPredictor):
    def __init__(self,baseline,normalization,vocabulary,priority_checkpoint,use_inputs=False,classifier_checkpoint=None,actor=None):
        super().__init__(baseline,normalization,vocabulary,priority_checkpoint,actor)
        self.classifier=ActionPriorityHead(self.model.action,use_inputs)
        if classifier_checkpoint is not None:
            saved=torch.load(classifier_checkpoint,weights_only=True,map_location='cpu')
            assert saved['architecture']=='frozen-M01-P05-action-priority-v1'
            assert saved['baseline_sha256']==sha(baseline) and saved['priority_sha256']==sha(priority_checkpoint)
            assert saved['labels']==self.labels and saved['config']['use_inputs']==bool(use_inputs)
            assert torch.equal(saved['extra_mean'],self.extra_mean) and torch.equal(saved['extra_std'],self.extra_std)
            self.classifier.load_state_dict(saved['head_state'])
        self.classifier.eval()

    def inputs(self,*args):
        result=super().inputs(*args)
        result['classifier_features']=classifier_features(result['extra'],result['priority_values'])
        return result

    @torch.no_grad()
    def distributions(self,inputs):
        _,context=self.model(inputs['x'],inputs['history'])
        logits=self.classifier(context,inputs['classifier_features'])
        parameters=routed_coordinates(self.model,context,inputs['grid'],inputs['valid'],logits,inputs['rules']).softmax(-1)
        return dict(action=logits.softmax(-1),coordinate=parameters,priority_raw=self.head(context,inputs['extra']),context=context)
