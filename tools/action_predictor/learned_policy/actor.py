"""Policy execution loop: decide, dispatch, then assimilate the actual result."""
import numpy as np
import torch
from .execution import Command
from .. import reliable_train as rt
from ..targets import OFFSETS

class PolicyActor:
    """One instance per champion/game, with no demonstration labels at deployment.

    The observation provider supplies current personal-PRE encoded inputs plus
    a frozen-P05 priority distribution captured at that SAME PRE. A native/live
    observation provider and model export are separate required shipping stages.
    """
    def __init__(self,model,actor_key):
        self.model=model.eval();self.actor_key=actor_key;self.state=model.empty(1);self.pending=None
    @torch.no_grad()
    def decide(self,inputs,geometry,priority_mode,priority_mode_logp,priority_log_mass=None,*,actor_key):
        if actor_key!=self.actor_key:raise ValueError('Do not mix game/actor state; identity is metadata, never a feature')
        if self.pending is not None:raise RuntimeError('Previous proposed command has not executed or been rejected')
        if len(inputs['x'])!=1:raise ValueError('One personal actor per instance')
        step=self.model.begin(**inputs,state=self.state);prediction=self.model.decode(step,**geometry,priority_mode=priority_mode,priority_mode_logp=priority_mode_logp);family=int(prediction['prediction'][0]);coordinate=int(prediction['coordinate'][0]);position=None
        if coordinate<289 and coordinate>=0 and bool(inputs['position_known'][0]):
            origin=np.rint(inputs['position'][0].numpy()*32).astype(int);offset=OFFSETS[coordinate];position=(int(origin[0]+offset[0]),int(origin[1]+offset[1]))
        if family==9 and priority_log_mass is None:raise ValueError('Capture priority likelihood at PRE before dispatch')
        command=Command(rt.LABELS[family],position=position,priority=int(priority_mode[0]) if family==9 else None);self.pending=dict(step=step,geometry=geometry,coordinate=coordinate,command=command,priority_log_mass=priority_log_mass);return command
    @torch.no_grad()
    def commit(self,execution):
        if self.pending is None or execution.requested!=self.pending['command']:raise ValueError('No matching executed proposal')
        # Crucially the returned outcome determines move vs blocked, not the
        # requested type. No future Fish action is available or required.
        family=rt.LABELS.index(execution.actual_action);priority_nll=0.
        if family==9:
            callback=self.pending['priority_log_mass']
            if callback is None:raise ValueError('Priority likelihood captured at PRE is required')
            priority_nll=-float(callback(execution.requested.priority))
        _,state=self.model.observed(self.pending['step'],**self.pending['geometry'],y=torch.tensor([family]),py=torch.tensor([self.pending['coordinate']]),priority_parameter_nll=torch.tensor([priority_nll]));self.state={k:v.detach() for k,v in state.items()};self.pending=None
    def reject(self):
        """No action occurred; do not pretend the forecast was an observation."""
        self.pending=None
    def act(self,inputs,geometry,priority_mode,priority_mode_logp,executor,compatible_targets=(),priority_log_mass=None,*,actor_key):
        command=self.decide(inputs,geometry,priority_mode,priority_mode_logp,priority_log_mass,actor_key=actor_key)
        try:result=executor.execute(command,compatible_targets)
        except Exception:
            self.reject();raise
        self.commit(result);return result
