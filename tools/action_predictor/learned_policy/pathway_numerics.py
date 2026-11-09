"""Independent float64 mixture arithmetic; primary float32 forecasts unchanged."""
import torch


def conditional64(model,step,heads,family):
    """Normalize component probabilities in double and marginalize stably.

    This checks arithmetic on the frozen component outputs. It is not a new
    decoder and does not overwrite the primary model's probabilities or state.
    """
    prior=step['logprior'].double().log_softmax(-1)
    types=model.types(step).double().log_softmax(-1)
    joint_weight=prior+types[:,:,family]
    type_mass=torch.logsumexp(joint_weight,1)
    weight=joint_weight.log_softmax(-1)
    normalized_heads=heads.double().log_softmax(-1)
    lp=torch.logsumexp(weight[:,:,None]+normalized_heads,1)
    return lp,type_mass


def empty_checks():
    return dict(max_sum_error_all_batch_rows=0.,max_sum_error_valid_decisions=0.,
        max_conditional64_sum_error=0.,max_conditional_probability_TV=0.,
        conditional_mode_mismatches_valid=0,conditional_rows_checked=0,
        max_observed_family_nll_difference=0.,observed_family_rows_checked=0)


def observe_sum(check,worst,kind,value,valid,ids,step,geo,p,target,loss,d,ix):
    error=(value.double().exp().sum(-1)-1).abs()
    allmax=float(error.max());check['max_sum_error_all_batch_rows']=max(check['max_sum_error_all_batch_rows'],allmax)
    real=error[valid]
    if not len(real):return
    check['max_sum_error_valid_decisions']=max(check['max_sum_error_valid_decisions'],float(real.max()))
    for scope,m in [('all',torch.ones_like(error,dtype=torch.bool)),('valid',torch.as_tensor(valid))]:
        at=int(error.masked_fill(~m,-1).argmax());v=float(error[at])
        if scope in worst and worst[scope]['error']>=v:continue
        worst[scope]=dict(error=v,kind=kind,at=at,at_valid=bool(valid[at]),
            rows=ids.copy(),valid=valid.copy(),step={k:t.detach().clone() for k,t in step.items()},
            geometry={k:t.detach().clone() for k,t in geo.items()},
            primary={k:p[k].detach().clone() for k in ('prediction','coordinate','priority','type_logp')},
            reported_log_probability=value.detach().clone(),
            target={k:t.detach().clone() for k,t in target.items()},primary_nll=loss.detach().clone(),
            priority_mode=torch.from_numpy(d['priority_mode'][ix].copy()),
            priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ix].copy()))


def observe_conditional(check,exact,type_mass,reported,target,loss,valid,family):
    mask=torch.as_tensor(valid);count=int(mask.sum())
    if not count:return
    check['max_conditional64_sum_error']=max(check['max_conditional64_sum_error'],float((exact[mask].exp().sum(-1)-1).abs().max()))
    check['max_conditional_probability_TV']=max(check['max_conditional_probability_TV'],float((.5*(exact[mask].exp()-reported[mask].double().exp()).abs().sum(-1)).max()))
    check['conditional_mode_mismatches_valid']+=int((exact.argmax(-1)[mask]!=reported.argmax(-1)[mask]).sum())
    check['conditional_rows_checked']+=count
    selected=mask&(target['y']==family)
    if selected.any():
        py=target['py'][selected];lp=exact[selected]
        nll=-type_mass[selected]-lp[torch.arange(len(py)),py]
        check['max_observed_family_nll_difference']=max(check['max_observed_family_nll_difference'],float((nll-loss[selected].double()).abs().max()))
        check['observed_family_rows_checked']+=int(selected.sum())
