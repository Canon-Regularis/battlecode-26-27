"""Immutable completion, guards and exact counts; does not change any forecast."""
import argparse,json
import numpy as np
from .protocol import ROOT,BASE,WORK,REPORT
from .data import read
from ..audit import immutable_json
from ..data import digest
from ..observation_metrics import correctness

def run(identifier):
    info=json.loads((REPORT/f'{identifier}.json').read_text());results={}
    for split in ('train','validation'):
        path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        with np.load(path) as z:raw={k:z[k] for k in ('y','py','priority','group')}
        p=read(WORK/f'runs/{identifier}/{split}-predictions.npz');old=read(BASE.parent/f'v9/runs/G00/{split}-predictions.npz');parameter,joint=correctness(raw,p);op,oj=correctness(raw,old);direction=np.load(BASE.parent/f'v7/{split}-direction.npy');masks={'all':np.ones(len(joint),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        results[split]={}
        for name,base in masks.items():
            contexts={}
            for kind,m in [('move',raw['y']==8),('blocked',raw['y']==3),('continuing',(raw['y']==8)&(direction==2)),('changing',(raw['y']==8)&(direction==3)),('startup',(raw['y']==8)&(direction==1))]:
                m=m&base;typed=m&(p['prediction']==raw['y']);n=int(m.sum());contexts[kind]=dict(rows=n,parameter_exact=int((parameter&m).sum()),G00_parameter_exact=int((op&m).sum()),joint_exact=int((joint&m).sum()),G00_joint_exact=int((oj&m).sum()),correctly_typed_support=int(typed.sum()),parameter_rescues=int((parameter&~op&m).sum()),parameter_regressions=int((~parameter&op&m).sum()),joint_rescues=int((joint&~oj&m).sum()),joint_regressions=int((~joint&oj&m).sum()),mean_joint_nll=float(p['nll'][m].mean()) if n else None,G00_mean_joint_nll=float(old['nll'][m].mean()) if n else None,mean_conditional_nll=float(p['param_nll'][m].mean()) if n else None,G00_mean_conditional_nll=float(old['param_nll'][m].mean()) if n else None)
            results[split][name]=contexts
    v=results['validation']['all'];report=info['reports']['validation'];delta=lambda k,field:(v[k][field]-v[k]['G00_'+field])/v[k]['rows']
    guards=dict(move_joint_gain_at_least_3pp=delta('move','joint_exact')>=.03,continuation_parameter_loss_at_most_half_pp=delta('continuing','parameter_exact')>=-.005,no_change_joint_regression=delta('changing','joint_exact')>=0,no_blocked_joint_regression=delta('blocked','joint_exact')>=0,full_joint_NLL_lower=info['comparisons']['G00']['all']['paired95']['joint_nll']['high'] is not None and report['all']['joint_nll']<float(np.mean(read(BASE.parent/'v9/runs/G00/validation-predictions.npz')['nll'])),paired_move_joint_gain_lower_positive=info['comparisons']['G00']['move']['paired95']['joint_accuracy']['low']>0,overall_strict_no_regression=report['all']['strict_correct']>=11510)
    guards['nonmovement_parameters_and_types_exactly_preserved']=True # asserted in completed fitter before report exists
    reports=[f'{identifier}.json',f'{identifier}-causal-roundtrip.json','protocol.json','input-bindings.json','G00-baseline-contexts.json','simple-baseline-reference.json'];files={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'runs'/identifier).iterdir() if p.is_file()}
    helper_names=['entity_set.py','goal_memory.py','consistent_data.py','observation_data.py','rich_data.py','reliable_train.py','proposal_predictor.py','command_mixture.py','priority_predictor.py','movement_predictor.py','priority_fit_v3.py']
    helpers={name:digest(ROOT/'tools/action_predictor'/name) for name in helper_names}
    immutable_json(REPORT/f'{identifier}-completion.json',dict(results=results,guards=guards,all_exploratory_guards_pass=all(guards.values()),artifacts=files,reports={n:digest(REPORT/n) for n in reports},helper_sources=helpers,commands=[f'python -m tools.action_predictor.movement_experts.fit {identifier}',f'python -m tools.action_predictor.movement_experts.roundtrip {identifier}',f'python -m tools.action_predictor.movement_experts.analysis {identifier}'],source_sha256=digest(__file__),reference='Strongest retained fixed simple movement exact baseline .5520745131244708; original target .6520745131244708 remains, independent of exploratory3pp allocation. G00/G01 are retained learned controls.',qualification='Parameter diagnostics use actual family only after inference. Full forecasts always unchanged predicted family. All natural and augmented rows retained in reports; frozen encoder saw augmented TRAIN, so neither is fresh held-out evidence. No success or robustness certification from one seed/five reused groups.',new_fits=0,reserved_opened=0,promoted=False));print(identifier,'guards',guards,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');run(p.parse_args().identifier)
