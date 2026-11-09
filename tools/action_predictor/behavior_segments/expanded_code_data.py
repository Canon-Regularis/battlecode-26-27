"""Reuse validated fitting-game windows without changing labels or evaluation rows."""
import argparse
import gzip
import json
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import numpy as np
import torch
from . import data,model,segmentation,code_weight_fit as first
from ..audit import immutable_json
from ..data import digest

ROOT=data.ROOT
REPORT=ROOT/'tools/action_predictor/experiments/v49'
WORK=ROOT/'.cambc/action-predictor/v49'


@contextmanager
def assembly_paths():
    old=(data.REPORT,data.WORK)
    data.REPORT,data.WORK=REPORT,WORK
    try:yield
    finally:data.REPORT,data.WORK=old


def fit_jobs(plan,receipt):
    jobs=[j for j in plan['jobs'] if j['partition']=='fit']
    groups={j['group'] for j in jobs}
    if len(jobs)!=32 or len(groups)!=32:raise ValueError('Expected32 distinct fitting groups')
    if groups & {j['group'] for j in plan['jobs'] if j['partition']!='fit'}:
        raise ValueError('Partition overlap')
    expected={r['payload']:r['candidates'] for r in receipt['groups'] if r['partition']=='fit'}
    if set(expected)!={j['payload'] for j in jobs}:raise ValueError('Missing fitting candidate counts')
    return jobs,expected


def read():
    with gzip.open(WORK/'data/windows.jsonl.gz','rt',encoding='utf-8') as f:windows=list(map(json.loads,f))
    maps={p.stem[:-4]:json.loads(p.read_text()) for p in (WORK/'data').glob('*-map.json')}
    return windows,maps


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    first.load_cache()
    old=json.loads((data.REPORT/'data-plan.json').read_text());receipt=json.loads((data.REPORT/'data.json').read_text())
    jobs,expected=fit_jobs(old,receipt)
    new=dict(old,jobs=jobs,windows_per_group=max(expected.values())+1,source_sha256=digest(data.__file__),
             revision='V49 fitting-only expansion to all previously counted eligible windows in the same32fitting games. '
             'Original observed-query threshold8,32turn boundaries,hash ordering,causal descriptors and PRE validation unchanged. '
             'No evaluation jobs, replay downloads or new discovery fitting.')
    immutable_json(REPORT/'data-plan.json',new)
    paths=[data.REPORT/'data-plan.json',data.REPORT/'data.json',data.REPORT/'discovery.json',
           data.REPORT/'protocol.json',first.REPORT/'plan.json',first.REPORT/'cache.json',first.INITIAL]
    immutable_json(REPORT/'assembly-plan.json',dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_expanded_code_data.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},expected_candidates=expected,
        data_plan_sha256=digest(REPORT/'data-plan.json'),
        requirements='Exactly1607nonoverlapping windows in the same32fitting groups; include every original256fitting window '
        'with exact object equality, identical frozen code labels and exact encoded-cache parity. '
        'Reconstruct with the original validated assembler through temporary output paths; restore globals even on failure. '
        'Keep original schema/prototypes/normalization/code meanings. No new architecture or evaluation targets.',
        next='Data/feature validation only. Freeze a separate optimizer plan before updates.'))


