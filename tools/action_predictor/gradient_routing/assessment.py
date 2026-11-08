"""Fixed fitting-only allocation guards; no favorable checkpoint selection."""
import numpy as np
from ..history_horizon.engine import infer, selectors
from ..history_horizon.assessment import summarize, paired
from ..movement_diagnosis.audit import forecast, measures, decomposition
from ..observation_metrics import correctness


def evaluate(model,data,directory,label):
    prediction = infer(model,data,'A',decode=True)
    movement = forecast(model,data);ids=movement['ids'];raw=data['arrays'];gold=raw['py'][ids]
    if not np.array_equal(movement['observed_nll'],prediction['nll'][ids]):raise ValueError('Observed loss parity failed')
    if not np.array_equal(movement['move_logp'].argmax(1),prediction['coordinate'][ids]):raise ValueError('Decoder parity failed')
    for name in ('move_coordinate_nll','move_group_nll','move_within_group_nll'):
        prediction[name]=np.full(len(raw['y']),np.nan)
    prediction['move_coordinate_nll'][ids]=-movement['move_logp'][np.arange(len(ids)),gold]
    last=raw['grid'][ids,:,18];safe=(last.max(1)>0)&(gold>=0)&(gold<289)
    required=np.isin(raw['direction'][ids],(2,3))
    if not np.all(safe[required]):raise ValueError('Known movement strata require a previous tile')
    detail=decomposition(movement['move_logp'][safe],gold[safe],last[safe].argmax(1))
    prediction['move_group_nll'][ids[safe]]=detail['group_nll']
    prediction['move_within_group_nll'][ids[safe]]=detail['within_group_nll']
    np.savez_compressed(directory/f'{label}-predictions.npz',**prediction)
    np.savez_compressed(directory/f'{label}-movement.npz',**movement)
    return prediction,dict(commands=summarize(data,prediction),
        movement=measures(raw,ids,movement['move_logp'],movement['type_logp']))


def comparison(data,treatment,control):
    previous=paired(data,treatment,control);metrics=previous['metrics'];raw=data['arrays']
    change=(raw['y']==8)&(raw['direction']==3);groups=np.unique(data['group'])
    coordinate_delta=treatment['move_coordinate_nll']-control['move_coordinate_nll']
    within_delta=treatment['move_within_group_nll']-control['move_within_group_nll']
    _,tj=correctness(raw,treatment);_,cj=correctness(raw,control)
    complete_delta=tj.astype(float)-cj
    per_group={};loo_nll=[];loo_accuracy=[]
    for g in groups:
        mask=data['group']==g;selected=mask&change;other=change&~mask
        per_group[str(g)]=dict(rows=int(mask.sum()),changes=int(selected.sum()),
            complete_command_delta=float(complete_delta[mask].mean()),
            complete_change_delta=float(complete_delta[selected].mean()) if selected.any() else None,
            change_coordinate_nll_delta=float(coordinate_delta[selected].mean()) if selected.any() else None)
        if other.any():
            loo_nll.append(float(coordinate_delta[other].mean()))
            loo_accuracy.append(float(complete_delta[other].mean()))
    nonmove=raw['y']!=8
    false_positive_delta=float(((treatment['prediction'][nonmove]==8).astype(float)-(control['prediction'][nonmove]==8)).mean()) if nonmove.any() else None
    delta=float(coordinate_delta[change].mean());within=float(within_delta[change].mean())
    macro_delta=summarize(data,treatment)['macro_F1']-summarize(data,control)['macro_F1']
    checks=dict(complete_change_gain=metrics['change_complete']['delta']>=.05,
        complete_movement_gain=metrics['move_complete']['delta']>=.01,
        continuation=metrics['continue_complete']['delta']>=-.005,
        change_coordinate_nll=delta<=-.15,within_alternative_nll=within<=-.05,
        balanced_joint_nll=selectors(data,treatment)['movement']<selectors(data,control)['movement'],
        full_nll=metrics['all_nll']['delta']<=.005,
        complete_commands=metrics['all_complete']['delta']>=-.002,macro_F1=macro_delta>=-.01,
        movement_false_positives=false_positive_delta is not None and false_positive_delta<=.002,
        change_nll_leave_one_group_out=len(loo_nll)==len(groups) and all(v<0 for v in loo_nll),
        change_accuracy_leave_one_group_out=len(loo_accuracy)==len(groups) and all(v>0 for v in loo_accuracy))
    for family in ('attack','cast_0','cast_1'):
        for kind in ('conditional','complete'):
            d=metrics[family+'_'+kind]['delta'];checks[family+'_'+kind]=d is not None and d>=-.02
    return dict(metrics=metrics,windows=previous['windows'],per_group=per_group,
        change_coordinate_nll_delta=delta,change_within_alternative_nll_delta=within,
        macro_F1_delta=macro_delta,movement_false_positive_rate_delta=false_positive_delta,
        change_coordinate_nll_leave_one_group_out=loo_nll,change_accuracy_leave_one_group_out=loo_accuracy,
        allocation_checks=checks,all_checks_pass=all(checks.values()),
        limitations='Fitting-only pre-exposed groups. Passing allocates a separately reviewed transfer experiment, not promotion, generalization or strategy. No gradient statistic overrides behavioral guards.')
