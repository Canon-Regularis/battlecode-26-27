"""One movement executor, with optional causal goal geometry and utility."""
import torch
from torch import nn
from .goal_execution import local_features,goal_geometry


def optional_goal(current,route,chosen,score=0.):
    if chosen is None:return torch.zeros(9,9)
    geometry=goal_geometry(current,route,chosen['goal'],chosen['radius'])
    if geometry is None:raise ValueError('Selected goal has no current geometry')
    if not 0<float(score)<=1:raise ValueError('Selected utility must be positive and bounded')
    return torch.cat((geometry,torch.full((9,1),float(score))),-1)


class SharedGoalExecutor(nn.Module):
    def __init__(self,conditioned=True):
        super().__init__();self.conditioned=conditioned;self.layers=nn.Sequential(nn.Linear(137,64),nn.Tanh(),nn.Linear(64,1))
        nn.init.zeros_(self.layers[-1].weight);nn.init.zeros_(self.layers[-1].bias)

    def forward(self,context,goal,baseline):
        # Unavailable means no goal information, even if a caller supplies stale fields.
        goal=goal*goal[...,7:8] if self.conditioned else torch.zeros_like(goal)
        return baseline+self.layers(torch.cat((local_features(context),goal),-1)).squeeze(-1)
