"""Offline entity-GRU complete-command inference; never sends a game action."""
import numpy as np
import torch
from .priority_residual_predictor import PriorityResidualPredictor
from .entity_model import EntityMovementModel
from .entity_set import encode_entities
from .action_priority_head import classifier_features
from .more_replays import sha

class EntityPredictor(PriorityResidualPredictor):
    def __init__(self,baseline,normalization,vocabulary,priority_checkpoint,checkpoint,expected_sha256,actor=None):
        assert sha(checkpoint)==expected_sha256,'Unbound entity checkpoint'
        super().__init__(baseline,normalization,vocabulary,priority_checkpoint,actor)
        saved=torch.load(checkpoint,weights_only=True,map_location='cpu')
        assert saved['labels']==self.labels
        assert torch.equal(saved['mean'],self.mean) and torch.equal(saved['std'],self.std)
        assert torch.equal(saved['priority_mean'],self.extra_mean) and torch.equal(saved['priority_std'],self.extra_std)
        self.network=EntityMovementModel(self.model,self.head,saved['config']['dimension'],saved['config']['use_entities'])
        self.network.load_state_dict(saved['state_dict']);self.network.eval()

    def inputs(self,*args):
        result=super().inputs(*args);entities=encode_entities(args[0]).astype(np.float32)
        result['entities']=torch.from_numpy(entities)[None]
        result['entity_mask']=torch.ones((1,len(entities)),dtype=torch.bool)
        result['classifier_features']=classifier_features(result['extra'],result['priority_values'])
        return result

    @torch.no_grad()
    def distributions(self,inputs):
        logits,movement,teacher=self.network(inputs['x'],inputs['history'],inputs['entities'],inputs['entity_mask'],inputs['classifier_features'])
        family=logits.argmax(-1)
        parameters=self.network.parameter_logits(movement,teacher,inputs['grid'],inputs['valid'],family,inputs['rules'])
        return dict(action=logits.softmax(-1),coordinate=parameters.softmax(-1),priority_raw=self.head(teacher,inputs['extra']),context=teacher,movement=movement)
