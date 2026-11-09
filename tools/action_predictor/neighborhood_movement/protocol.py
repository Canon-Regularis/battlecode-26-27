"""Prospective fitting-only test of neighborhood evidence with a frozen base."""
import json
import subprocess
import sys
import torch
from .model import Policy
from .engine import ARMS
from ..gradient_routing.data import ROOT,load_subset
from ..gradient_routing.protocol import REPORT as PREVIOUS
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

REPORT=ROOT/'tools/action_predictor/experiments/v38'
WORK=ROOT/'.cambc/action-predictor/v38'
BASE=ROOT/'.cambc/action-predictor/v36/runs/R00/round-08.pt'
SEED=27
TESTS=('tools.action_predictor.neighborhood_movement.test_contract',
       'tools.action_predictor.gradient_routing.test_contract',
       'tools.action_predictor.destination_audit.test_audit',
       'tools.action_predictor.movement_diagnosis.test_audit')


def build(arm):
    return Policy(torch.load(BASE,map_location='cpu',weights_only=False)['state'],ARMS[arm])


def sources():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.neighborhood_movement.fit',
        'tools.action_predictor.neighborhood_movement.probe',*TESTS)))


def freeze():
    commit,code=sources();prior=json.loads((PREVIOUS/'protocol.json').read_text());bindings=dict(prior['inputs'])
    for key,expected in prior['sources'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Reference source changed')
    for key,expected in bindings.items():
        if digest(ROOT/key)!=expected:raise ValueError('Reference data changed')
    def bind(p):bindings[str(p.relative_to(ROOT))]=digest(p)
    result=json.loads((PREVIOUS/'R00.json').read_text());review=json.loads((PREVIOUS/'R00-review.json').read_text())
    if review['verdict']!='APPROVE' or review['result_sha256']!=digest(PREVIOUS/'R00.json'):
        raise ValueError('Unreviewed base checkpoint')
    for p in (BASE,ROOT/'.cambc/action-predictor/v36/runs/R00/final-predictions.npz'):
        if digest(p)!=result['bindings'][str(p.relative_to(ROOT))]:raise ValueError('Base archive changed')
        bind(p)
    audit=ROOT/'tools/action_predictor/experiments/v37'
    audit_review=json.loads((audit/'code-review.json').read_text())
    if audit_review['verdict']!='APPROVE' or audit_review['audit_sha256']!=digest(audit/'audit.json'):
        raise ValueError('Unreviewed destination audit')
    for p in (PREVIOUS/'protocol.json',PREVIOUS/'R00.json',PREVIOUS/'R00-review.json',
              PREVIOUS/'R01.json',PREVIOUS/'R01-review.json',audit/'audit.json',audit/'code-review.json',
              REPORT/'design.json',REPORT/'construction-probe.json'):bind(p)
    probe=json.loads((REPORT/'construction-probe.json').read_text())
    for key,expected in probe['bindings'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Construction archive changed')
        bindings[key]=expected
    setup(SEED);model=build('N00')
    counts=dict(total=sum(p.numel() for p in model.parameters()),trainable=sum(p.numel() for p in model.trainable_parameters()))
    if counts!=dict(total=144989,trainable=5697):raise ValueError('Parameter count changed')
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=code,inputs=bindings,seed=SEED,
        arms=ARMS,parameters=counts,base_checkpoint_sha256=digest(BASE),
        question='Does actual local terrain evidence improve movement ranking beyond an equally shaped center-only residual on a fixed reviewed base?',
        common='Frozen R00 pass8 backbone (139292 parameters), same fresh5697 residual parameters, zero final readout, identical initial predictions. Candidate20 and sharedcontext128 in both arms. All original likelihood terms and joint MAP, memory/reset8 and support mixture unchanged. Residual enters movement tile logits BEFORE mixture; special raw logits and nonmovement formulas unchanged.',
        contrast='3x3 patch channels: in-map, blocked-and-in-map, crop-availability. N01 uses actual neighbors from existinggrid; N00 repeats center terrain at available crop slots. Both receive identical crop availability. No entities, new labels, extra source observations, global map encoder or shared-backbone updates.',
        population=dict(rows=34720,windows=1085,groups=40,source='Exact V36 fitting-window subset; all categories retained. No V37 error cohort selection.'),
        optimization='Full modeled-command NLL sum divided by actual whole batch rows (1024 or928), ordinary gradient accumulation over four8-root segments. One AdamW call per32-root batch. Only residual parameters train, lr.0003 decay.01 clip5. Empty movement batches skip backward naturally; frozen schedules require a nonempty movement stratum in every actual optimizer batch.',
        budget=dict(arms=2,passes=8,updates_per_arm=272,row_presentations_per_arm=277760,
            combined_seconds=7200,selector='Finalpass8only; initialreference and onlineNLL cannot select. No repeats, restarts or extensions; incompletepair inconclusive.'),
        gates='All V36 comparison conditions must pass versus BOTH matched N00 and frozen R00 reference: +5ppchanges,+1ppmoves,continuationloss<=.5pp,change-coordinateNLL reduction>=.15,within-alternative reduction>=.05,lowerbalancedNLL,fullNLLincrease<=.005,completecommandloss<=.2pp,macroF1loss<=.01,eachattack/castconditionalANDcomplete loss<=2pp (absentfails),moveFPincrease<=.2pp,changeaccuracy/NLL favorable everygroupdeletion.',
        reviews='Actual Sol xhigh code/prefit approval before N00, actual N00 postfit approval before N01. Negative training-result reviews use Astra high per user instruction. Parent verifies every fit; no automatic next arm.',
        limits='Warm frozen fitting-only backbone and one residual seed. Not comparable as a fresh full-policy training intervention. Passing only allocates a separately reviewed transfer study; original strong-reference/category90/reliability/three-seed and data limitations remain. No strategy, generalization or promotion.',new_fits=0))


def preflight(arm):
    if arm not in ARMS:raise ValueError('Unknown arm')
    commit,code=sources();path=REPORT/'protocol.json';plan=json.loads(path.read_text());sha=digest(path)
    if code!=plan['sources']:raise ValueError('Frozen source closure changed')
    for key,expected in plan['inputs'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Frozen input changed: '+key)
    reviews={};prior_seconds=0.
    for name in ['prefit']+(['N00'] if arm=='N01' else []):
        p=REPORT/f'{name}-review.json';r=json.loads(p.read_text())
        if r['verdict']!='APPROVE' or not r['review_task_id'] or r['protocol_sha256']!=sha:raise ValueError('Actual review required')
        reviews[str(p.relative_to(ROOT))]=digest(p)
        if name=='N00':
            p=REPORT/'N00.json';result=json.loads(p.read_text())
            if r['result_sha256']!=digest(p) or result['protocol_sha256']!=sha:raise ValueError('Reviewed control changed')
            for key,expected in result['bindings'].items():
                if digest(ROOT/key)!=expected:raise ValueError('Control archive changed')
            reviews[str(p.relative_to(ROOT))]=digest(p);prior_seconds=result['seconds']
    if prior_seconds>=7200:raise ValueError('Paired budget exhausted')
    tests=subprocess.run([sys.executable,'-m','unittest',*TESTS,'-v'],cwd=ROOT,capture_output=True,text=True)
    if tests.returncode:raise RuntimeError(tests.stdout+tests.stderr)
    return plan,dict(source_commit=commit,protocol_sha256=sha,review_bindings=reviews,prior_seconds=prior_seconds,
        tests_stdout=tests.stdout,tests_stderr=tests.stderr)


if __name__=='__main__':freeze()
