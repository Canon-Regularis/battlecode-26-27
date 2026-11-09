"""Frozen P05 plus a shared signed correction on every point component."""
import copy
import torch
from torch import nn

RELATIONS=tuple((role,time,sign,offset,changed_only)
    for changed_only in (False,True) for role in (0,1) for time in (0,1)
    for sign in (-1,1) for offset in (-1,0,1))
OWN_NAMES=tuple(f'own_{source}_sign{sign}_offset{offset}'
    for source in ('current','scheduled','latest','history16') for sign in (-1,1) for offset in (-1,0,1))
OTHER_NAMES=tuple(f"{'changed_' if changed else ''}{('ally','enemy')[role]}_"
    f"{('current','scheduled')[time]}_sign{sign}_offset{offset}"
    for role,time,sign,offset,changed in RELATIONS)
NAMES=OWN_NAMES+OTHER_NAMES


def own_features(points,values,history):
    if points.dtype!=torch.int64 or values.dtype!=torch.int64 or history.dtype!=torch.int64:
        raise TypeError('Exact int64 point/own inputs required')
    if values.shape!=(len(points),7) or history.shape!=(len(points),16,2):
        raise ValueError('Own-priority input shape changed')
    flags=torch.cat((values[:,[1,3,5]],history[:,:,1]),1)
    if not bool(((flags==0)|(flags==1)).all()):raise ValueError('Invalid own availability mask')
    sources=[(values[:,i,None],values[:,i+1,None].bool()) for i in (0,2,4)]
    sources.append((history[:,:,0],history[:,:,1].bool()))
    columns=[]
    for value,available in sources:
        value=torch.where(available,value,torch.zeros_like(value))
        if bool(((value<-(2**31))|(value>=2**31)).any()):raise ValueError('Own priority outside signed int32 input domain')
        for sign in (-1,1):
            for offset in (-1,0,1):
                columns.append(((points[:,:,None]==(sign*value+offset)[:,None])&available[:,None]).any(-1))
    return torch.stack(columns,-1)


def other_features(points,priorities,available,roles):
    if points.dtype!=torch.int64 or priorities.dtype!=torch.int64:
        raise TypeError('Exact int64 point/other inputs required')
    if priorities.ndim!=3 or priorities.shape[0]!=len(points) or priorities.shape[2]!=2:
        raise ValueError('Other-priority shape changed')
    if available.shape!=priorities.shape or available.dtype!=torch.bool or roles.shape!=priorities.shape[:2]:
        raise ValueError('Other availability/role shape changed')
    if roles.dtype not in (torch.int8,torch.int16,torch.int32,torch.int64):raise TypeError('Integer roles required')
    if bool((available.any(-1)&~((roles==0)|(roles==1))).any()):raise ValueError('Available unit lacks known role')
    clean=torch.where(available,priorities,torch.zeros_like(priorities))
    if bool(((clean<-(2**31))|(clean>=2**31)).any()):raise ValueError('Other priority outside signed int32 input domain')
    changed=available.all(-1)&(clean[:,:,0]!=clean[:,:,1])
    columns=[]
    for role,time,sign,offset,changed_only in RELATIONS:
        value=sign*clean[:,:,time]+offset
        valid=available[:,:,time]&(roles==role)&(value>=-(2**31))&(value<2**31)
        if changed_only:valid=valid&changed
        columns.append(((points[:,:,None]==value[:,None])&valid[:,None]).any(-1))
    return torch.stack(columns,-1)


class SignedPointCorrection(nn.Module):
    """Correct point logits before the original normalized mixture arithmetic.

    Same-value absolute/residual explanations receive the same correction.
    Fallback logit and logistic parameters retain their original raw values;
    the mixture is then normalized jointly by the unchanged P05 methods.
    """
    def __init__(self,base,active=None):
        super().__init__()
        self.base=copy.deepcopy(base).requires_grad_(False).eval()
        active=torch.ones(len(NAMES),dtype=torch.bool) if active is None else torch.as_tensor(active,dtype=torch.bool)
        if active.shape!=(len(NAMES),) or not bool(active.any()):raise ValueError('Empty/invalid common feature mask')
        self.register_buffer('active',active.clone())
        self.weights=nn.Parameter(torch.zeros(int(active.sum()),dtype=base.linear.weight.dtype))

    @property
    def absolute(self):return self.base.absolute
    @property
    def residual(self):return self.base.residual
    @property
    def point_count(self):return len(self.absolute)+len(self.residual)

    def features(self,points,values,history,priorities,available,roles):
        result=torch.cat((own_features(points,values,history),other_features(points,priorities,available,roles)),-1)
        result[:,len(self.absolute):]&=values[:,5,None,None].bool()
        return result

    def correct_logits(self,raw,features):
        if raw.ndim!=2 or raw.shape[1]!=self.point_count+3:
            raise ValueError('Raw P05 interface changed')
        if features.dtype!=torch.bool or features.shape!=(len(raw),self.point_count,len(NAMES)):
            raise ValueError('All-point exact-relation interface changed')
        correction=features[:,:,self.active].to(raw.dtype)@self.weights
        return torch.cat((raw[:,:self.point_count]+correction,raw[:,self.point_count:]),-1)

    def forward(self,context,extra,values,history,priorities,available,roles):
        with torch.no_grad():
            raw=self.base(context,extra)
            points,_=self.base.components(raw,values)
        features=self.features(points,values,history,priorities,available,roles)
        return self.correct_logits(raw,features)

    def components(self,raw,values):return self.base.components(raw,values)
    def log_mass(self,raw,target,values):return self.base.log_mass(raw,target,values)
    def candidate_log_masses(self,raw,values):return self.base.candidate_log_masses(raw,values)
    def integer(self,raw,values):return self.base.integer(raw,values)
