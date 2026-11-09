"""Goal features that describe local direction/progress without absolute range."""
import torch
from .model import OFFSETS
from .goal_execution import GoalExecutor


def bounded_goal(goal):
    dx,dy=goal[...,0],goal[...,1];length=torch.sqrt(dx.square()+dy.square()).clamp_min(1e-8);ux,uy=dx/length,dy/length
    offsets=torch.tensor(OFFSETS,dtype=goal.dtype,device=goal.device);step_length=offsets.square().sum(-1).sqrt().clamp_min(1.)
    alignment=ux*(offsets[:,0]/step_length)+uy*(offsets[:,1]/step_length)
    geometric_progress=((torch.maximum(dx.abs(),dy.abs())-goal[...,2])*32).clamp(-1,1)
    result=torch.stack((ux,uy,geometric_progress,goal[...,5],(goal[...,4]==0).to(goal.dtype),(goal[...,3]==0).to(goal.dtype),alignment.clamp(-1,1),goal[...,7]),-1)
    return result*goal[...,7,None]


class BoundedGoalExecutor(GoalExecutor):
    def forward(self,context,goal,baseline):return super().forward(context,bounded_goal(goal),baseline)
