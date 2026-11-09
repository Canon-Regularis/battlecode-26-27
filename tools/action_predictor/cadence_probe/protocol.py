"""Separate reviewed diagnostic; never expands the completed horizon study."""
import json
import subprocess
import sys
import torch
from .data import ROOT,WORK,REPORT,DATA_WORK,DATA_REPORT
from .engine import ARMS
from ..history_horizon.model import Policy
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

SEED=20261109
INITIAL=ROOT/'.cambc/action-predictor/v33/runs/A/initial.pt'
TESTS=('tools.action_predictor.cadence_probe.test_contract',
       'tools.action_predictor.movement_diagnosis.test_audit',
       'tools.action_predictor.history_horizon.test_contract')


def sources():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.cadence_probe.fit',
        'tools.action_predictor.cadence_probe.probe',*TESTS)))


def freeze():
    commit,code=sources();bindings={}
    def bind(p):bindings[str(p.relative_to(ROOT))]=digest(p)
    selection=json.loads((REPORT/'selection.json').read_text())
    if not selection['passed'] or selection['source_sha256']!=digest(__import__('tools.action_predictor.cadence_probe.data',fromlist=['x']).__file__):
        raise ValueError('Window selection changed')
    for key,expected in selection['bindings'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Selection input changed')
        bindings[key]=expected
    manifest=json.loads((DATA_REPORT/'assembly.json').read_text())
    for game in manifest['games']:
        if game['partition']!='fit':continue
        path=DATA_WORK/'games'/game['payload']/'data.npz'
        if digest(path)!=game['arrays_sha256']:raise ValueError('Fitting data changed')
        bind(path)
    for p in (DATA_WORK/'normalizer.npz',REPORT/'selection.json',REPORT/'astra-research.json',REPORT/'construction-probe.json',
              ROOT/'tools/action_predictor/experiments/v34/diagnostic-r2.json',
              ROOT/'tools/action_predictor/experiments/v34/diagnostic-plan-r2.json',
              ROOT/'tools/action_predictor/experiments/v33/C-review.json',
              ROOT/'tools/action_predictor/experiments/v33/A.json',
              ROOT/'.cambc/action-predictor/data/dataset.json',INITIAL):bind(p)
    a=json.loads((ROOT/'tools/action_predictor/experiments/v33/A.json').read_text())
    if digest(INITIAL)!=a['bindings'][str(INITIAL.relative_to(ROOT))]:raise ValueError('Initial checkpoint changed')
    setup(SEED);model=Policy();initial=torch.load(INITIAL,map_location='cpu',weights_only=False)
    if not all(torch.equal(v,initial['state'][k]) for k,v in model.state_dict().items()):raise ValueError('Initial checkpoint is not fresh weights')
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=code,inputs=bindings,seed=SEED,
        arms=ARMS,parameters=139292,selection_sha256=digest(REPORT/'selection.json'),
        question='Does smaller-batch more-frequent AdamW updating improve fitting-subset destination learning at identical row exposure? It does not isolate updatecount from gradientnoise,moments or cumulativeweightdecay.',
        common='SameAinitialweights,freshAdamW,current/history/geometryinputs,fit-onlynormalizer,allcommandlabels,exactjointMAP,supportmixture. Both reset/detach every8roots; isolated32rootwindows start at originalAresetboundaries. No learned metadata.',
        treatment='U00 four8rootbackwards divided by1024 rows thenoneupdate; U01 backward/detach/clip/update each8roots divided by256rows before nextsegmentforward. lr.0003,decay.01,clip5 identical.',
        population=dict(groups=40,windows=256,rows=8192,changes=selection['strata']['change'],continuations=selection['strata']['continue'],
            note='Fitting-only deterministichash/roundrobinselection,no resampling,allpresentcategories retained. No tuning/assessment/originalDEV/reserved loading.'),
        budget=dict(arms=2,passes=16,row_presentations_per_arm=131072,updates={'U00':128,'U01':512},
            combined_seconds=7200,selection='Finalpass16only; initialreference,intermediateonlineNLL neverselects. Noextensions/restarts/repeats.'),
        diagnostic_allocation=dict(change_complete_gain=.05,change_coordinate_nll_reduction=.15,
            lower_balanced_joint_nll=True,max_continuation_loss=.01,max_full_nll_increase=.005,max_complete_loss=.002,
            change_coordinate_nll_improves_every_leave_one_group_out=True),
        evaluation='Initial/finalselected-window fullcommand metrics,everycategory,falsepositives,targeting,movementprobabilitydecomposition; pergroupdifferences,clippingfrequency. Fitting statistics only; notgeneralization or strategy.',
        gates='FreshSolprefitreviewmustcovercorrectedV34auditandnewboundaries/normalization. FreshpostfitU00review beforeU01. Passing permits only separatelyreviewed full-population study; no promotion.',
        limits='Exposedseed/subsetmemorization. Originalstrongreference/reliability/90percent/three-seedrequirements remain. Ambiguousentities/missingshops/incompletelegality/newPOSTvalidation.',new_fits=0))


def preflight(arm):
    if arm not in ARMS:raise ValueError('Unknown arm')
    commit,code=sources();path=REPORT/'protocol.json';plan=json.loads(path.read_text());sha=digest(path)
    if code!=plan['sources']:raise ValueError('Frozen source closure changed')
    for key,expected in plan['inputs'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Frozen input changed: '+key)
    reviews={};prior=0.
    for name in ['prefit']+(['U00'] if arm=='U01' else []):
        p=REPORT/f'{name}-review.json';r=json.loads(p.read_text())
        if r['verdict']!='APPROVE' or not r['review_task_id'] or r['protocol_sha256']!=sha:raise ValueError('Unresolved independent review')
        reviews[str(p.relative_to(ROOT))]=digest(p)
        if name=='U00':
            result_path=REPORT/'U00.json';result=json.loads(result_path.read_text())
            if r['result_sha256']!=digest(result_path) or result['protocol_sha256']!=sha:raise ValueError('Reviewed control changed')
            for key,expected in result['bindings'].items():
                if digest(ROOT/key)!=expected:raise ValueError('Control archive changed')
            reviews[str(result_path.relative_to(ROOT))]=digest(result_path);prior=result['seconds']
    if prior>=7200:raise ValueError('Diagnostic budget exhausted')
    tests=subprocess.run([sys.executable,'-m','unittest',*TESTS,'-v'],cwd=ROOT,capture_output=True,text=True)
    if tests.returncode:raise RuntimeError(tests.stdout+tests.stderr)
    return plan,dict(source_commit=commit,protocol_sha256=sha,review_bindings=reviews,prior_seconds=prior,
        tests_stdout=tests.stdout,tests_stderr=tests.stderr)


if __name__=='__main__':freeze()
