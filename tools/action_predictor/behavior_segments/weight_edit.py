"""Three explicit inference-only checkpoint edits; never overwrites trained weights."""
import argparse,json,time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from .data import ROOT,REPORT as BASE,WORK as BASE_WORK,load
from . import model
from .study import check,evaluate
from ..audit import immutable_json
from ..data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v44'
WORK=ROOT/'.cambc/action-predictor/v44'
CANDIDATES={'history_x5':(5.,0.),'prior_half':(1.,.5),'combined':(5.,.5)}


def edit(state,frequency,history_scale,prior_strength):
    result={k:v.clone() for k,v in state.items()}
    result['memory.weight_ih'][:,32:55]*=history_scale
    freq=torch.as_tensor(frequency,dtype=result['code.bias'].dtype)
    shift=torch.where(freq>0,-prior_strength*freq.clamp_min(1e-12).log(),torch.zeros_like(freq))
    result['code.bias']+=shift
    return result


def code_metrics(records):
    counts=Counter(r['code_label'] for r in records)
    recalls={k:sum(r['code_prediction']==k for r in records if r['code_label']==k)/n for k,n in counts.items()}
    return dict(accuracy=sum(r['code_prediction']==r['code_label'] for r in records)/len(records),
        balanced_recall=float(np.mean(list(recalls.values()))),recalls=recalls,
        predicted_counts=dict(Counter(r['code_prediction'] for r in records)))


def guard(summary,codes,reference,reference_codes):
    return dict(code_balance=codes['balanced_recall']>=reference_codes['balanced_recall']+.10,
        code_accuracy=codes['accuracy']>=reference_codes['accuracy']-.02,
        movement_accuracy=summary['movement_accuracy']>=reference['movement_accuracy']-.01,
        movement_nll=summary['movement_nll']<=reference['movement_nll']+.01,
        goal_within2=summary['goal_within2']>=reference['goal_within2']-.02,
        goal_error=summary['mean_goal_error']<=reference['mean_goal_error']+.25)


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    plan=json.loads((BASE/'protocol.json').read_text());check(plan)
    inputs={str((BASE/'protocol.json').relative_to(ROOT)):digest(BASE/'protocol.json'),
        str((BASE/'discovery.json').relative_to(ROOT)):digest(BASE/'discovery.json'),
        str((BASE_WORK/'S01-run/final.pt').relative_to(ROOT)):digest(BASE_WORK/'S01-run/final.pt')}
    for split in ('fit','evaluation'):
        p=BASE_WORK/'S01-run'/(split+'-predictions.json');inputs[str(p.relative_to(ROOT))]=digest(p)
    immutable_json(REPORT/'plan.json',dict(sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_weight_edit.py'))},
        input_bindings=inputs,candidates=CANDIDATES,seconds_cap=600,
        edits='Multiply only GRU input weights for23previous-descriptor values by5; or add-half-log-fitting-frequency correction to active code biases; or both. Leave unavailable classes unchanged. No masks, recurrent weights or other tensors are edited.',
        selection='Evaluate all3on fitting groups only. Among candidates passing every fitting guard select highest balanced code recall, then highest code accuracy, then name. If none pass, select the same ranking across all3as a diagnostic only. Evaluate only that selected candidate on evaluation groups once. Never switch after evaluation.',
        guards='Balanced code recall +10pp minimum; code accuracy loss<=2pp; movement accuracy loss<=1pp; movementNLL increase<=0.01; goalwithin2 loss<=2pp; goalerror increase<=0.25tiles. All required in each split.',
        scope='Postfit manual weight editing authorized by user. Same preexposed research groups and hindsight code labels. No gradient descent, optimizer state reuse, model promotion or runtime modification. Original checkpoint preserved.'))


