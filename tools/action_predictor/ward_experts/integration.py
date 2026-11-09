"""Normalized expert replacement; fixed hierarchical and secondary joint MAP."""
import numpy as np
import torch
import torch.nn.functional as F

def type_distribution(old,ward_logit):
    if ward_logit is None:return old.double()
    old=old.double();other=torch.ones(old.shape[1],dtype=torch.bool);other[14]=False;out=torch.empty_like(old);out[:,14]=F.logsigmoid(ward_logit.double());out[:,other]=old[:,other]-torch.logsumexp(old[:,other],-1)[:,None]+F.logsigmoid(-ward_logit.double())[:,None];return out

def loss_overlay(base_nll,old_type,new_type,y,old_ward_parameter=None,new_ward_parameter=None):
    i=torch.arange(len(y));nll=base_nll.double()+old_type[i,y]-new_type[i,y]
    if new_ward_parameter is not None:
        ward=y==14;nll[ward]+=old_ward_parameter[ward]-new_ward_parameter[ward]
    return nll

def commands(types,old_types,modes,mode_joint,ward_coordinate=None,ward_lp=None):
    modes=np.array(modes,copy=True);conditional=np.array(mode_joint)-np.array(old_types)
    if ward_coordinate is not None:modes[:,14,1]=ward_coordinate;conditional[:,14]=ward_lp
    t=np.asarray(types);primary=t.argmax(-1);secondary=(t+conditional).argmax(-1);rows=np.arange(len(t));a=modes[rows,primary];b=modes[rows,secondary]
    pack=lambda c,y:dict(prediction=c[:,0],coordinate=c[:,1],priority=c[:,2],command_log_probability=t[rows,y]+conditional[rows,y],family_commands=modes)
    return pack(a,primary),pack(b,secondary)
