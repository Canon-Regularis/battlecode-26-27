"""Frozen matched routing protocol; actual reviews gate each separate fit."""
import json
import subprocess
import sys
from .data import ROOT,WORK,REPORT,DATA_WORK,DATA_REPORT
from .engine import ARMS
from ..history_horizon.model import Policy
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

SEED=27
TESTS=('tools.action_predictor.gradient_routing.test_contract',
       'tools.action_predictor.movement_diagnosis.test_audit',
       'tools.action_predictor.history_horizon.test_contract')


def sources():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.gradient_routing.fit',
        'tools.action_predictor.gradient_routing.probe',*TESTS)))


def freeze():
    commit,code=sources();bindings={}
    def bind(p):bindings[str(p.relative_to(ROOT))]=digest(p)
    selection=json.loads((REPORT/'selection.json').read_text())
    from . import data
    if not selection['passed'] or selection['source_sha256']!=digest(data.__file__):raise ValueError('Window inventory changed')
    for key,expected in selection['bindings'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Window input changed')
        bindings[key]=expected
    manifest=json.loads((DATA_REPORT/'assembly.json').read_text())
    for game in manifest['games']:
        if game['partition']!='fit':continue
        p=DATA_WORK/'games'/game['payload']/'data.npz'
        if digest(p)!=game['arrays_sha256']:raise ValueError('Fitting arrays changed')
        bind(p)
    for p in (DATA_WORK/'normalizer.npz',REPORT/'selection.json',REPORT/'astra-research.json',REPORT/'construction-probe.json',
              ROOT/'tools/action_predictor/experiments/v35/U01-review.json',
              ROOT/'tools/action_predictor/experiments/v35/U01.json',
              ROOT/'tools/action_predictor/experiments/v34/diagnostic-r2.json',
              ROOT/'tools/action_predictor/experiments/v9/D02-REPORT.md',
              ROOT/'.cambc/action-predictor/data/dataset.json'):bind(p)
    review=json.loads((ROOT/'tools/action_predictor/experiments/v35/U01-review.json').read_text())
    if review['verdict']!='APPROVE' or review['result_sha256']!=digest(ROOT/'tools/action_predictor/experiments/v35/U01.json'):
        raise ValueError('Completed cadence result review changed')
    probe=json.loads((REPORT/'construction-probe.json').read_text())
    for key,expected in probe['bindings'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Construction archive changed')
        bindings[key]=expected
    setup(SEED);model=Policy()
    if sum(p.numel() for p in model.parameters())!=139292:raise ValueError('Architecture changed')
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=code,inputs=bindings,seed=SEED,
        arms=ARMS,parameters=139292,selection_sha256=digest(REPORT/'selection.json'),
        question='Does simultaneous projection of conflicting change/continuation coordinate gradients improve fitting movement without sacrificing continuation and other commands?',
        rationale='D02 measured negative cosines in an earlier model, not this model. V35 failed movement guards. Neither proves interference causes the current errors.',
        common='Fresh identical seed27 Policy weights and empty AdamW. Unchanged 139292 parameters, inputs, fit-only normalizer, support mixture, joint MAP and observed-command assimilation. All three loss gradients computed in both arms. Reset/detach every eight roots, one update per 32-root by up-to-32-lane batch.',
        loss_partition='Change coordinate NLL, continuation coordinate NLL, and every remaining original NLL term. Each sum divided by actual nonpadding batch rows (1024 or928), never stratum counts. Direction is training partition metadata only.',
        treatment='R00 sums the three accumulated gradient vectors. R01, iff dot(D,C)<0 and both norms positive, simultaneously uses D-dot*C/normC^2 and C-dot*D/normD^2 from the ORIGINAL vectors, plus R. Dot/norm and projection arithmetic float64 then cast float32. Zero unused coordinates; wholly unused parameters retain grad=None. Clip global norm5 then AdamW lr0.0003 decay0.01. Changes direction and magnitude; not an unchanged scalar-objective or continuation-protection guarantee.',
        population=dict(groups=40,windows=1085,rows=34720,strata=selection['strata'],category_counts=selection['category_counts'],
            note='All existing contiguous32 fitting windows, canonical order. No substitution or target-based selection; no tuning, assessment, originalDEV or reserved payload loading.'),
        budget=dict(arms=2,passes=8,row_presentations_per_arm=277760,updates={'R00':272,'R01':272},
            batches_per_pass=34,last_batch_rows=928,combined_seconds=7200,
            selection='Final pass8 only; initial reference, online loss never selects. Incomplete pair inconclusive. No restarts, extensions or repeats.'),
        diagnostic_allocation=dict(change_complete_gain=.05,move_complete_gain=.01,max_continuation_loss=.005,
            change_coordinate_nll_reduction=.15,change_within_alternative_nll_reduction=.05,lower_balanced_joint_nll=True,
            max_full_nll_increase=.005,max_complete_loss=.002,max_macro_F1_loss=.01,
            max_attack_cast0_cast1_conditional_and_complete_loss=.02,absent_targeting_category_fails=True,
            max_move_false_positive_rate_increase=.002,change_accuracy_and_coordinate_nll_favorable_every_leave_one_group_out=True),
        evaluation='All command categories, targeting, false positives, change/continue coordinate probability decomposition, paired groups/windows, conflict frequencies/norms and clipping. Fitting-only diagnostics; no gradient metric can override failed behavior gates.',
        gates='Actual independent Sol prefit approval before R00, actual R00 postfit approval before R01, then fresh R01 review. Passing only warrants a separately reviewed transfer experiment.',
        limits='One fresh seed on exposed fitting windows, teacher-forced history, missing shops, ambiguous targets, incomplete legality/newPOST validation. Strong references, category90percent, reliability and3seed requirements remain. No strategy, intent, playing-strength or promotion claim.',new_fits=0))


def preflight(arm):
    if arm not in ARMS:raise ValueError('Unknown arm')
    commit,code=sources();path=REPORT/'protocol.json';plan=json.loads(path.read_text());sha=digest(path)
    if code!=plan['sources']:raise ValueError('Frozen source closure changed')
    for key,expected in plan['inputs'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Frozen input changed: '+key)
    reviews={};prior=0.
    for name in ['prefit']+(['R00'] if arm=='R01' else []):
        p=REPORT/f'{name}-review.json';r=json.loads(p.read_text())
        if r['verdict']!='APPROVE' or not r['review_task_id'] or r['protocol_sha256']!=sha:raise ValueError('Unresolved independent review')
        reviews[str(p.relative_to(ROOT))]=digest(p)
        if name=='R00':
            p=REPORT/'R00.json';result=json.loads(p.read_text())
            if r['result_sha256']!=digest(p) or result['protocol_sha256']!=sha:raise ValueError('Reviewed control changed')
            for key,expected in result['bindings'].items():
                if digest(ROOT/key)!=expected:raise ValueError('Control archive changed')
            reviews[str(p.relative_to(ROOT))]=digest(p);prior=result['seconds']
    if prior>=7200:raise ValueError('Diagnostic budget exhausted')
    tests=subprocess.run([sys.executable,'-m','unittest',*TESTS,'-v'],cwd=ROOT,capture_output=True,text=True)
    if tests.returncode:raise RuntimeError(tests.stdout+tests.stderr)
    return plan,dict(source_commit=commit,protocol_sha256=sha,review_bindings=reviews,prior_seconds=prior,
        tests_stdout=tests.stdout,tests_stderr=tests.stderr)


if __name__=='__main__':freeze()
