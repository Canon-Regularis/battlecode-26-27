"""Parent reproduction and diagnostics. No optimizer updates or new selection."""
import json,time
from collections import Counter
import numpy as np
import torch
from .data import ROOT,REPORT,WORK,FEATURES,load
from . import segmentation,model
from .study import check,endpoint_labels,evaluate
from ..goal_position.study import baseline
from ..goal_position.model import goal_guided_move
from ..goal_position.evaluator import xy
from ..audit import immutable_json
from ..data import digest


def run():
    torch.set_num_threads(4);plan=json.loads((REPORT/'protocol.json').read_text());check(plan)
    receipt=json.loads((REPORT/'data.json').read_text())
    for p,h in receipt['source_bindings'].items():
        if digest(p)!=h:raise ValueError('Original cached source changed')
    windows,maps=load();fitting=[w for w in windows if w['partition']=='fit'];discovery=json.loads((REPORT/'discovery.json').read_text())
    pairs=[(np.asarray([s['behavior'] for s in w['steps']]),np.asarray([s['behavior_mask'] for s in w['steps']])) for w in fitting]
    fitted=segmentation.fit(pairs,k=plan['codes'],iterations=plan['discovery_iterations'],penalty=plan['change_penalty'],minimum=plan['minimum_duration'],seed=plan['seed'])
    assert fitted==discovery['fitted']
    assert np.all(np.diff([x['objective'] for x in fitted['trace']])<=1e-8)
    keys=set();code_counts=Counter();code_profiles={};incidental=Counter()
    for w in windows:
        assert w['key'] not in keys;keys.add(w['key']);assert len(w['steps'])==32
        code=segmentation.assign([s['behavior'] for s in w['steps']],[s['behavior_mask'] for s in w['steps']],fitted)
        assert code.tolist()==discovery['labels'][w['key']]
        goals,_=endpoint_labels(w,code,maps[w['payload']]);assert goals==discovery['endpoints'][w['key']]
        if w['partition']=='fit':
            for i,(s,k) in enumerate(zip(w['steps'],code)):
                if s['observed']:code_counts[int(k)]+=1
                p=code_profiles.setdefault(int(k),dict(turns=0,observed=0,commands=np.zeros(15),health_delta_available=0))
                p['turns']+=1;p['observed']+=s['observed'];p['commands']+=np.expm1(s['behavior'][:15]);p['health_delta_available']+=s['behavior_mask'][17]>0
                if i<31:
                    for name,j in (('ward',9),('cast0',2),('cast1',3),('recall',6)):
                        if s['behavior'][j]>0:incidental[name+'_turns']+=1;incidental[name+'_without_next_boundary']+=code[i]==code[i+1]
    majority=code_counts.most_common(1)[0][0]
    cache={w['key']:model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    verified={};saved_results={};last_net=None
    for arm in ('S00','S01'):
        r=json.loads((REPORT/(arm+'.json')).read_text());saved_results[arm]=r
        for p,h in r['bindings'].items():assert digest(ROOT/p)==h
        directory=WORK/(arm+'-run');torch.manual_seed(plan['seed']);net=model.SegmentPolicy(plan['schema'],plan['codes'])
        initial=torch.load(directory/'initial.pt',map_location='cpu',weights_only=True)
        assert all(torch.equal(v,initial[k]) for k,v in net.state_dict().items())
        saved=torch.load(directory/'final.pt',map_location='cpu',weights_only=False);net.load_state_dict(saved['model'])
        assert all(torch.isfinite(v).all() for v in saved['model'].values())
        trace=json.loads((directory/'trace.json').read_text());rng=np.random.default_rng(plan['seed'])
        for epoch,t in enumerate(trace,1):
            assert t['order']==rng.permutation(len(fitting)).tolist();assert t['updates']==epoch*len(fitting)
        n_goal=sum(any(g is not None for g in discovery['endpoints'][w['key']]) for w in fitting)*plan['passes']
        n_move=sum(any(s['movement'] is not None for s in w['steps']) for w in fitting)*plan['passes']
        n_either=sum(any(g is not None for g in discovery['endpoints'][w['key']]) or any(s['movement'] is not None for s in w['steps']) for w in fitting)*plan['passes']
        for index,(name,param) in enumerate(net.named_parameters()):
            optimizer=saved['optimizer']['state'][index]
            expected=n_goal if name.startswith(('goal.','query.')) else n_move if name.startswith('movement.') else n_either if name=='embeddings' else plan['updates_per_arm']
            assert int(optimizer['step'])==expected,(name,int(optimizer['step']),expected)
            assert all(torch.isfinite(v).all() for v in optimizer.values() if isinstance(v,torch.Tensor))
        reproduced={}
        for split in ('fit','evaluation'):
            value=evaluate(net,windows,maps,cache,discovery,split,time.perf_counter()+300)
            archive=json.loads((directory/(split+'-predictions.json')).read_text());assert value==archive
            assert r['summaries'][split]==dict(summary=value['summary'],groups=value['groups'])
            reproduced[split]=len(value['records'])
        verified[arm]=dict(exact_initial_tensors=True,exact_schedules=True,exact_forecasts=reproduced,all_optimizer_steps_verified=True)
        last_net=net
    a=torch.load(WORK/'S00-run/initial.pt',weights_only=True);b=torch.load(WORK/'S01-run/initial.pt',weights_only=True)
    assert all(torch.equal(a[k],b[k]) for k in a)
    evaluation=json.loads((WORK/'S01-run/evaluation-predictions.json').read_text())['records']
    code_recall={k:sum(r['code_prediction']==k for r in evaluation if r['code_label']==k)/sum(r['code_label']==k for r in evaluation) for k in sorted({r['code_label'] for r in evaluation})}
    baselines={}
    for kind in ('current_position','nearest_known_camp_approach','nearest_altar_approach'):
        errors=[];moves=0;correct=0
        for w in windows:
            if w['partition']!='evaluation':continue
            route=maps[w['payload']]
            for s,g in zip(w['steps'],discovery['endpoints'][w['key']]):
                if not s['observed'] or s['input']['observation']['own'].get('position') is None:continue
                p=baseline(s['input'],route,kind)
                if g is not None:errors.append(max(abs(p[0]-g[0]),abs(p[1]-g[1])))
                if s['movement'] is not None:
                    origin=xy(s['input']['observation']['own']['position']);actual=(origin[0]+s['movement'][0],origin[1]+s['movement'][1])
                    moves+=1;correct+=goal_guided_move(route,s['input'],p)==actual
        baselines[kind]=dict(goal_rows=len(errors),goal_within2=float(np.mean(np.asarray(errors)<=2)),goal_error=float(np.mean(errors)),movement_rows=moves,astar_accuracy=correct/moves)
    # Permuting only the code embeddings is a postfit reliance diagnostic, not a new policy candidate.
    with torch.no_grad():last_net.embeddings.copy_(last_net.embeddings.roll(1,0))
    ablated=evaluate(last_net,windows,maps,cache,discovery,'evaluation',time.perf_counter()+300)['summary']
    from .predictor import BehaviorPredictor
    predictor=BehaviorPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None
    records=[r for r in evaluation if r['key']==w['key']]
    for i,s in enumerate(w['steps']):
        p=predictor.predict(s['input'],maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state);state=p['state']
        if s['observed']:
            r=next(r for r in records if r['position']==i);assert p['code']==r['code_prediction']
            assert (None if p['goal'] is None else list(p['goal']))==r['goal_prediction']
    profiles={str(k):dict(turns=p['turns'],observed=p['observed'],mean_commands_per_turn={FEATURES[j]:float(v/p['turns']) for j,v in enumerate(p['commands'])},health_delta_available=p['health_delta_available']) for k,p in code_profiles.items()}
    examples=[]
    for w in sorted(fitting,key=lambda w:w['key'])[:4]:
        examples.append(dict(key=w['key'],codes=discovery['labels'][w['key']],observed=[s['observed'] for s in w['steps']],segments=[dict(start=a,end=b,code=k) for a,b,k in segmentation.ranges(discovery['labels'][w['key']])]))
    immutable_json(REPORT/'verification.json',dict(protocol_sha256=digest(REPORT/'protocol.json'),results={k:digest(REPORT/(k+'.json')) for k in saved_results},
        discovery_reproduced_exactly=True,all_endpoint_labels_reproduced=True,matched_initialization=True,arms=verified,
        streaming_window_matches=True,code_profiles=profiles,incidental_event_counts={k:int(v) for k,v in incidental.items()},
        evaluation_code_recalls=code_recall,evaluation_balanced_code_accuracy=float(np.mean(list(code_recall.values()))),
        fitting_majority_code=majority,evaluation_majority_accuracy=sum(r['code_label']==majority for r in evaluation)/len(evaluation),
        baselines=baselines,permuted_code_embedding_diagnostic=ablated,examples=examples,
        optimizer_updates=0,qualification='Parent reproduction and postfit diagnostics; no selection/retraining. Baselines and permutation do not override frozen gates.'))
    print(json.dumps(dict(verified=verified,baselines=baselines,balanced_code_accuracy=float(np.mean(list(code_recall.values()))),permuted_embeddings=ablated),indent=2))


if __name__=='__main__':run()
