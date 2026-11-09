"""V8 entry audit and frozen category-wise objective. No fits or replay decoding."""
import json
from pathlib import Path
import sys
import numpy as np
from . import reliable_train as rt
from .more_replays import ROOT,sha,frozen
from .observation_metrics import correctness

WORK=ROOT/'.cambc/action-predictor/v8'
REPORTS=ROOT/'tools/action_predictor/experiments/v8'

def run():
    WORK.mkdir(parents=True,exist_ok=True);REPORTS.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.cambc/action-predictor/diagnostics/M01-error-audit-20261106.json'
    supplied=json.loads(source.read_text())
    for path,digest in supplied['sources'].items():assert sha(path)==digest,path
    with np.load(ROOT/'.cambc/action-predictor/v4/validation.npz') as z:raw={k:z[k] for k in z.files}
    prediction_path=ROOT/'.cambc/action-predictor/v5/runs/M01/validation-predictions.npz'
    with np.load(prediction_path) as z:pred={k:z[k] for k in z.files}
    parameter,joint=correctness(raw,pred);y=raw['y'];p=pred['prediction'];labels=rt.LABELS
    wrong=p!=y;unknown=(p==y)&(y==labels.index('shop'))
    bad_parameter=(p==y)&~parameter&~unknown
    accounting=dict(rows=len(y),strict_failures=int((~joint).sum()),wrong_action_type=int(wrong.sum()),
        wrong_parameter_with_correct_type=int(bad_parameter.sum()),unassessed_shop_with_correct_type=int(unknown.sum()))
    for key,value in accounting.items():assert value==supplied['accounting'][key],key
    assert np.array_equal(~joint,wrong|bad_parameter|unknown)
    assert len(supplied['errors'])==int((~joint).sum())
    assert {r['validation_row'] for r in supplied['errors']}==set(np.flatnonzero(~joint))
    for row in supplied['errors']:
        i=row['validation_row'];assert row['actual_action']==labels[y[i]] and row['predicted_action']==labels[p[i]]
        assert ('parameter' in row['primary_failure'])==bool(bad_parameter[i])
        assert (row['primary_failure']=='wrong_action_type')==bool(wrong[i])
        if row['conditional_parameter_correct'] is not None:
            assert row['conditional_parameter_correct']==bool(parameter[i])
    per_action=[]
    for i,name in enumerate(labels):
        mask=y==i;n=int(mask.sum())
        if not n:continue
        entry=dict(action=name,support=n,strict_correct=int(joint[mask].sum()),failures=int((mask&~joint).sum()),
            joint_correctness=float(joint[mask].mean()),wrong_type=int((mask&wrong).sum()),
            wrong_parameter=int((mask&bad_parameter).sum()),unassessed=int((mask&unknown).sum()),
            false_positives=int(((p==i)&~mask).sum()))
        saved=next(r for r in supplied['per_action'] if r['action']==name)
        assert entry['failures']==saved['strict_failures'] and entry['false_positives']==saved['false_positives']
        per_action.append(entry)
    direction=np.load(ROOT/'.cambc/action-predictor/v7/validation-direction.npy')
    move=y==labels.index('move');move_errors=move&~parameter
    blocked=p==labels.index('blocked');success=p==labels.index('move');c=pred['proposed_coordinate']
    def move_flags(mask):
        idx=np.flatnonzero(mask);inside=c[idx]<289
        return int((~inside).sum()+(~raw['move_mask'][idx[inside],c[idx[inside]]]).sum())
    invalid=rt.invalid_rate(raw,pred)
    assert invalid['invalid']==109 and move_flags(blocked)==92 and move_flags(success)==0
    assert move_errors.sum()==958 and (move_errors&(direction==3)).sum()==881
    priority=y==labels.index('priority');ward=p==labels.index('ward')
    assert joint[priority].sum()==10 and priority.sum()==576
    assert ward.sum()==317 and ((y==labels.index('recall'))&ward).sum()==257
    frequencies={}
    for name,paths in [('natural',['v4/train.npz','v5/train.npz']),('augmented',['v5/combined-train.npz'])]:
        counts=np.zeros(len(labels),np.int64)
        for path in paths:
            with np.load(ROOT/'.cambc/action-predictor'/path) as z:counts+=np.bincount(z['y'],minlength=len(labels))
        frequencies[name]=dict(zip(labels,map(int,counts)))
    principal=sum(r['failures'] for r in per_action if r['action'] in ('move','recall','priority'))
    result=dict(audit_sha256=sha(source),accounting=accounting,per_action=per_action,
        principal_failure_share=principal/accounting['strict_failures'],movement_errors=958,direction_change_movement_errors=881,
        priority_joint_correct=10,priority_support=576,predicted_wards=317,recall_to_ward=257,
        partial_legality=invalid,blocked_flags=92,successful_move_mask_flags=0,training_frequencies=frequencies,
        source_hashes=supplied['sources'],audit_independently_reproduced=True)
    frozen(REPORTS/'entry-audit.json',result)
    frozen(REPORTS/'success-definition.json',dict(schema=8,created_before_new_fitting=True,
        objective='At least 90% joint correctness in EVERY recorded action category, separately, on each of three training seeds. Overall accuracy is never the criterion.',
        categories=[name for name in labels if name!='<unknown>'],
        joint='Correct action type AND every required reliably recorded parameter: exact coordinate/destination/target, exact integer priority, and original shop item/count when available. Unsupported/missing arguments remain explicit failures/unassessed in the unchanged denominator, never correct.',
        support={r['action']:r['support'] for r in per_action},validation_rows=14439,
        evidence='Report category precision/recall/F1, false positives, conditional parameter accuracy, joint loss, partial/full legality coverage and paired whole-group uncertainty. Three seed consistency is required. Two examples cannot certify reliability; report sparse categories as uncertified even if empirical accuracy reaches 100%.',
        uncertainty='2000 paired resamples of all five original development groups, fixed seed20261106, support/empty draws explicit. Intervals condition on selected checkpoints, not selection-adjusted.',
        preserved='All original v4-v7 studies, checkpoint hashes, splits, all rows and original regression guards remain intact; new outputs only under v8.',
        reserved='Do not open/decode any of the75 new validation or75 final-test games; no downloads, matches, playing-bot modifications or deployment.',
        fit_registration='Before every fit, freeze configuration, hypothesis, control, dataset/code hashes, support, losses, checkpoint rule and seeds. Isolate inputs, sampling/losses and architectures in separate comparisons. Do not repeat identical failed designs indefinitely.',
        order=['Recover observable priority/current/scheduled/previous argument evidence and original purchase-command availability',
               'Isolated priority copy/residual/discrete full-support designs preserving other paths',
               'Natural-frequency and corrected-weight controls, difficult recall/ward/priority discrimination without blanket suppression',
               'Separate movement branch and richer causal entity/public geometry inputs; then recorded continuation/change auxiliary and emphasis',
               'Ward coverage/location; cast identity/unit-ground targeting; end/cancel semantics; blocked attempted outcomes; objective interactions'],
        reviews='Fresh GPT-6.1 Sol xhigh after every meaningful completed implementation/analysis milestone and every completed fit; exact user question; review full thread, code/protocol/predictions/objections. No later work covered by an earlier review.',
        stopping='Continue while distinct evidence-backed experiments can improve categories. If command evidence, private state, randomness or insufficient support demonstrates an irreducible gap, report it exactly without claiming success.',
        delivery='DRAFT PR only, open/unmerged, no auto-merge/merge queue. User draft override supersedes skill defaults.'))
    with (WORK/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.category_study'],code_sha256=sha(__file__)))+'\n')
    print(json.dumps(accounting));print('Audit reproduced; success definition frozen; new fits:0')

if __name__=='__main__':run()
