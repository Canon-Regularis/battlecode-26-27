"""Frozen all-game feature assembly and canonical parity; no optimizer."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import zipfile
import numpy as np
from ..audit import cursor, immutable_json
from ..data import digest
from ..targets import point
from ..rich_data import SPATIAL
from ..priority_regularized.safety import dependency_files, reject_optimized_python
from ..priority_broad.guard import committed_sources
from .audit import ROOT, REPORT, BASE, eligible_jobs, label, window_counts
from .feature_sources import load_game
from .feature_inputs import inputs
from .reference import ranges

WORK = ROOT/'.cambc/action-predictor/v32/features-v1'
FIELDS = ('grid','valid','move_mask','y','py','priority','attack_range','ability_range','ability_mask')


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT, dependency_files(ROOT,
        ('tools.action_predictor.trajectory_history.assemble',
         'tools.action_predictor.trajectory_history.test_audit',
         'tools.action_predictor.trajectory_history.test_windows',
         'tools.action_predictor.trajectory_history.test_features',
         'tools.action_predictor.trajectory_history.test_reference')))


def freeze():
    commit, sources = source_gate()
    records = json.loads((REPORT/'window-validation.json').read_text())['games']
    jobs = {j['record']['raw_sha256']:j for j in eligible_jobs()}
    bindings = {}
    for r in records:
        bindings.update(r['bindings']); job = jobs[r['payload']]
        bindings[job['shard']] = job['shard_sha256']
        for kind in ('supplement','augmentation'):
            p = Path(job['work'])/kind/r['payload']/'pre.jsonl'
            if p.exists(): bindings[str(p)] = digest(p)
        p = REPORT/'window-proposals'/(r['payload']+'.json'); bindings[str(p)] = digest(p)
    for name in ('window-validation.json','window-inventory.json','feature-probe.json','data-review-r2.json'):
        p = REPORT/name; bindings[str(p)] = digest(p)
    for p, expected in bindings.items():
        if digest(p) != expected: raise ValueError('Assembly input changed: '+p)
    immutable_json(REPORT/'assembly-plan.json', dict(source_commit=commit,sources=sources,inputs=bindings,
        rows=97152, games=60, extra_roots=42010,
        contract='Same frozen windows and all selected roots in60games. Current253features/last16actualcommands/last16observations+availability/candidategeometry/earlierpriorityarguments. Current/scheduledpriority uniformly unavailable. No learned IDs. Targetarrays separate from inputs.',
        normalization='Only current-observation rows belonging to fitting groups determine mean/sample-std, floor.01; missing observation vectors must be re-masked after normalization. No pretrained components.',
        scope='Data assembly only; fitting requires independent review and a separate matched-horizon protocol.',
        new_fits=0,reserved_opened=0))


def reference_cache(jobs):
    selections = [(j['record']['raw_sha256'], j['offset'], j['rows']) for j in jobs]
    with zipfile.ZipFile(BASE/'combined-train.npz') as archive:
        for name in FIELDS:
            with archive.open(name+'.npy') as stream:
                for payload, value in ranges(stream, selections):
                    directory = WORK/'reference'/payload; directory.mkdir(parents=True,exist_ok=True)
                    np.save(directory/(name+'.npy'), value)
            print('Reference rows', name, flush=True)


def game(job, record):
    loaded = load_game(job, record)
    frames, selected, actors = loaded['frames'],loaded['selected'],loaded['actors']
    labels = job['manifest']['labels']; out = defaultdict(list); identifiers=[]; offsets=[0]
    reference = {k:np.load(WORK/'reference'/record['payload']/(k+'.npy'),mmap_mode='r') for k in FIELDS}
    counts=Counter(); streams=[]
    for actor, roots in sorted(actors.items()):
        roots.sort(key=lambda r:cursor(r['event'])); previous=None; stream=[]
        for ordinal, root in enumerate(roots):
            event=root['event']
            if event not in loaded['keep']:
                if stream: streams.append(stream); stream=[]
                continue
            frame=frames[event]; obs=frame['observation']; own=obs['own']
            target=label(root['indexed_turn'],root['root'],frame)
            if target is None: raise ValueError('Unmodeled retained row')
            value=inputs(frame, roots[:ordinal], frames, loaded['route'],labels)
            pos=own.get('position'); destination=target['destination']; py=-1
            if target['family'] in SPATIAL:
                py=290
                if point(pos) and point(destination):
                    dx,dy=destination['x']-pos['x'],destination['y']-pos['y']
                    py=(dy+8)*17+dx+8 if max(abs(dx),abs(dy))<=8 else 289
            props=own.get('abilityProps',[{},{}])
            rules=np.array([own.get('attackRange',0),*[p.get('range',0) for p in props],
                            *[p.get('target',0) for p in props]],np.float32)
            y=labels.index(target['family']); priority=target['priority'] if y==labels.index('priority') else 0
            if event in selected:
                ix=selected[event]
                np.testing.assert_array_equal(value['x'],loaded['expected']['x'][ix])
                np.testing.assert_array_equal(value['history'],loaded['expected']['history'][ix,-16:])
                for k in ('grid','valid','move_mask'):
                    candidate=value[k].astype(np.float16) if k=='grid' else value[k]
                    np.testing.assert_array_equal(candidate,reference[k][ix])
                if y!=reference['y'][ix] or py!=reference['py'][ix] or priority!=reference['priority'][ix]:
                    raise ValueError('Canonical target parity failed')
                old_rules=np.r_[reference['attack_range'][ix],reference['ability_range'][ix],reference['ability_mask'][ix]]
                np.testing.assert_array_equal(rules,old_rules)
                counts['canonical_rows_exact_parity']+=1
            else: counts['extra_rows']+=1
            # Match canonical float16 geometry storage for all three future arms.
            value['grid']=value['grid'].astype(np.float16)
            for k,v in value.items():
                if not np.isfinite(v).all(): raise ValueError('Nonfinite feature: '+k)
                out[k].append(v)
            gap=ordinal-previous if previous is not None else ordinal+1
            out['root_gap'].append(gap);out['actor_start'].append(previous is None)
            out['y'].append(y);out['py'].append(py);out['priority'].append(priority)
            out['rules'].append(rules);out['round'].append(root['round'])
            # Diagnostic only: do not feed target direction to any model.
            direction=0
            if target['family']=='move':
                current=np.array([destination[k]-root['step']['from'][k] for k in ('x','y')])
                earlier=next((p['step'] for p in reversed(roots[:ordinal]) if p['step']['kind']==4),None)
                direction=4 if not current.any() else 1 if earlier is None else 2 if np.array_equal(
                    np.sign(current),np.sign([earlier['to'][k]-earlier['from'][k] for k in ('x','y')])) else 3
            out['direction'].append(direction)
            identifiers.append(dict(actor=actor,ordinal=ordinal,event=event,pre=frame['pre']))
            stream.append((ordinal,root['round']));previous=ordinal
        if stream:streams.append(stream)
        if offsets[-1]!=len(identifiers):offsets.append(len(identifiers))
    if window_counts(streams)!=record['windows']:raise ValueError('Assembled window topology changed')
    if len(identifiers)!=len(loaded['keep']):raise ValueError('Assembled row coverage changed')
    arrays={k:np.asarray(v) for k,v in out.items()};arrays['offsets']=np.array(offsets,np.int64)
    directory=WORK/'games'/record['payload'];directory.mkdir(parents=True,exist_ok=False)
    target=directory/'data.npz';np.savez_compressed(target,**arrays)
    immutable_json(directory/'rows.json',identifiers)
    result=dict(payload=record['payload'],group=record['group'],partition=record['partition'],
        rows=len(identifiers),counts=dict(counts),windows=record['windows'],input_bindings=loaded['bindings'],
        arrays_sha256=digest(target),row_identity_sha256=digest(directory/'rows.json'))
    immutable_json(directory/'receipt.json',result)
    return result,arrays['x']


def run():
    commit,sources=source_gate();plan_path=REPORT/'assembly-plan.json';plan=json.loads(plan_path.read_text())
    if sources!=plan['sources']:raise ValueError('Frozen source closure changed')
    for name,expected in plan['inputs'].items():
        if digest(name)!=expected:raise ValueError('Frozen assembly input changed: '+name)
    if WORK.exists():raise FileExistsError('Preserve prior assembly attempt: '+str(WORK))
    records=json.loads((REPORT/'window-validation.json').read_text())['games']
    jobs={j['record']['raw_sha256']:j for j in eligible_jobs()}
    WORK.mkdir(parents=True);reference_cache([jobs[r['payload']] for r in records])
    results=[];n=0;total=np.zeros(253);squares=np.zeros(253)
    for record in records:
        result,x=game(jobs[record['payload']],record);results.append(result)
        if record['partition']=='fit':
            x=x.astype(np.float64);n+=len(x);total+=x.sum(0);squares+=(x*x).sum(0)
        print('Assembled',len(results),'/',len(records),record['partition'],flush=True)
    if sum(r['rows'] for r in results)!=plan['rows']:raise ValueError('Frozen total row count changed')
    mean=total/n;std=np.sqrt(np.maximum((squares-total*total/n)/(n-1),0)).clip(.01)
    np.savez_compressed(WORK/'normalizer.npz',mean=mean.astype(np.float32),std=std.astype(np.float32),fit_rows=n)
    immutable_json(REPORT/'assembly.json',dict(source_commit=commit,plan_sha256=digest(plan_path),
        games=results,normalizer_sha256=digest(WORK/'normalizer.npz'),fit_normalizer_rows=n,
        new_fits=0,reserved_opened=0,ready_for_fit=False,
        next='Independent feature/data review and matched reset/BPTT training protocol required before optimization. Preserve masks after normalization; no warm trained components.'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run'])
    (freeze if p.parse_args().command=='freeze' else run)()
