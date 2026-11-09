"""Matched soft-PRE classifier inputs; no priority/channel transition masks."""
import numpy as np
import torch
from torch import nn

CLASSIFIER_EXTRA=41

def classifier_features(normalized_priority,values):
    assert values.dtype==torch.int64 and values.ndim==2 and values.shape[1]==7
    assert normalized_priority.shape==(len(values),39)
    both=(values[:,1]==1)&(values[:,3]==1)
    changed=both&(values[:,0]!=values[:,2])
    # Zero on fully observed rows: do not add a treatment-only constant bias.
    return torch.cat((normalized_priority,(~both)[:,None].float(),changed[:,None].float()),-1)

class ActionPriorityHead(nn.Module):
    def __init__(self,original,use_inputs):
        super().__init__();state=torch.get_rng_state()
        self.core=nn.Linear(128,original.out_features)
        self.extra=nn.Linear(CLASSIFIER_EXTRA,original.out_features,bias=False)
        with torch.no_grad():
            self.core.weight.copy_(original.weight);self.core.bias.copy_(original.bias);self.extra.weight.zero_()
        torch.set_rng_state(state);self.use_inputs=bool(use_inputs)

    def forward(self,context,features):
        assert context.shape==(len(features),128) and features.shape[1]==CLASSIFIER_EXTRA
        if not self.use_inputs:features=torch.zeros_like(features)
        # Separate affine products preserve exact original-logit initialization.
        return self.core(context)+self.extra(features)

def routed_coordinates(model,context,grid,valid,logits,rules):
    """Never supply the recorded target family to runtime parameter routing."""
    return model.parameter_logits(context,grid,valid,logits.argmax(-1),rules)

def assemble_predictions(baseline,logits,proposed,y,priority_code,priority_nll64):
    result={k:v.copy() for k,v in baseline.items()}
    logp=logits.log_softmax(-1)
    result['prediction']=logp.argmax(-1).numpy()
    result['type_nll']=-logp.gather(1,y[:,None])[:,0].numpy()
    result['proposed_coordinate']=proposed.numpy()
    result['nll']=result['type_nll']+result['param_nll']
    # Preserve P05's original float64-priority-loss then float32 archive rounding.
    selected=y.numpy()==priority_code
    result['nll'][selected]=(result['type_nll'][selected].astype(np.float64)+priority_nll64[selected]).astype(result['nll'].dtype)
    return result
