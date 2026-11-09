"""In-sample diagnostics and prospectively specified allocation gates only."""
import numpy as np
from ..history_horizon.engine import infer,selectors
from ..history_horizon.assessment import summarize,paired
from ..movement_diagnosis.audit import forecast,measures
from ..observation_metrics import correctness


def evaluate(model,data,directory,label):
    prediction=infer(model,data,'A',decode=True)
    movement=forecast(model,data);ids=movement['ids'];gold=data['arrays']['py'][ids]
    if not np.array_equal(movement['observed_nll'],prediction['nll'][ids]):raise ValueError('Observed loss parity failed')
    if not np.array_equal(movement['move_logp'].argmax(1),prediction['coordinate'][ids]):raise ValueError('Decoder parity failed')
    coordinate_nll=-movement['move_logp'][np.arange(len(ids)),gold]
    prediction['move_coordinate_nll']=np.full(len(prediction['nll']),np.nan)
    prediction['move_coordinate_nll'][ids]=coordinate_nll
    np.savez_compressed(directory/f'{label}-predictions.npz',**prediction)
    np.savez_compressed(directory/f'{label}-movement.npz',**movement)
    return prediction,dict(commands=summarize(data,prediction),
        movement=measures(data['arrays'],ids,movement['move_logp'],movement['type_logp']))


def comparison(data,treatment,control):
    previous=paired(data,treatment,control);metrics=previous['metrics'];raw=data['arrays']
    change=(raw['y']==8)&(raw['direction']==3);groups=np.unique(data['group'])
    coordinate_delta=treatment['move_coordinate_nll']-control['move_coordinate_nll']
    total=float(coordinate_delta[change].sum());count=int(change.sum());per_group={};loo=[]
    _,tj=correctness(raw,treatment);_,cj=correctness(raw,control)
    for g in groups:
        mask=data['group']==g;selected=mask&change;n=int(selected.sum());s=float(coordinate_delta[selected].sum())
        per_group[str(g)]=dict(rows=int(mask.sum()),changes=n,
            complete_command_delta=float(tj[mask].mean()-cj[mask].mean()),
            complete_change_delta=float(tj[selected].mean()-cj[selected].mean()) if n else None,
            change_coordinate_nll_delta=s/n if n else None)
        if count>n:loo.append((total-s)/(count-n))
    delta=total/count
    checks=dict(complete_change_gain=metrics['change_complete']['delta']>=.05,
        change_coordinate_nll=delta<=-.15,
        balanced_joint_nll=selectors(data,treatment)['movement']<selectors(data,control)['movement'],
        continuation=metrics['continue_complete']['delta']>=-.01,
        full_nll=metrics['all_nll']['delta']<=.005,
        complete_commands=metrics['all_complete']['delta']>=-.002,
        change_nll_leave_one_group_out=len(loo)==len(groups) and all(v<0 for v in loo))
    return dict(metrics=metrics,windows=previous['windows'],per_group=per_group,
        change_coordinate_nll_delta=delta,change_coordinate_nll_leave_one_group_out=loo,
        allocation_checks=checks,all_checks_pass=all(checks.values()),
        limitations='Fitting-only, exposed subset. Bootstrap/window statistics are descriptive, not generalization evidence. Passing only allocates a separately reviewed full-population experiment; no promotion.')
