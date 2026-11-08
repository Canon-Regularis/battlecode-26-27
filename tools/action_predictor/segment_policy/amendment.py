"""Narrow reviewed-control and amended-history prerequisites for H01 only."""
import json
import subprocess
import sys
import torch
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files, reject_optimized_python
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from .data import ROOT, REPORT
from .protocol import SEED
from .history_model import HistorySegmentPolicy

H00_SOURCE = '341ee3413cb680a4ee0ca2c9e7dd1c95b20fed0d'
H00_CHECKPOINT = '6be14700c51bb5f181ae4d5caeddc3acad5de7d74669f9b6b975b4429890b587'
H00_REPORT = '104388aaaf5922b42b7968ad3806489be1bbf3a5da23add432db93e0208dfe1d'
PARENT = 'mcp:launch:c4185c930eca174d8d1afc1306852295d17ffddccc8ef520a6713bb41d411891'
CHILD = 'thread:delegated-task:command%3Amcp%3A114c49bc-e597-481f-9362-cbd2efe3bb19%3Adelegate-task%3Afish-v30-h00-direct-sequence-postfit-20261108'
PLAN = REPORT/'H01-amendment.json'
TESTS = ('test_filter', 'test_model', 'test_entry', 'test_history', 'test_hierarchy_entry')
ROOTS = tuple('tools.action_predictor.segment_policy.'+n for n in ('hierarchy_fit', *TESTS))


def read_checked(path):
    relative = path.relative_to(ROOT).as_posix()
    actual = path.read_bytes()
    committed = subprocess.run(['git', 'show', 'HEAD:'+relative], cwd=ROOT, check=True, capture_output=True).stdout
    if actual != committed: raise RuntimeError('Uncommitted prerequisite: '+relative)
    return json.loads(actual)


def original(name):
    return subprocess.run(['git', 'show', H00_SOURCE+':tools/action_predictor/segment_policy/'+name],
        cwd=ROOT, check=True, capture_output=True).stdout.decode('utf-8').replace('\r\n', '\n')


def matched_science():
    old = read_checked(REPORT/'H00.json')
    if digest(REPORT/'H00.json') != H00_REPORT or old['checkpoint_sha256'] != H00_CHECKPOINT:
        raise RuntimeError('Reviewed H00 result changed')
    for key, expected in old['sources'].items():
        if digest(ROOT/key) == expected: continue
        if key != 'tools/action_predictor/segment_policy/fit.py':
            raise RuntimeError('Shared H00 science changed: '+key)
        source = (ROOT/key).read_text()
        guard = "    if arm == 'H01':\n        raise RuntimeError('Original H01 has a known history mismatch; use the amended hierarchy_fit entrypoint and frozen amendment')\n"
        if source.count(guard) != 1 or source.replace(guard, '') != original('fit.py'):
            raise RuntimeError('Legacy entrypoint change exceeds the H01 safety guard')
    source = original('fit.py')
    source = source.replace('from .protocol import SEED, ARMS, preflight', 'from .protocol import SEED, ARMS\nfrom .amendment import preflight')
    source = source.replace('from .model import SegmentPolicy', 'from .history_model import HistorySegmentPolicy as SegmentPolicy')
    source = source.replace('from .inference import infer, take, put', 'from .history_inference import infer, take, put')
    source = source.replace('from .assessment import assess', 'from .hierarchy_assessment import assess\nfrom .gradient_diagnostic import gradient_summary')
    source = source.replace("if arm not in ARMS: raise ValueError('Unknown registered arm')", "if arm != 'H01': raise ValueError('Amended entrypoint is H01 only')")
    source = source.replace("parser.add_argument('arm', choices=ARMS)", "parser.add_argument('arm', choices=['H01'])")
    source = source.replace('            objective.backward()\n', "            objective.backward()\n            if updates == 0 or (updates+1) % 250 == 0:\n                immutable_json(directory/f'gradient-{updates+1:06d}.json', gradient_summary(model, updates+1, epoch))\n")
    if (ROOT/'tools/action_predictor/segment_policy/hierarchy_fit.py').read_text() != source:
        raise RuntimeError('Amended runner changed optimization beyond declared imports/logging/arm guard')