def assemble():
    frozen=json.loads((REPORT/'assembly-plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in frozen[kind].items():assert digest(ROOT/p)==h,p
    assert digest(REPORT/'data-plan.json')==frozen['data_plan_sha256']
    with assembly_paths():data.assemble()
    expanded,maps=read();original,_=data.load();original={w['key']:w for w in original if w['partition']=='fit'}
    assert len(expanded)==sum(frozen['expected_candidates'].values())==1607
    assert len({w['key'] for w in expanded})==len(expanded)
    assert all(w['partition']=='fit' for w in expanded)
    assert {w['group'] for w in expanded}=={w['group'] for w in original.values()}
    actual=Counter(w['payload'] for w in expanded);assert dict(actual)==frozen['expected_candidates']
    bykey={w['key']:w for w in expanded};assert all(bykey[k]==w for k,w in original.items())
    events=[(w['payload'],s['event']) for w in expanded for s in w['steps']]
    assert len(events)==len(set(events))
    discovery=json.loads((data.REPORT/'discovery.json').read_text());labels={};counts=Counter()
    for w in expanded:
        code=segmentation.assign([s['behavior'] for s in w['steps']],[s['behavior_mask'] for s in w['steps']],discovery['fitted']).tolist()
        labels[w['key']]=code
        counts.update(k for k,s in zip(code,w['steps']) if s['observed'])
        if w['key'] in original:assert code==discovery['labels'][w['key']]
    immutable_json(WORK/'labels.json',dict(labels=labels,original_discovery_sha256=digest(data.REPORT/'discovery.json')))
    immutable_json(REPORT/'parity.json',dict(assembly_plan_sha256=digest(REPORT/'assembly-plan.json'),
        data_sha256=digest(REPORT/'data.json'),labels_sha256=digest(WORK/'labels.json'),
        groups=len({w['group'] for w in expanded}),windows=len(expanded),turns=len(events),
        original_windows_exact=len(original),original_labels_exact=len(original),no_overlapping_turns=True,
        observed_queries=sum(counts.values()),code_counts=dict(counts),evaluation_payloads_reconstructed=0))
    print('Expanded data parity',len(expanded),'windows;',sum(counts.values()),'queries;',dict(counts),flush=True)


def cache():
    frozen=json.loads((REPORT/'assembly-plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in frozen[kind].items():assert digest(ROOT/p)==h,p
    receipt=json.loads((REPORT/'data.json').read_text());parity=json.loads((REPORT/'parity.json').read_text())
    for p,h in receipt['output_bindings'].items():assert digest(ROOT/p)==h,p
    assert digest(REPORT/'data.json')==parity['data_sha256'] and digest(WORK/'labels.json')==parity['labels_sha256']
    old,architecture,canonical,ids=first.load_cache();original={r['key']:i for i,r in enumerate(ids)}
    windows,maps=read();labels=json.loads((WORK/'labels.json').read_text())['labels']
    torch.set_num_threads(4);net=model.SegmentPolicy(architecture['schema'],8).eval()
    net.load_state_dict(torch.load(first.INITIAL,map_location='cpu',weights_only=False)['model']);capture={}
    handle=net.context.register_forward_pre_hook(lambda module,args:capture.update(context=args[0].detach()))
    rows=[];identities=[];unknown=0;matched=0
    with torch.no_grad():
        for index,w in enumerate(windows):
            args,n=model.encode_window(w,maps[w['payload']],architecture['schema']);unknown+=n;output=net(**args)
            item=dict(context=capture['context'].clone(),**{k:args[k] for k in ('previous','previous_mask','rounds','observed')},
                      labels=torch.tensor(labels[w['key']]))
            torch.testing.assert_close(first.code_forward(net,{k:v[None] for k,v in item.items()})[0],output['code'],atol=2e-6,rtol=2e-5)
            if w['key'] in original:
                for k,v in item.items():assert torch.equal(v,canonical[k][original[w['key']]]),(w['key'],k)
                matched+=1
            rows.append(item);identities.append(dict(key=w['key'],group=w['group'],fold=old['folds'][w['group']],canonical=w['key'] in original))
            if (index+1)%200==0:print('Cached',index+1,'/',len(windows),'windows',flush=True)
    handle.remove();assert matched==256
    torch.save({k:torch.stack([r[k] for r in rows]) for k in rows[0]},WORK/'fit-cache.pt')
    immutable_json(WORK/'identities.json',identities)
    immutable_json(REPORT/'cache.json',dict(parity_sha256=digest(REPORT/'parity.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'fit-cache.pt',WORK/'identities.json')},
        exact_canonical_windows=matched,all_forward_paths_match=True,windows=len(windows),
        unencoded_fields=unknown,scope='Original schema and map encoder; only fitting-game windows.'))
    print('Cached all expanded fitting windows with exact original256window parity',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','assemble','cache'))
    globals()[parser.parse_args().command]()
