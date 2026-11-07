"""Additive C03 repair attribution and immutable completion; no new decisions."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from .proposal_data import ROOT,BASE,WORK,REPORT
from .proposal_generator import NAMES
from .algorithmic.study import matches
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

def run():
    plan=json.loads((REPORT/'C03-plan.json').read_text())
    for p,h in plan['sources'].items():assert digest(ROOT/p)==h
    receipt=json.loads((REPORT/'C03-validation.json').read_text());path=BASE.parent/'v4/validation.npz'
    assert digest(path)==receipt['data_sha256']
    with np.load(path) as z:y=z['y'];py=z['py'];priority=z['priority']
    with np.load(BASE.parent/'v9/runs/G00/validation-predictions.npz') as z:base=np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),-1)[:,None]
    old=np.load(BASE.parent/'v10/validation-candidates.npy',mmap_mode='r')[:,1];new=np.load(WORK/'validation-candidates.npy',mmap_mode='r');b=matches(base,y,py,priority).any(1);om=matches(old,y,py,priority);nm=matches(new,y,py,priority);ou=om.any(1)|b;nu=nm.any(1)|b
    assert len(y)==14439
    losses=[];per={};source_recovery={}
    for k,name in enumerate(rt.LABELS):
        m=y==k;per[name]=dict(rows=int(m.sum()),old_union=int((ou&m).sum()),new_union=int((nu&m).sum()),old_missing_recovered=int((~ou&nu&m).sum()),support_lost=int((ou&~nu&m).sum()),remaining_missing=int((~nu&m).sum()))
    for idx in np.flatnonzero(ou&~nu):
        oldsources=[NAMES[k] for k in np.flatnonzero(om[idx]) if k<len(NAMES)-1]
        destination_sources=[NAMES[k] for k in np.flatnonzero((new[idx,:,1]==py[idx])&(new[idx,:,0]>=0))]
        outcomes=[rt.LABELS[int(new[idx,NAMES.index(s),0])] for s in destination_sources]
        losses.append(dict(index=int(idx),true_action=rt.LABELS[int(y[idx])],recorded_coordinate=int(py[idx]),old_matching_sources=oldsources,new_same_destination_sources=destination_sources,new_same_destination_actions=outcomes,explanation='Matching attempted destination retained but forecast as blocked, not move' if outcomes and set(outcomes)=={'blocked'} and y[idx]==8 else 'Inspect source availability; no inferred hidden cause'))
    for k,name in enumerate(NAMES):source_recovery[name]=dict(matches_on_old_missing=int((nm[:,k]&~ou).sum()),unique_recovery=int((nm[:,k]&~ou&(nm.sum(1)==1)).sum()))
    priority_slot=NAMES.index('priority/P05');assert (new[:,priority_slot,0]==9).all();np.testing.assert_array_equal(new[:,priority_slot,2],np.load(WORK/'validation-priority.npy'))
    assert (new[:,NAMES.index('end'),0]==7).all()
    for row in new:
        outcomes={}
        for c in row:
            if c[0] in (3,8):outcomes.setdefault(int(c[1]),set()).add(int(c[0]))
        assert all(len(v)==1 for v in outcomes.values())
    attribution=dict(per_family=per,lost_support_rows=losses,per_source_on_old_missing=source_recovery,
        invariants=dict(P05_priority_proposed_all_14439_rows=True,end_proposed_all_14439_rows=True,no_destination_duplicated_under_both_outcomes=True,shop_strict_matches=0),
        new_fits=0,reserved_opened=0,source_sha256=digest(__file__))
    immutable_json(REPORT/'C03-attribution.json',attribution)
    files=list(REPORT.glob('C03-*.json'));files=[p for p in files if p.name!='C03-completion.json']
    model_files=[BASE/'runs/M01/model.pt',BASE.parent/'v8/runs/P05/model.pt',BASE.parent/'v9/runs/G00/model.pt']
    immutable_json(REPORT/'C03-completion.json',dict(
        commands=['python -m unittest tools.action_predictor.test_proposal_generator','python -m tools.action_predictor.proposal_study train','python -m tools.action_predictor.proposal_study validation','python -m tools.action_predictor.proposal_roundtrip','python -m tools.action_predictor.proposal_analysis'],
        cwd=str(ROOT),interpreter=str(ROOT/'.venv-action-predictor/Scripts/python.exe'),
        reports={str(p.relative_to(ROOT)):digest(p) for p in files},
        models={str(p.relative_to(ROOT)):digest(p) for p in model_files},
        local_outputs={str(p.relative_to(ROOT)):digest(p) for p in WORK.glob('*.npy')},
        analysis_source_sha256=digest(__file__),new_fits=0,new_selector_checkpoint=None,achieved_accuracy_change=None,
        claims='Generator repair and oracle coverage only. Not a promoted complete predictor. Old A00/G00/P05 results unchanged. Full TRAIN bridge/priority diagnostic plus24-game TRAIN geometry cohort, then all original DEV. Both reserved75-game partitions sealed; no matches/downloads/deployment.',
        missing_shop_arguments='All43DEV original purchase commands remain unavailable/unassessed strict failures.',
        qualifications='Unit-coordinate agreement cannot uniquely certify original entity identity. Full engine legality unassessed. Sparse altar/teleport/submit uncertified. No unchanged495-game extraction audit repeated.'))
    print(json.dumps(dict(per_family=per,losses=losses),indent=2))

if __name__=='__main__':run()