def source_gate():
    reject_optimized_python()
    for name in TESTS:
        if not (ROOT/'tools/action_predictor/segment_policy'/f'{name}.py').is_file():
            raise RuntimeError('Mandatory prerequisite test source absent: '+name)
    result = committed_sources(ROOT, dependency_files(ROOT, ROOTS))
    matched_science()
    return result


def review_records():
    return {name: read_checked(REPORT/name) for name in
        ('H00-review.json', 'H00-review-delegation.json', 'H00-review-delegation-launch.json', 'H00-review-request.json')}


def validate_review(records):
    review = records['H00-review.json']; terminal = records['H00-review-delegation.json']
    launch = records['H00-review-delegation-launch.json']; request = records['H00-review-request.json']
    if terminal['status'] != 'completed' or terminal.get('hasPendingChildRuns') or terminal.get('hasPendingQuestion'):
        raise RuntimeError('Fresh control review is not terminal')
    if terminal.get('model') != 'gpt-6.1-sol' or terminal.get('providerInstanceId') != 'codex':
        raise RuntimeError('Wrong reviewer model/provider')
    if dict((o['id'], o['value']) for o in terminal.get('options', [])) .get('reasoningEffort') != 'xhigh':
        raise RuntimeError('Requested review effort absent')
    if launch.get('childThreadId') != CHILD or terminal.get('childThreadId') != CHILD or launch.get('taskId') != terminal.get('taskId'):
        raise RuntimeError('Wrong review identity')
    thread = review['thread']
    if thread['threadId'] != CHILD or thread.get('parentThreadId') != PARENT or thread.get('activeRunId') is not None or thread.get('pendingRequestCount'):
        raise RuntimeError('Review parent/terminal state mismatch')
    runs = review['recentRuns']
    if not runs or runs[-1]['status'] != 'completed' or runs[-1]['runId'] != terminal.get('latestTerminalRunId'):
        raise RuntimeError('Completed review run not bound')
    finals = [m for m in review['items'] if m['type'] == 'assistant_message' and m['status'] == 'completed'
              and m['runId'] == runs[-1]['runId'] and m['sourceThreadId'] == CHILD]
    if not finals or len(finals[-1].get('text') or '') < 1000: raise RuntimeError('Substantive review record absent')
    if request['checkpoint_sha256'] != H00_CHECKPOINT or request['report_sha256'] != H00_REPORT:
        raise RuntimeError('Review checkpoint/result scope mismatch')