def run():
    frozen=json.loads((REPORT/'plan.json').read_text())
    for group in ('sources','input_bindings'):
        for p,h in frozen[group].items():assert digest(ROOT/p)==h
    WORK.mkdir(parents=True,exist_ok=False);start=time.perf_counter();deadline=start+frozen['seconds_cap'];torch.set_num_threads(4)
    plan=json.loads((BASE/'protocol.json').read_text());check(plan);discovery=json.loads((BASE/'discovery.json').read_text());windows,maps=load()
    cache={w['key']:model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    base=torch.load(BASE_WORK/'S01-run/final.pt',map_location='cpu',weights_only=False)['model']
    original=json.loads((BASE_WORK/'S01-run/fit-predictions.json').read_text());counts=Counter(r['code_label'] for r in original['records'])
    frequency=[counts[k]/len(original['records']) for k in range(8)];reference_codes=code_metrics(original['records']);results={}
    for name,(scale,prior) in frozen['candidates'].items():
        state=edit(base,frequency,scale,prior);changed=[k for k in base if not torch.equal(base[k],state[k])]
        assert set(changed)<= {'memory.weight_ih','code.bias'}
        net=model.SegmentPolicy(plan['schema'],8).eval();net.load_state_dict(state)
        value=evaluate(net,windows,maps,cache,discovery,'fit',deadline);codes=code_metrics(value['records'])
        checks=guard(value['summary'],codes,original['summary'],reference_codes)
        torch.save(dict(model=state,base_checkpoint_sha256=digest(BASE_WORK/'S01-run/final.pt'),plan_sha256=digest(REPORT/'plan.json'),
            edit=name,frequency=frequency,inference_only=True),WORK/(name+'.pt'))
        immutable_json(WORK/(name+'-fit.json'),value)
        results[name]=dict(summary=value['summary'],codes=codes,guards=checks,eligible=all(checks.values()),changed_tensors=changed)
        print(name,json.dumps(results[name]),flush=True)
    eligible=[k for k,v in results.items() if v['eligible']]
    chosen=sorted(eligible or results,key=lambda k:(-results[k]['codes']['balanced_recall'],-results[k]['codes']['accuracy'],k))[0]
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),fit_results=results,selected=chosen,fit_eligible=bool(eligible),
        qualification='Frozen fitting-only selection, written before selected evaluation inference.'))
    saved=torch.load(WORK/(chosen+'.pt'),map_location='cpu',weights_only=False)
    net=model.SegmentPolicy(plan['schema'],8).eval();net.load_state_dict(saved['model'])
    evaluation=evaluate(net,windows,maps,cache,discovery,'evaluation',deadline);codes=code_metrics(evaluation['records'])
    reference=json.loads((BASE_WORK/'S01-run/evaluation-predictions.json').read_text());reference_codes=code_metrics(reference['records'])
    checks=guard(evaluation['summary'],codes,reference['summary'],reference_codes)
    immutable_json(WORK/'selected-evaluation.json',evaluation)
    for p,h in frozen['input_bindings'].items():assert digest(ROOT/p)==h
    elapsed=time.perf_counter()-start
    if elapsed>=frozen['seconds_cap']:raise TimeoutError('Editing/evaluation cap exceeded')
    immutable_json(REPORT/'result.json',dict(selection_sha256=digest(REPORT/'selection.json'),selected=chosen,
        evaluation_summary=evaluation['summary'],evaluation_codes=codes,evaluation_guards=checks,
        passed=bool(eligible) and all(checks.values()),seconds=elapsed,optimizer_updates=0,original_inputs_unchanged=True,
        bindings={str(p.relative_to(ROOT)):digest(p) for p in WORK.iterdir() if p.is_file()},
        qualification='Manual weight-edit pilot on preexposed groups. Code accuracy is agreement with inferred labels, not verified intent or goal-location accuracy. No runtime promotion.'))
    print(json.dumps(dict(selected=chosen,evaluation=evaluation['summary'],codes=codes,guards=checks),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','run'));a=p.parse_args()
    freeze() if a.command=='freeze' else run()
