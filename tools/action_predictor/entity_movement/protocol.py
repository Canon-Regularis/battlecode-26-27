"""Freeze one matched pair before optimization; preserve earlier experiments."""
import json
import subprocess
import sys
import torch
from ..segment_policy.protocol import retained_inputs
from ..segment_policy.data import ROOT
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files, reject_optimized_python
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from .model import EntityMovementPolicy

WORK = ROOT / '.cambc/action-predictor/v31'
REPORT = ROOT / 'tools/action_predictor/experiments/v31'
SEED = 20261130
ARMS = {'E00': 'candidate-independent entity attention', 'E01': 'candidate-conditioned entity attention'}
TESTS = ['tools.action_predictor.entity_movement.test_model',
         'tools.action_predictor.entity_movement.test_entry',
         'tools.action_predictor.segment_policy.test_history']


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT, dependency_files(ROOT,
        ('tools.action_predictor.entity_movement.fit', *TESTS)))


def freeze():
    commit, sources = source_gate()
    inputs = retained_inputs()
    for name in ('H01-review-response.json', 'H01.json', 'H01-component-analysis.json', 'H01-matched-analysis.json'):
        path = ROOT/'tools/action_predictor/experiments/v30'/name
        inputs[str(path.relative_to(ROOT))] = digest(path)
    parameters = {}
    for arm in ARMS:
        rt.setup(SEED)
        teacher, _ = load_base()
        model = EntityMovementPolicy(teacher, arm == 'E01')
        parameters[arm] = dict(trainable=sum(p.numel() for p in model.parameters() if p.requires_grad),
                              total=sum(p.numel() for p in model.parameters()))
    if parameters['E00'] != parameters['E01']: raise RuntimeError('Unmatched parameter counts')
    immutable_json(REPORT/'protocol.json', dict(source_commit=commit, sources=sources, inputs=inputs,
        seed=SEED, arms=ARMS, parameters=parameters,
        hypothesis='Entity-to-destination relationships may improve movement execution beyond global entity pooling. This is not persistent entity grounding or proof of learned strategic intent.',
        common='Fresh identical M01-derived HistorySegmentPolicy initialization; trainable observation/history/shared execution and hierarchy. Same new32-dimensional query/key/value layers and96to32to1movement residual; zero final layer. Same active parameter shapes. Entities are current known119fieldtokens, with maskedzero null token. No IDs, future targets or new replay inputs.',
        contrast='E01 adds each candidate embedding to its attention query; E00 adds the mean valid candidate embedding to one query shared across destinations. Both score each destination from candidate embedding, attended entity values and state context. Residual is applied before the unchanged restricted/full-support mixture, only to move family8 tiles; special buckets and other heads retain their formula.',
        training=dict(rows=433071, validation_rows=14439, actor_batch=32, unroll=8,
            optimizer='AdamW', lr=.0003, weight_decay=.01, clip=5, max_rounds=35, patience=6,
            selection='Full original DEV command NLL, min improvement0.0001; round0 never selectable',
            loss='Original normalized observed complete-command likelihood; no weighting or auxiliary targets',
            sequence='Identical actual-root gap resets, command assimilation after prediction, same actor-stream permutation seeded20261130'),
        evaluation='Retain every original row and category, conditional and joint commands, movement continuation/change/blocked, false positives, macroF1, targeting, commandNLL, group-bootstrap and genuine consecutive windows. Assess natural/augmentedTRAIN separately as in-sample. Compare both arms with G00/L02/JP02; E01 also againstE00. Keep every regression.',
        exploratory_gate=dict(joint_move_gain=24, joint_change_gain=12, lower_full_DEV_NLL=True,
            max_continuation_loss_percentage_points=.5, original_targeting_and_category_guards=True,
            note='All conditions required against E00; stronger retained references remain binding. Original reliability and three-seed targets unchanged. No promotion from single-seed reusedDEV.'),
        restrictions='One fit per invocation. Fresh independent postfit review before next arm. Both reserved75gamepartitions sealed. No matches/downloads/runtime/deployment. Immutable prior artifacts.',
        new_fits=0, reserved_opened=0))


def preflight(arm):
    if arm not in ARMS: raise ValueError('Unknown experiment arm')
    commit, sources = source_gate()
    path = REPORT/'protocol.json'
    plan = json.loads(path.read_text())
    if sources != plan['sources']: raise RuntimeError('Frozen source closure changed')
    for key, expected in plan['inputs'].items():
        if digest(ROOT/key) != expected: raise RuntimeError('Frozen input changed: '+key)
    gate = dict(source_commit=commit, sources=sources, protocol_sha256=digest(path))
    if arm == 'E01':
        review_path = REPORT/'E00-review-response.json'
        review = json.loads(review_path.read_text())
        result_path = REPORT/'E00.json'
        result = json.loads(result_path.read_text())
        if (review['verdict'] != 'APPROVE' or not review['review_task_id'] or
                review['result_sha256'] != digest(result_path) or
                review['checkpoint_sha256'] != result['checkpoint_sha256']):
            raise RuntimeError('Fresh matched-control review is unresolved')
        prediction = WORK/'runs/E00/validation-predictions.npz'
        key = str(prediction.relative_to(ROOT))
        if digest(prediction) != result['bindings'][key]: raise RuntimeError('Control predictions changed')
        gate['matched_direct_control'] = {key: digest(prediction),
            str(result_path.relative_to(ROOT)): digest(result_path),
            str(review_path.relative_to(ROOT)): digest(review_path)}
    test = subprocess.run([sys.executable, '-m', 'unittest', *TESTS, '-v'], cwd=ROOT,
                          capture_output=True, text=True)
    if test.returncode: raise RuntimeError('Prerequisite tests failed: '+test.stdout+test.stderr)
    gate.update(prerequisite_stdout=test.stdout, prerequisite_stderr=test.stderr)
    return plan, gate


if __name__ == '__main__': freeze()
