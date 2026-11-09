"""Immutable matched study; review gates precede every optimizer invocation."""
import json
import subprocess
import sys
from .data import ROOT,WORK as DATA_WORK,REPORT as DATA_REPORT,LEGACY_FILES
from .model import Policy
from .engine import ARMS
from ..audit import immutable_json
from ..data import digest
from ..reliable_train import setup
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

WORK=ROOT/'.cambc/action-predictor/v33'
REPORT=ROOT/'tools/action_predictor/experiments/v33'
SEED=20261109
TESTS=('tools.action_predictor.history_horizon.test_contract',
       'tools.action_predictor.trajectory_history.test_audit',
       'tools.action_predictor.trajectory_history.test_windows',
       'tools.action_predictor.trajectory_history.test_features',
       'tools.action_predictor.trajectory_history.test_reference')


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.history_horizon.fit',
        'tools.action_predictor.history_horizon.probe',*TESTS)))


def freeze():
    commit,sources=source_gate();manifest=json.loads((DATA_REPORT/'assembly.json').read_text())
    inputs={}
    def bind(p):inputs[str(p.relative_to(ROOT))]=digest(p)
    for name in ('assembly.json','assembly-plan.json','assembly-review.json','astra-research.json'):
        bind(DATA_REPORT/name)
    bind(REPORT/'construction-probe.json')
    review=json.loads((DATA_REPORT/'assembly-review.json').read_text())
    if review['verdict']!='APPROVE' or review['assembly_sha256']!=digest(DATA_REPORT/'assembly.json'):
        raise ValueError('Assembly review is not bound')
    bind(DATA_WORK/'normalizer.npz')
    if digest(DATA_WORK/'normalizer.npz')!=manifest['normalizer_sha256']:raise ValueError('Normalizer changed')
    for g in manifest['games']:
        for name,key in (('data.npz','arrays_sha256'),('rows.json','row_identity_sha256')):
            p=DATA_WORK/'games'/g['payload']/name
            if digest(p)!=g[key]:raise ValueError('Assembly changed')
            bind(p)
    for name in LEGACY_FILES:bind(ROOT/'.cambc/action-predictor'/name)
    bind(ROOT/'.cambc/action-predictor/data/dataset.json')
    references=json.loads((ROOT/'tools/action_predictor/experiments/v30/H01-matched-analysis-plan.json').read_text())['references']
    references={k:references[k] for k in ('G00','L02','JP02')}
    for reference in references.values():
        p=ROOT/reference['path']
        if digest(p)!=reference['sha256']:raise ValueError('Historical reference changed')
        bind(p)
    setup(SEED);model=Policy()
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=sources,inputs=inputs,
        seed=SEED,arms=ARMS,parameters=sum(p.numel() for p in model.parameters()),references=references,
        hypothesis='B minus A tests extra recurrent carry beyond the shared explicit16root history. C minus B tests gradient horizon within this training configuration. No Fish intent or playing-strength identification.',
        input_contract='Current253, sanitized last16commands24, normalized/remasked last16observations253 and availability5, earlier priority argument3derivedfields, candidate geometry/rules. Root gap and actor-start ONLY reset state. No learned group, actor, ordinal, event, current command or target direction.',
        model='Fresh direct GRU memory28 with trainable JointModel execution and observed-command assimilation AFTER prediction; no pretrained weights, entity/goal modules, future targets or auxiliary losses. Both priority and spatial execution train from fit groups only.',
        training=dict(fit_rows=65465,tuning_rows=15298,assessment_rows=16389,actor_batch=32,
            optimizer_window=32,rounds=12,optimizer='AdamW',lr=.0003,weight_decay=.01,clip=5,
            loss='Unweighted sum of observed modeled-command NLL divided by all nonpadding rows in the same32node window; A/B backward every8, C every32, one optimizer step per window.',
            sampling='Same seeded actor-stream permutations; each fitting row exactly once each round. All actual omitted-root gaps and actor starts reset all arms; A also resets after8 consecutive assimilated roots. State starts empty each epoch and evaluation.',
            selection='Primary equal-weight continuation/change jointNLL; secondary full modeled-command NLL, tuning only, same12 checkpoints, earliest exact ties. Both reported; no selector switching. Shop purchase arguments absent from likelihood, strictshopaccuracy always0.'),
        evaluation='Archive selected fit/tuning/assessment/legacy forecasts before scoring. All categories, conditional and joint movement, changes/continuation/blocked, false positives, macroF1, paired2000wholegroup intervals/leaveonegroupout and genuine16/32root windows. Original14439DEV and G00/L02/JP02 are secondary historical regressions; different training exposure prevents a causal reference contrast.',
        allocation_gate=dict(move_gain=.01,change_gain=.01,continuation_loss=.005,lower_balanced_move_nll=True,
            full_nll_max_increase=.005,complete_loss_strictly_less_than=.002,targeting_loss_strictly_less_than=.02,
            other_supported_category_loss_max=.02,macro_F1_no_loss=True,
            note='All required on assessment primary selector for matched contrasts; secondary selector and legacy regressions remain visible. No promotion: original reliability/three-seed/runtime requirements unchanged.'),
        limits='Availability-enriched, previously exposed research groups. Actual past commands supplied. Missing shops/entity identity/fulllegality/outcome validation remain. Window agreement is teacher-forced imitation, not strategic intent or autonomous play.',
        budget='One matched seed, three single-arm invocations, exactly12rounds each; no automatic repeats or extra seeds.24machinehours total, abort preserving all artifacts on exhaustion. Fresh independent prefit and after-each-fit review required.',
        restrictions='Reserved75+75sealed; no matches/downloads/runtime/deployment/merge. No model promotion.',new_fits=0))


