"""Frozen-weight TRAIN pathway dependence; no fitting or policy-quality claim."""
import json
from collections import Counter
import numpy as np
import torch
import torch.nn.functional as F
from tools.action_predictor.learned_policy.sequence_data import ROOT, BASE, WORK, REPORT, JOBS
from tools.action_predictor.learned_policy.model import GoalPolicy, SPATIAL
from tools.action_predictor.learned_policy.data import load, causal_inputs, geometry, targets
from tools.action_predictor.learned_policy.retention_gradients import fingerprint
from tools.action_predictor.priority_fit_v3 import load_base
from tools.action_predictor.audit import immutable_json
from tools.action_predictor.data import digest

LOCAL=ROOT/'.cambc/action-predictor/v17'
VARIANTS=('geometry_off','uncertainty_availability_off','all_variables_off','bias_off','full_projection_off')


def command(p):
    family=int(p['prediction'][0])
    argument=int(p['coordinate'][0]) if family in SPATIAL else int(p['priority'][0]) if family==9 else None
    return family,argument


@torch.no_grad()
def run():
    plan=dict(id='Q00-frozen-TRAIN-goal-pathways',models=['L01','L02'],
        selection='Same twelve distinct TRAIN groups, six per engine, as the already fixed retention-gradient cohort. First actor/first64 selected nodes; first16 known-position, noninitial decisions after8 prefix nodes. No action label, future-target availability or correctness condition in selection.',
        treatments=list(VARIANTS),
        treatment='Subtract only specified linear goal_condition contributions from the current conditioned context. Keep all other goal paths. Original causal baseline filter always advances after the actual command; counterfactual readouts never update future state. Frozen-weight/fixed-state sensitivity, not a causally refiltered policy.',
        measurements='Semantic mode changes in observed command representation; type changes; TV of15-way type probabilities and conditional move291-bucket distribution; conditional move mode changes; context perturbation norms; archived baseline semantic-command parity. No accuracy ranking, threshold/checkpoint/seed selection or architecture change.',
        interpretation='Functional dependence is not usefulness, Fish intent, observation sufficiency or achieved deployable accuracy. All TRAIN only, bounded early streams, fixed selected weights.',
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0)
    immutable_json(LOCAL/'Q00-plan.json',plan)
    torch.set_num_threads(2); teacher,saved=load_base(); d=load('train',saved)
    chosen=json.loads((REPORT/'L01-retention-gradients.json').read_text())['selected_groups']
    jobs={j['record']['raw_sha256']:j for j in json.loads(JOBS.read_text()) if j['split']=='train'}
    streams=[]
    for entry in chosen:
        job=jobs[entry['raw']]
        stream=next(s for s in d['sequences'] if job['offset']<=s[0]<job['offset']+job['rows'])[:64]
        streams.append((entry,stream))
    assert len({entry['group'] for entry,_ in streams})==12
    summaries={}; all_records={}; bindings={}
    for identifier in ('L01','L02'):
        info=json.loads((REPORT/f'{identifier}.json').read_text())
        path=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
        assert digest(path)==info['checkpoint_sha256']
        model=GoalPolicy(teacher,True);model.load_state_dict(torch.load(path,weights_only=False)['state']);model.eval()
        before=fingerprint(model)
        with np.load(WORK/f'runs/{identifier}/train-predictions.npz') as z:
            archived={k:z[k] for k in ('prediction','proposed_coordinate','priority')}
        records=[]; baseline_mismatches=[]; types=Counter()
        for entry,stream in streams:
            state=model.empty(1);probes=0
            for at,row in enumerate(stream):
                ix=np.array([row]);inputs=causal_inputs(d,ix);geo=geometry(d,ix)
                step=model.begin(**inputs,state=state)
                eligible=at>=8 and probes<16 and bool(inputs['position_known'][0]) and not bool(inputs['transition_gap'][0,2]>.5)
                if eligible:
                    kwargs=dict(**geo,priority_mode=torch.from_numpy(d['priority_mode'][ix]),priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ix]))
                    baseline=model.decode(step,**kwargs);original=command(baseline)
                    af=int(archived['prediction'][row]);aa=int(archived['proposed_coordinate'][row]) if af in SPATIAL else int(archived['priority'][row]) if af==9 else None
                    if original!=(af,aa):baseline_mismatches.append(int(row))
                    relative=(step['world']-inputs['position'][:,None])*inputs['position_known'][:,None,None]
                    usable=step['known']&inputs['position_known'][:,None]
                    metadata=torch.cat((step['logscale'],usable[:,:,None].float()),-1)
                    w=model.goal_condition.weight
                    g=F.linear(relative,w[:,:2]);u=F.linear(metadata,w[:,2:]);b=model.goal_condition.bias[None,None].expand_as(g)
                    changes=dict(geometry_off=g,uncertainty_availability_off=u,all_variables_off=g+u,bias_off=b,full_projection_off=g+u+b)
                    row_record=dict(row=int(row),group=entry['group'],engine=entry['engine'],baseline=list(original),variants={})
                    for name,delta in changes.items():
                        alternative=model.decode(dict(step,context=step['context']-delta),**kwargs)
                        new_command=command(alternative)
                        def tv(a,b):return float((.5*(a.double().exp()-b.double().exp()).abs().sum(-1))[0])
                        row_record['variants'][name]=dict(command=list(new_command),semantic_mode_changed=new_command!=original,
                            type_changed=new_command[0]!=original[0],
                            type_TV=tv(baseline['type_logp'],alternative['type_logp']),
                            conditional_move_TV=tv(baseline['parameter_logp'][8],alternative['parameter_logp'][8]),
                            conditional_move_mode_changed=int(baseline['parameter_logp'][8].argmax(-1)[0])!=int(alternative['parameter_logp'][8].argmax(-1)[0]),
                            context_delta_norm=float(delta.norm(dim=-1).mean()))
                    records.append(row_record);probes+=1;types[original[0]]+=1
                target=targets(d,ix)
                _,post=model.observed(step,**geo,**{k:target[k] for k in ('y','py','priority_parameter_nll')})
                state=post
            assert probes==16,(identifier,entry['group'],probes)
        assert fingerprint(model)==before
        def stats(values):
            a=np.asarray(values,float);return dict(mean=float(a.mean()),quantiles=np.quantile(a,[0,.5,.9,.99,1]).tolist())
        summaries[identifier]=dict(rows=len(records),groups=len({r['group'] for r in records}),predicted_types=dict(types),
            archived_semantic_mode_mismatches=baseline_mismatches,weights_unchanged=True,
            variants={name:dict(semantic_mode_changes=sum(r['variants'][name]['semantic_mode_changed'] for r in records),
                type_changes=sum(r['variants'][name]['type_changed'] for r in records),
                conditional_move_mode_changes=sum(r['variants'][name]['conditional_move_mode_changed'] for r in records),
                type_TV=stats([r['variants'][name]['type_TV'] for r in records]),
                conditional_move_TV=stats([r['variants'][name]['conditional_move_TV'] for r in records]),
                context_delta_norm=stats([r['variants'][name]['context_delta_norm'] for r in records])) for name in VARIANTS})
        all_records[identifier]=records;bindings[identifier]=dict(checkpoint_sha256=digest(path),forecast_sha256=digest(WORK/f'runs/{identifier}/train-predictions.npz'))
        print(identifier,json.dumps(summaries[identifier]),flush=True)
    immutable_json(LOCAL/'Q00-records.json',all_records)
    immutable_json(LOCAL/'Q00-result.json',dict(results=summaries,bindings=bindings,plan_sha256=digest(LOCAL/'Q00-plan.json'),
        records_sha256=digest(LOCAL/'Q00-records.json'),input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0))


if __name__=='__main__':run()
