"""Saved-output matched study, endpoint accounting and unchanged initialization."""
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files
from ..policy_action_readout.protocol import ROOT,OUT,LOCAL
from ..policy_action_readout.data import load


def run():
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.action_readout_analysis.matched_study',)))
    reports={};bindings={}
    for arm in ('AB00','AB01'):
        reports[arm],more=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+arm+'.json');bindings.update(more)
        _,more=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+arm+'-completion.json');bindings.update(more)
    a,b=reports['AB00'],reports['AB01'];r=b['results']['validation']['all']['overall'];o=a['results']['validation']['all']['overall']
    data,cohorts,plan,ready=load();init={arm:torch.load(LOCAL/f'runs/{arm}/initial-state.pt',map_location='cpu',weights_only=True) for arm in reports}
    checks=dict(initial_parameters_identical=all(torch.equal(v,init['AB01']['state'][k]) for k,v in init['AB00']['state'].items()),
        initial_optimizer_identical=init['AB00']['optimizer']==init['AB01']['optimizer'],initial_torch_rng_identical=torch.equal(init['AB00']['torch_rng'],init['AB01']['torch_rng']))
    common=min(len(a['trace']),len(b['trace']));checks['common_rounds']=common;checks['numpy_rng_states_identical']=True
    for round_number in range(1,common+1):
        p={arm:LOCAL/f'runs/{arm}/round-{round_number:02d}.pt' for arm in reports}
        states={arm:torch.load(path,map_location='cpu',weights_only=True) for arm,path in p.items()}
        if states['AB00']['numpy_rng']!=states['AB01']['numpy_rng']:checks['numpy_rng_states_identical']=False
        for path in p.values():bindings[str(path.relative_to(ROOT))]=digest(path)
    for arm in reports:
        path=LOCAL/f'runs/{arm}/initial-state.pt';bindings[str(path.relative_to(ROOT))]=digest(path)
    if not all(checks[k] for k in ('initial_parameters_identical','initial_optimizer_identical','initial_torch_rng_identical','numpy_rng_states_identical')):
        immutable_json(OUT/'AB-matched-initialization-failure.json',checks);raise RuntimeError('Matched initialization/order contract failed')
    categories={row['action']:row for row in r['per_category']};control={row['action']:row for row in o['per_category']}
    baseline={}
    y=data['validation']['targets']['y'];old=data['validation']['baseline'];_,joint=__import__('tools.action_predictor.observation_metrics',fromlist=['correctness']).correctness(data['validation']['targets'],old)
    for code,name in enumerate(__import__('tools.action_predictor.reliable_train',fromlist=['LABELS']).LABELS):
        m=y==code;baseline[name]=dict(support=int(m.sum()),joint_correct=int((m&joint).sum()),observed_NLL=float(old['nll'][m].mean()) if m.any() else None)
    gate=plan['exploratory_continuation'];priority=categories['priority'];base_priority=int((joint&(y==9)).sum())
    gates=dict(net_complete_vs_JP02=b['comparisons']['JP02']['overall']['rescues']-b['comparisons']['JP02']['overall']['regressions']>=gate['net_complete_gain_vs_JP02_minimum'],
        net_complete_vs_control=b['comparisons']['AB00']['overall']['rescues']-b['comparisons']['AB00']['overall']['regressions']>=gate['net_complete_gain_vs_control_minimum'],
        priority_joint_gain=priority['joint_correct']-base_priority>=gate['priority_joint_gain_vs_JP02_minimum'],
        priority_type_FP_guard=priority['type_FP']<=34+gate['priority_type_FP_increase_vs_JP02_maximum'],
        mean_NLL_below_both=r['joint_nll']<old['nll'].mean() and r['joint_nll']<o['joint_nll'],
        macro_F1_guard=r['macro_f1']>=.62004805600384-gate['macro_F1_decline_vs_JP02_maximum'])
    for family in ('move','recall','attack','cast_0','cast_1'):
        limit=gate['move_recall_joint_decline_maximum'] if family in ('move','recall') else gate['attack_cast_joint_decline_maximum']
        n=baseline[family]['support'];gates[family+'_guard']=(categories[family]['joint_correct']-baseline[family]['joint_correct'])/n>=-limit
    initialization_scope='Same initialization,optimizerandRNG; same deterministic row-orderprocedure verified on14commonrounds. Different selected/stoppingrounds are a consequence of the predeclared shared DEVrule, not equal completed updatecounts.'
    evidence=dict(checks=checks,initialization_scope=initialization_scope,exploratory_gate=gates,all_exploratory_conditions_pass=all(gates.values()),
        per_category={name:dict(support=categories[name]['support'],JP02_complete=baseline[name]['joint_correct'],AB00_complete=control[name]['joint_correct'],
            AB01_complete=categories[name]['joint_correct'],JP02_NLL=baseline[name]['observed_NLL'],AB00_NLL=control[name]['observed_joint_NLL'],AB01_NLL=categories[name]['observed_joint_NLL']) for name in categories},
        comparisons=b['comparisons'],sources=sources,bindings=bindings,new_fits=0,reserved_opened=0)
    immutable_json(OUT/'AB-matched-study.json',evidence)
    lines=['# Matched action-belief study: no demonstrated benefit','',
        '| Policy | Complete DEV /14,439 | Macro F1 | Observed joint NLL | Complete priority /576 |',
        '| --- | ---: | ---: | ---: | ---: |',
        '| JP02 frozen reference | 12,137 | 0.620048 | 0.629052 | 131 |',
        f"| AB00 shuffled training | {o['strict_correct']:,} | {o['macro_f1']:.6f} | {o['joint_nll']:.6f} | {control['priority']['joint_correct']} |",
        f"| AB01 real training | {r['strict_correct']:,} | {r['macro_f1']:.6f} | {r['joint_nll']:.6f} | {priority['joint_correct']} |",'',
        'AB01 ties the frozen reference through34rescues/34regressions. Against the shuffled control it loses7commands through15rescues/22regressions. Both paired accuracy intervals include zero, as do the paired NLL-difference intervals. This is a negative result for the named representation/readout/training comparison; it does not prove the inputs uninformative or observations insufficient.','',
        f"Selected/completed rounds: AB00 {a['selected_round']}/{len(a['trace'])}; AB01 {b['selected_round']}/{len(b['trace'])}. {initialization_scope}",'',
        'The common scientific implementation is byte-identical. Only continuation gates/tests changed after the control review: review identities and terminal status, supplemental scope, pre-optimization control forecasts and scientific source pin. A positive-path Markdown/JSON mismatch failed before optimization, was retained and fixed with a regression test. Original protocol/data/checkpoints were not rewritten.','',
        f"Exploratory continuation conditions: `{gates}`. All pass: **{all(gates.values())}**. These are separate from the original binding success targets; no promotion or repeat seeds are justified.",'',
        '| Family | JP02 correct | AB00 correct | AB01 correct |', '| --- | ---: | ---: | ---: |']
    for name,row in evidence['per_category'].items():
        if name=='<unknown>':continue
        lines.append(f"| {name} | {row['JP02_complete']} | {row['AB00_complete']} | {row['AB01_complete']} |")
    lines += ['', 'All argument distributions remain fixed: changes in correctly typed argument-error counts reflect selection of rows, not learned argument improvements. The numerical JSON retains category NLLs and paired targeting/continuation/change/blocked results.','',
        'Optimization excludes15wholeTRAINgroups; all original rows remain in assessment. Warm components and prior research already saw these games. The shuffled control retains contextual structure and identical vectors. The combined39-plus2soft-indicator input package and linear correction cannot identify individual-field value, recover lost float32 precision, or determine Fish intent. Five reused DEV groups, selected checkpoints, one seed, engine/group confounding and augmented-cadence filtering limit inference.','',
        'Frozen modes cap priority248/576,ward27/112,blocked22/110,movement1428/2362 andcast1 144/243. The original90%-per-supported-category,macro,movement,likelihood,targetingandthree-seed requirements remain unmet. Shops remain43strictfailureswithmissingargumentlikelihood; sparsecategories,entityidentity,fulllegalityandglobalcalibrationremainuncertified.','',
        'A fresh Sol xhigh review of AB01 and the matched study is required. No new fit, reserved access, match, download, engine query, bot/runtime or deployment work occurs in this saved-output analysis.','']
    path=OUT/'AB-MATCHED-REPORT.md'
    if path.exists():raise FileExistsError('Preserve matched report')
    path.write_text('\n'.join(lines),encoding='utf-8')
    print('Matched study',checks,gates,flush=True)


if __name__=='__main__':run()