def freeze():
    commit, sources = source_gate()
    records = review_records(); validate_review(records)
    old = read_checked(REPORT/'protocol.json')
    rt.setup(SEED); teacher, _ = load_base(); model = HistorySegmentPolicy(teacher)
    count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if count != 149530: raise RuntimeError('Amended capacity differs')
    review_bindings = {str((REPORT/k).relative_to(ROOT)): digest(REPORT/k) for k in records}
    response = dict(review_bindings=review_bindings, reviewed_checkpoint_sha256=H00_CHECKPOINT,
        findings_resolved={'history_path': True, 'exit_timepoint': True, 'combined_architecture_attribution': True,
                           'sequence_limits': True, 'review_entry_gate': True},
        implementation={str(p.relative_to(ROOT)): digest(p) for p in
            (ROOT/'tools/action_predictor/segment_policy'/n for n in ('history_filter.py', 'history_model.py', 'history_inference.py', 'hierarchy_assessment.py', 'test_history.py', 'test_hierarchy_entry.py'))},
        interpretation='Parent response to actual fresh review, not reviewer-authored certification or future-result approval. Live preflight verifies code, matching contract and tests before optimizer construction.',
        parameter_correction='Expanding all64initial/12transition/4hazard outputs by21would add1680weights, not1616. Initial64x21columns alwayszeroonreset are omitted; only16x21=336dynamics weights added.',
        evidence_limits='H00 valid negative; no HSMM result yet. The contrast measures a combined architecture. Only163TRAINruns/3202rows reach16roots; DEVmax15and27.3%resets;8nodeBPTT limits temporalcredit. States can alternate similar execution despite nonselftransitions.',
        new_fits=0, reserved_opened=0)
    immutable_json(REPORT/'H00-review-response.json', response)
    inputs = dict(old['inputs']); inputs.update(review_bindings)
    inputs[str((REPORT/'H00-review-response.json').relative_to(ROOT))] = digest(REPORT/'H00-review-response.json')
    control = read_checked(REPORT/'H00.json')
    control_bindings = {k.replace('\\', '/'): v for k, v in control['bindings'].items()}
    for relative in ('.cambc/action-predictor/v30/runs/H00/validation-predictions.npz',
                     '.cambc/action-predictor/v30/runs/H00/initial.pt'):
        inputs[relative] = control_bindings[relative]
    inputs[str((REPORT/'H00.json').relative_to(ROOT))] = H00_REPORT
    immutable_json(PLAN, dict(id='V30-H01-causal-command-history-amendment', source_commit=commit,
        sources=sources, inputs=inputs, prior_protocol_sha256=digest(REPORT/'protocol.json'),
        parameters={'H00': old['parameters']['H00'], 'H01': dict(trainable=count, total=sum(p.numel() for p in model.parameters()))},
        matching_contract=dict(initial_features=128, dynamics_features=149, previous_command_fields=21,
            extra_nominal_trainable_weights=336, command_written_after_prediction=True, reset_at_same_gaps=True),
        initialization='Every original common/state/age/conditioning tensor and RNG preserved; copy128context columns/biases exactly and zero only new21columns in transitions/hazards. No new columns in initial distribution. No initializer change based on small gradient norms.',
        supervision='Same complete-command sequence NLL, decoder, data/sampling/normalization, seed and optimizer/checkpoint rule as preserved H00. New command buffer contains only the same earlier21fields used by H00, cleared at identical resets. Both may compress/use that evidence differently.',
        attribution='Supersedes original phrase evidence for duration structure: this tests combined discrete state/age inference, memory and conditioned execution versus direct recurrence. An age-independent matched state control is needed before specific duration attribution. Grounding remains separate.',
        diagnostics='Exit event uses PREVIOUS posterior and actually applied hazards; reset entries NaN/unassessed, current-prior age separately named. Read-only preclip gradient scales archived update1/every250; no optimization change.',
        continuation='Original numerical exploratory allocation criteria unchanged; original binding category/macro/movement/loss/targeting/three-seed targets unchanged. No global research cap or future-result approval.',
        new_fits=0, reserved_opened=0))


def preflight():
    commit, sources = source_gate()
    plan = read_checked(PLAN)
    if plan['sources'] != sources: raise RuntimeError('Amended executable closure changed')
    expected = dict(initial_features=128, dynamics_features=149, previous_command_fields=21,
        extra_nominal_trainable_weights=336, command_written_after_prediction=True, reset_at_same_gaps=True)
    if plan['matching_contract'] != expected: raise RuntimeError('History matching contract unresolved')
    records = review_records(); validate_review(records)
    response = read_checked(REPORT/'H00-review-response.json')
    required = {'history_path', 'exit_timepoint', 'combined_architecture_attribution', 'sequence_limits', 'review_entry_gate'}
    if response['reviewed_checkpoint_sha256'] != H00_CHECKPOINT or set(response['findings_resolved']) != required or not all(response['findings_resolved'].values()):
        raise RuntimeError('Review findings unresolved')
    for relative, expected in response['review_bindings'].items():
        if digest(ROOT/relative) != expected: raise RuntimeError('Resolved review record changed')
    for relative, expected in plan['inputs'].items():
        if digest(ROOT/relative) != expected: raise RuntimeError('Amendment prerequisite changed: '+relative)
    test = subprocess.run([sys.executable, '-m', 'unittest', *('tools.action_predictor.segment_policy.'+n for n in TESTS), '-v'],
        cwd=ROOT, capture_output=True, text=True)
    if test.returncode: raise RuntimeError('Amended prerequisite tests failed: '+test.stdout+test.stderr)
    return plan, dict(source_commit=commit, sources=sources, protocol_sha256=digest(PLAN),
        original_protocol_sha256=digest(REPORT/'protocol.json'),
        prerequisite_stdout=test.stdout, prerequisite_stderr=test.stderr)


if __name__ == '__main__': freeze()
