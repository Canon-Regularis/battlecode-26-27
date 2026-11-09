"""Goal selectors with no learned input encoder and explicit game exclusion."""
import torch
from torch import nn


class RawGoalSelector(nn.Module):
    def __init__(self):
        super().__init__();self.net=nn.Sequential(nn.Linear(660,64),nn.Tanh(),nn.Linear(64,1),nn.Tanh())
    def forward(self,x):return self.net(x).squeeze(-1)


def head_name(excluded):
    return 'exclude-'+'-'.join(map(str,sorted(excluded))) if excluded else 'full'


def training_head(outer,group_fold,crossfit):
    pool=[i for i in range(4) if i!=outer]
    if group_fold not in pool:raise ValueError('Outer held group cannot supply training rows')
    omitted=group_fold if crossfit else pool[(pool.index(group_fold)+1)%len(pool)]
    return head_name(([outer] if outer is not None else [])+[omitted])


def head_exclusions(name):
    return [] if name=='full' else [int(v) for v in name.removeprefix('exclude-').split('-')]


def selected_head(outer,group_fold,crossfit):
    return head_name([outer]) if outer is not None and outer==group_fold else training_head(outer,group_fold,crossfit)


def selector_features(raw_context,candidate_features):
    if raw_context.shape[-1]!=648:raise ValueError('Selector requires deterministic features,not learned state/code')
    return torch.cat((raw_context,torch.as_tensor(candidate_features,dtype=raw_context.dtype)),-1)
