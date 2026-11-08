"""All existing fitting windows; no target-dependent selection."""
import json
import numpy as np
from ..history_horizon.data import load as load_fit,ROOT,WORK as DATA_WORK,REPORT as DATA_REPORT
from ..history_horizon.assessment import windows
from ..audit import immutable_json
from ..data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v36'
WORK=ROOT/'.cambc/action-predictor/v36'


def freeze():
    previous=ROOT/'tools/action_predictor/experiments/v33/protocol.json'
    protocol=json.loads(previous.read_text());assembly=DATA_REPORT/'assembly.json'
    if digest(assembly)!=protocol['inputs'][str(assembly.relative_to(ROOT))]:raise ValueError('Assembly changed')
    manifest=json.loads(assembly.read_text());data=load_fit('fit');identities=[];groups={};bindings={str(assembly.relative_to(ROOT)):digest(assembly)}
    for index,game in enumerate(manifest['games']):
        if game['partition']!='fit':continue
        groups[index]=game['group'];path=DATA_WORK/'games'/game['payload']/'rows.json'
        if digest(path)!=game['row_identity_sha256']:raise ValueError('Row identities changed')
        bindings[str(path.relative_to(ROOT))]=digest(path)
        identities.extend(dict(row=r,payload=game['payload'],group=game['group']) for r in json.loads(path.read_text()))
    candidates=[];phase=np.full(len(identities),-1,np.int64);raw=data['arrays']
    for sequence in data['sequences']:
        age=0
        for i in sequence:
            if raw['actor_start'][i] or raw['root_gap'][i]!=1 or age>=8:age=0
            phase[i]=age;age+=1
    for ids in windows(data,32):
        first,last=identities[ids[0]],identities[ids[-1]]
        if phase[ids[0]]!=0:raise ValueError('Window is not aligned with A reset')
        if first['payload']!=last['payload'] or first['row']['actor']!=last['row']['actor']:raise ValueError('Mixed stream')
        identity=json.dumps([first['payload'],first['row']['actor'],first['row']['ordinal'],first['row']['event'],last['row']['event']],separators=(',',':'))
        candidates.append(dict(identity=identity,group=first['group'],source_ids=ids.tolist()))
    selected=candidates;ids=np.array([i for window in selected for i in window['source_ids']])
    counts={str(k):int(v) for k,v in zip(*np.unique(raw['y'][ids],return_counts=True))}
    strata={name:int(((raw['y'][ids]==8)&(raw['direction'][ids]==code)).sum()) for name,code in [('change',3),('continue',2)]}
    actual_groups={w['group'] for w in selected}
    passed=len(selected)==1085 and len(ids)==34720 and len(np.unique(ids))==34720 and actual_groups==set(groups.values()) and len(actual_groups)==40 and min(strata.values())>=400
    value=dict(source_sha256=digest(__file__),bindings=bindings,windows=selected,candidate_windows=len(candidates),
        rows=len(ids),groups=len(actual_groups),category_counts=counts,strata=strata,passed=passed,
        rule='All 1085 existing nonoverlapping 32-root fitting windows in canonical source order, aligned with A eight-root resets. Verify 40 groups and unique contiguous rows. No replacements or label-dependent selection.',new_fits=0)
    immutable_json(REPORT/'selection.json',value)
    if not passed:raise ValueError('Frozen feasibility gate failed; do not resample')
    print(json.dumps({k:value[k] for k in ('candidate_windows','rows','groups','category_counts','strata','passed')},indent=2))


def load_subset():
    selection=json.loads((REPORT/'selection.json').read_text())
    if not selection['passed']:raise ValueError('Selection failed')
    original=load_fit('fit');ids=np.array([i for w in selection['windows'] for i in w['source_ids']],np.int64)
    if len(ids)!=34720 or len(np.unique(ids))!=34720:raise ValueError('Selection coverage changed')
    raw={k:v[ids].copy() for k,v in original['arrays'].items()}
    # Each isolated window begins on an original A reset boundary. This bit is
    # reset metadata only; explicit histories and all learned inputs stay exact.
    raw['actor_start'][::32]=True
    if not np.all(raw['root_gap'].reshape(-1,32)[:,1:]==1):raise ValueError('Noncontiguous window')
    return dict(arrays=raw,sequences=[np.arange(a,a+32) for a in range(0,34720,32)],
                group=original['group'][ids],source_ids=ids)


if __name__=='__main__':freeze()
