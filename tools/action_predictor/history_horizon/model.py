"""Fresh direct recurrent policy; same parameters for all horizon arms."""
import torch
from torch import nn
from ..reliable_model import JointModel, priority_log_mass
from ..segment_policy.history_model import encode_command
from ..segment_policy.model import SPATIAL


class Policy(nn.Module):
    def __init__(self):
        super().__init__()
        self.execution = JointModel(253,24,15,dict(history=16,spatial=True,constrain=True))
        self.observation = nn.Sequential(nn.Linear(253,16),nn.Tanh())
        self.observation_history = nn.GRU(45,32,batch_first=True)
        self.history_projection = nn.Linear(32,128)
        self.priority_projection = nn.Linear(3,128)
        self.memory = nn.GRUCell(149,28)
        self.memory_projection = nn.Linear(28,128)
        for layer in (self.history_projection,self.priority_projection):
            nn.init.zeros_(layer.weight);nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.memory_projection.bias)

    def empty(self,n):
        return dict(hidden=torch.zeros(n,28),age=torch.zeros(n,dtype=torch.long))

    def begin(self,x,history,observations,history_gaps,priority_inputs,root_gap,actor_start,state,reset8):
        _,base=self.execution(x,history)
        encoded=self.observation(observations)*history_gaps[:,:,1:2]
        _,h=self.observation_history(torch.cat((history,encoded,history_gaps),-1))
        p=priority_inputs.double()
        previous=torch.stack((torch.asinh(p[:,4]/100)*p[:,5],p[:,5],torch.log1p(p[:,6])/8),-1).float()
        base=base+self.history_projection(h[-1])+self.priority_projection(previous)
        reset=actor_start | (root_gap!=1)
        if reset8: reset=reset | (state['age']>=8)
        hidden=torch.where(reset[:,None],torch.zeros_like(state['hidden']),state['hidden'])
        age=torch.where(reset,torch.zeros_like(state['age']),state['age'])
        return dict(base=base,context=base+self.memory_projection(hidden),hidden=hidden,age=age,reset=reset)

    def spatial(self,step,grid,valid,rules,family):
        return self.execution.parameter_logits(step['context'],grid,valid,family,rules).double().log_softmax(-1)

    def observed(self,step,grid,valid,rules,y,py,priority):
        typ=self.execution.action(step['context']).double().log_softmax(-1)
        lp=typ[torch.arange(len(y)),y]
        mask=torch.isin(y,torch.tensor(SPATIAL))
        if mask.any():
            sub=dict(context=step['context'][mask])
            parameter=self.spatial(sub,grid[mask],valid[mask],rules[mask],y[mask])
            lp=lp.clone();lp[mask]+=parameter[torch.arange(int(mask.sum())),py[mask]]
        integer=y==9
        if integer.any():
            lp=lp.clone();lp[integer]+=priority_log_mass(self.execution.priority(step['context'][integer]).double(),priority[integer].double())
        hidden=self.memory(torch.cat((step['base'],encode_command(y,py,priority)),-1),step['hidden'])
        return -lp,dict(hidden=hidden,age=step['age']+1)

    def decode(self,step,grid,valid,rules):
        typ=self.execution.action(step['context']).double().log_softmax(-1)
        joint=typ.clone();coordinates=torch.full_like(typ,-1,dtype=torch.long)
        parameters={}
        for family in SPATIAL:
            lp=self.spatial(step,grid,valid,rules,torch.full((len(typ),),family,dtype=torch.long))
            parameters[family]=lp
            score,coordinates[:,family]=lp.max(-1);joint[:,family]+=score
        raw=self.execution.priority(step['context']).double()
        integer=(raw[:,0]*100).round().long()
        joint[:,9]+=priority_log_mass(raw,integer.double())
        prediction=joint.argmax(-1)
        return dict(prediction=prediction,proposed_coordinate=coordinates[torch.arange(len(typ)),prediction],
            priority=integer,family_coordinates=coordinates,type_logp=typ,parameter_logp=parameters,
            family_mode_logp=joint)
