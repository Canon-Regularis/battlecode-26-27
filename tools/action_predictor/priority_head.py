"""Only the logistic priority head changes; M01 representations stay frozen."""
import numpy as np
import torch
from torch import nn
from .reliable_model import priority_log_mass

EXTRA=7+16*2

def flatten(values,history):
    assert values.dtype==np.int64 and history.dtype==np.int64
    assert values.shape[1:]==(7,) and history.shape[1:]==(16,2)
    return np.concatenate((values,history.reshape(len(values),-1)),axis=1)

def normalizer(raw):
    # Train only. Compute in float64, retain exact integers in source evidence.
    return raw.mean(0).astype(np.float32),np.maximum(raw.std(0,ddof=1),.01).astype(np.float32)

def quantized_grid(grid):
    return np.asarray(grid,dtype=np.float16).astype(np.float32)

class PriorityHead(nn.Module):
    def __init__(self,original,use_inputs):
        super().__init__();state=torch.get_rng_state();self.linear=nn.Linear(128+EXTRA,2)
        with torch.no_grad():
            self.linear.weight.zero_();self.linear.weight[:,:128].copy_(original.weight);self.linear.bias.copy_(original.bias)
        torch.set_rng_state(state);self.use_inputs=use_inputs

    def forward(self,context,features):
        if not self.use_inputs:features=torch.zeros_like(features)
        return self.linear(torch.cat((context,features),-1))

    def log_mass(self,context,features,target):return priority_log_mass(self(context,features),target)

    def integer(self,context,features):return (self(context,features)[:,0]*100).round().long()