def checked_review(path,protocol_sha,result_path=None):
    review=json.loads(path.read_text())
    if review['verdict']!='APPROVE' or not review['review_task_id'] or review['protocol_sha256']!=protocol_sha:
        raise ValueError('Unresolved independent review: '+str(path))
    bindings={str(path.relative_to(ROOT)):digest(path)}
    if result_path is not None:
        if review['result_sha256']!=digest(result_path):raise ValueError('Reviewed result changed')
        result=json.loads(result_path.read_text())
        if result['protocol_sha256']!=protocol_sha:raise ValueError('Control protocol changed')
        for key,expected in result['bindings'].items():
            if digest(ROOT/key)!=expected:raise ValueError('Reviewed run changed: '+key)
        bindings[str(result_path.relative_to(ROOT))]=digest(result_path)
    return bindings


def preflight(arm):
    if arm not in ARMS:raise ValueError('Unknown arm')
    commit,sources=source_gate();path=REPORT/'protocol.json';plan=json.loads(path.read_text());sha=digest(path)
    if sources!=plan['sources']:raise ValueError('Frozen source closure changed')
    for key,expected in plan['inputs'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Frozen input changed: '+key)
    reviews=checked_review(REPORT/'prefit-review.json',sha)
    elapsed=0.
    for previous in {'A':[],'B':['A'],'C':['A','B']}[arm]:
        result_path=REPORT/f'{previous}.json'
        reviews.update(checked_review(REPORT/f'{previous}-review.json',sha,result_path))
        elapsed+=json.loads(result_path.read_text())['seconds']
    if elapsed>=86400:raise ValueError('Study compute budget exhausted')
    test=subprocess.run([sys.executable,'-m','unittest',*TESTS,'-v'],cwd=ROOT,capture_output=True,text=True)
    if test.returncode:raise RuntimeError('Contract tests failed: '+test.stdout+test.stderr)
    return plan,dict(source_commit=commit,protocol_sha256=sha,review_bindings=reviews,
        prior_seconds=elapsed,tests_stdout=test.stdout,tests_stderr=test.stderr)


if __name__=='__main__':freeze()
