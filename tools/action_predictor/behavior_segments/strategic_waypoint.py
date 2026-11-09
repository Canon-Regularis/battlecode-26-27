"""Eight-own-turn waypoint supervision; future observations are labels only."""
import torch
from torch import nn
from .model import OFFSETS
from ..algorithmic.library import field
from ..goal_position.model import goal_guided_move


def position(step):
    if not step['observed']:return None
    p=step['input']['observation']['own'].get('position')
    return None if p is None else (p['x'],p['y'])


def labels(window,history,horizon=8):
    result=[]
    for i in range(len(window['steps'])-horizon):
        origin=position(window['steps'][i]);target=position(window['steps'][i+horizon])
        if origin is None or target is None:continue
        expected=list(origin);valid=True
        for j in range(i+1,i+horizon+1):
            for dx,dy in history[j]:expected[0]+=dx;expected[1]+=dy
            observed=position(window['steps'][j])
            if window['steps'][j]['observed'] and (observed is None or tuple(expected)!=observed):valid=False;break
        if valid:result.append(dict(position=i,origin=list(origin),goal=list(target),offset=[target[0]-origin[0],target[1]-origin[1]]))
    return result


def features(states,probabilities,geometry,heading,commands):
    return torch.cat((states,probabilities,geometry.flatten(-2),heading.flatten(-2),commands.flatten(-2)),-1)


class WaypointHead(nn.Module):
    def __init__(self):
        super().__init__();self.layers=nn.Sequential(nn.Linear(704,128),nn.Tanh(),nn.Linear(128,2))
        nn.init.zeros_(self.layers[-1].weight);nn.init.zeros_(self.layers[-1].bias)

    def forward(self,x):return self.layers(x)*8


def reachable_goal(origin,offset,route):
    distances=field(route['width'],route['height'],tuple(route['blocked']),tuple(origin),0)
    x,y=origin[0]+float(offset[0]),origin[1]+float(offset[1]);width=route['width']
    valid=[i for i,d in enumerate(distances) if d<10000]
    return min(((i%width,i//width) for i in valid),key=lambda p:((p[0]-x)**2+(p[1]-y)**2,p[1],p[0]))


def route_move(current,route,goal,fallback):
    move=goal_guided_move(route,current,goal)
    return fallback if move is None else move


def commitment(origin,proposal,state=None):
    if origin is None:return None,None
    if state is None or state['remaining']<=0 or tuple(state['goal'])==tuple(origin):
        state=dict(goal=list(proposal),remaining=8)
    return tuple(state['goal']),dict(goal=state['goal'],remaining=state['remaining']-1)
