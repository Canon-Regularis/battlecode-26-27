"""No-fit verification and training-only priority vocabulary diagnostics."""
from collections import Counter
import json
from pathlib import Path
import sys
import subprocess
import numpy as np
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_inputs import FIELDS
from . import reliable_train as rt

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def run():
    from .priority_verify import verify
    verify() # Full chain + independent reconstruction + exact merged slices, before statistics.
    from .observation_study import freeze_plan
    freeze_plan()
    old_lock=read(ROOT/'tools/action_predictor/experiments/v7/execution-lock.json')
    for path,digest in old_lock['preserved_checkpoints'].items():assert sha(path)==digest
    for path,digest in old_lock['training_sources'].items():assert sha(path)==digest
    old_report=read(ROOT/'tools/action_predictor/experiments/v7/report-provenance.json')
    for name,digest in old_report['outputs'].items():assert sha(ROOT/'tools/action_predictor/experiments/v7'/name)==digest
    for identifier in ('H01','H02'):
        saved=read(ROOT/'tools/action_predictor/experiments/v7'/(identifier+'.json'))
        assert sha(ROOT/'.cambc/action-predictor/v7/runs'/identifier/'model.pt')==saved['checkpoint_sha256']
    ready=read(REPORTS/'priority-data-ready.json');plan=read(REPORTS/'priority-extraction-plan.json')
    for path,digest in plan['sources'].items():assert sha(path)==digest,path
    jobs=read(ROOT/'.cambc/action-predictor/v7/jobs.json');assert len(jobs)==495
    totals=Counter();engines={};receipt_inputs={}
    for job in jobs:
        raw=job['record']['raw_sha256'];directory=WORK/'priority'/raw;receipt=read(directory/'receipt.json')
        assert sha(directory/'receipt.json')==ready['receipts'][raw]
        for name,digest in receipt['files'].items():assert sha(directory/name)==digest
        assert receipt['rows']==job['rows'] and receipt['streaming_index_parity']
        stats=receipt['audit_only'];key=receipt['engine'];engines.setdefault(key,Counter())
        for name in ('setters','unchanged_setters','post_scheduled_matches','rollovers','rollover_mismatches'):
            totals[name]+=stats[name];engines[key][name]+=stats[name]
        receipt_inputs[raw]=sha(directory/'receipt.json')
    assert totals['setters']==totals['post_scheduled_matches']
    summary={};training_values=None;diagnostic_inputs={}
    for split,path in [('train',ROOT/'.cambc/action-predictor/v5/combined-train.npz'),('validation',ROOT/'.cambc/action-predictor/v4/validation.npz')]:
        with np.load(path) as z:y,labels=z['y'],z['priority']
        assert np.isfinite(labels).all() and np.array_equal(labels,labels.astype(np.int64))
        diagnostic_inputs[str(path)]=sha(path)
        source=WORK/('priority-'+split+'.npz');assert sha(source)==ready['files'][split]
        with np.load(source) as z:v,h,outside=z['values'],z['history'],z['last_outside_window']
        assert v.dtype==np.int64 and h.dtype==np.int64 and v.shape==(len(y),len(FIELDS)) and h.shape==(len(y),16,2)
        assert np.isin(v[:,[1,3,5]],[0,1]).all() and np.isin(h[:,:,1],[0,1]).all()
        assert (v[:,6]>=0).all() and np.array_equal(outside,(v[:,5]>0)&~h[:,:,1].any(-1))
        mask=y==rt.LABELS.index('priority');target=labels[mask].astype(np.int64);selected=v[mask]
        current=selected[:,1]>0;scheduled=selected[:,3]>0;last=selected[:,5]>0
        if split=='train':training_values=set(map(int,target))
        unseen=sorted(set(map(int,target))-training_values)
        summary[split]=dict(rows=len(y),priority_support=int(mask.sum()),
            current_available=int(current.sum()),scheduled_available=int(scheduled.sum()),last_available=int(last.sum()),
            last_outside16=int(outside[mask].sum()),current_copy_correct=int(((selected[:,0]==target)&current).sum()),
            scheduled_copy_correct=int(((selected[:,2]==target)&scheduled).sum()),last_copy_correct=int(((selected[:,4]==target)&last).sum()),
            target_min=int(target.min()),target_max=int(target.max()),distinct_target_values=len(set(map(int,target))),
            unseen_training_values=unseen,unseen_training_value_rows=int(np.isin(target,unseen).sum()),
            missing_current_rows=int((v[:,1]==0).sum()),missing_scheduled_rows=int((v[:,3]==0).sum()),
            round_gap_histogram=dict(Counter(map(int,selected[last,6]))))
        if split=='train':
            # Only training labels determine vocabulary and residual modes.
            frozen(REPORTS/'priority-training-vocabulary.json',dict(values=sorted(training_values),
                absolute_counts=dict(Counter(map(int,target))),
                residual_from_current=dict(Counter(map(int,target[current]-selected[current,0]))),
                residual_from_scheduled=dict(Counter(map(int,target[scheduled]-selected[scheduled,2]))),
                residual_from_last=dict(Counter(map(int,target[last]-selected[last,4]))),
                training_only=True,source_sha256=sha(path)))
    from .observation_validate import sealed_audit
    # The existing helper checks v7 caches; additionally forbid any V8 reserved cache.
    reserved_audit=sealed_audit()
    membership=read(ROOT/'tools/action_predictor/experiments/v5/membership.json')
    for record in membership['records']:
        if record['split']!='train':assert not (WORK/'priority'/record['raw_sha256']).exists()
    assert {p.name for p in (WORK/'priority').iterdir() if p.is_dir()}==set(receipt_inputs)
    command=[sys.executable,'-m','unittest','tools.action_predictor.test_priority_inputs','tools.action_predictor.test_priority_verify','-v']
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(argv=command))+'\n')
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    (WORK/'priority-tests.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0,result.stderr
    frozen(REPORTS/'priority-recovery-audit.json',dict(passed=True,split_summary=summary,engine_audits=engines,
        all_target_rows_retained=True,all_game_index_streaming_input_roundtrips=True,
        setter_semantics=dict(total_counts=totals,
            interpretation='Counted recorded roots only. Absence of unchanged setter events is not proof that underlying setter calls are never made. No game actions or branches were run.'),
        rollover_reset_diagnostics='Mismatch counts retained for investigation; do not silently rewrite values or infer resets.',
        old_studies_unchanged=True,reserved_audit=reserved_audit,new_reserved_priority_caches=0,
        input_hashes=diagnostic_inputs,receipt_hashes=receipt_inputs,
        plan_sha256=sha(REPORTS/'priority-extraction-plan.json'),data_ready_sha256=sha(REPORTS/'priority-data-ready.json'),
        tests_sha256=sha(WORK/'priority-tests.log'),audit_source_sha256=sha(__file__),
        chain_verification_sha256=sha(REPORTS/'priority-chain-verification.json'),
        validator_source_sha256=sha(Path(__file__).with_name('priority_verify.py')),
        test_source_sha256={name:sha(Path(__file__).with_name(name)) for name in ('test_priority_inputs.py','test_priority_verify.py')},new_training_fits=0))
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.priority_audit'],source_sha256=sha(__file__)))+'\n')
    print(json.dumps(summary,indent=2));print('Priority recovery audited; no fits',flush=True)

if __name__=='__main__':run()
