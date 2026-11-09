"""Exact causal priority inputs, shared by extraction and offline inference."""
from collections import deque
import numpy as np
from .audit import cursor

FIELDS=('current','current_available','scheduled','scheduled_available','last_argument','last_available','last_round_gap')

class PriorityMemory:
    """Per game/actor; observe EVERY actual own action, never a forecast.

    The current own-priority dictionary must come from personal PRE. Missing
    values use explicit masks; signed integer arguments are never clipped.
    """
    def __init__(self,actor):
        self.actor=actor;self.history=deque(maxlen=16);self.last=None;self.at=None;self.round=None

    def observe(self,step,event,round_number):
        if step['actor']!={'kind':1,'index':self.actor}:raise ValueError('Mixed actor')
        at=cursor(event)
        if self.at is not None and at<=self.at:raise ValueError('Nonconsecutive ordered own-action stream required')
        if self.round is not None and round_number<self.round:raise ValueError('Round went backwards')
        available=step['kind']==9
        value=step['priority'] if available else 0
        if not isinstance(value,int) or isinstance(value,bool):raise ValueError('Exact integer required')
        self.history.append((value,int(available)))
        if available:self.last=(value,round_number)
        self.at=at;self.round=round_number

    def inputs(self,own_priority,pre,round_number):
        if self.at is not None and self.at>cursor(pre):raise ValueError('Future action input')
        if self.round is not None and round_number<self.round:raise ValueError('Current round before history')
        values=[]
        for key in ('current','scheduled'):
            value=own_priority.get(key)
            if value is not None and (not isinstance(value,int) or isinstance(value,bool)):raise ValueError('Exact integer required')
            values.extend((value if value is not None else 0,int(value is not None)))
        values.extend((self.last[0],1,round_number-self.last[1]) if self.last else (0,0,0))
        history=np.zeros((16,2),dtype=np.int64)
        if self.history:history[-len(self.history):]=list(self.history)
        return np.asarray(values,dtype=np.int64),history
