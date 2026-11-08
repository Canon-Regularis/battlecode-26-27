"""Frozen initial movement-sequence contrast; no global research stop rule."""
import json
import subprocess
import sys
import torch
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files, reject_optimized_python
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from .data import ROOT, WORK, REPORT
from .model import SegmentPolicy

SEED = 20261130
ARMS = {'H00': 'direct_recurrent_sequence', 'H01': 'neural_explicit_duration'}
ROOTS = tuple('tools.action_predictor.segment_policy.'+n for n in
             ('fit', 'test_filter', 'test_model', 'test_entry'))
ANCHOR = '1caf7ff5f38e62e28c8bfbf6cc6521230f6d4eeb'


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT, dependency_files(ROOT, ROOTS))


def retained_inputs():
    receipt, bindings = committed_manifest(ANCHOR, 'tools/action_predictor/experiments/v27/JP-completion.json')
    allowed = {k.replace('\\', '/'): v for k, v in receipt['bindings'].items()}
    path = 'tools/action_predictor/experiments/v16/policy-input-bindings.json'
    if digest(ROOT/path) != allowed[path]: raise RuntimeError('Immutable sequence input receipt changed')
    bindings[path] = allowed[path]
    legacy = json.loads((ROOT/path).read_text())
    needed = {k.replace('\\', '/'): v for k, v in legacy['files'].items()}
    # Approved V7 diagnostic inputs plus exact original natural row membership.
    v7path = 'tools/action_predictor/experiments/v7/data-ready.json'
    v7, more = committed_manifest(ANCHOR, v7path)
    bindings.update(more)
    for split in ('train', 'validation'):
        for suffix in ('direction', 'available', 'near_obstacle'):
            name = f'{split}-{suffix}.npy'
            needed[f'.cambc/action-predictor/v7/{name}'] = v7['files'][name]
        for name in ('integer', 'mode_logp'):
            key = f'.cambc/action-predictor/v27/forecasts/{split}/JP02/{name}.npy'
            needed[key] = allowed[key]
        key = f'.cambc/action-predictor/v27/JP02-{split}-predictions.npz'
        needed[key] = allowed[key]
    needed['.cambc/action-predictor/v9/frequency/natural-mask.npy'] = '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    for name in ('L02',):
        path = f'tools/action_predictor/experiments/v16/{name}.json'
        report, more = committed_manifest(ANCHOR, path)
        bindings.update(more)
        for split in ('train', 'validation'):
            needed[f'.cambc/action-predictor/v16/runs/{name}/{split}-predictions.npz'] = report['predictions_sha256'][split]
    for key, expected in needed.items():
        if digest(ROOT/key) != expected: raise RuntimeError('Retained input changed: '+key)
        bindings[key] = expected
    return bindings


def freeze():
    commit, sources = source_gate()
    bindings = retained_inputs()
    counts = {}
    for arm in ARMS:
        rt.setup(SEED)
        teacher, _ = load_base()
        model = SegmentPolicy(teacher, arm == 'H01')
        counts[arm] = dict(trainable=sum(p.numel() for p in model.parameters() if p.requires_grad),
                          total=sum(p.numel() for p in model.parameters()))
    value = dict(id='V30-causal-segment-policy', source_commit=commit, sources=sources, inputs=bindings,
        arms=ARMS, parameters=counts, seed=SEED,
        hypothesis='Jointly learned explicit durations/state transitions may improve command-sequence prediction versus a direct recurrent policy. Anonymous states have no assigned strategy meaning. No performance assumed.',
        common='Warm M01 current/action-history encoder, trainable action and 291-bucket candidate-coordinate heads; 16 earlier personal observation frames with availability/round gaps, all V9 known champion/camp tokens and public geometry. Same initialization of every common tensor. New history/entity projections startzero; direct memory projection biaszero; hierarchy FiLM biaszero with tiny random weight symmetrybreaking. No achieved-position auxiliary, no frozen spatial executor, no hand strategy/camp preference. RC01 integer distribution retained and fixed on every row.',
        direct='GRUCell receives current shared context and recorded command encoding ONLY after command prediction. 28-dimensional memory projects into execution context. Resets at actual own-root gaps and actor starts.',
        hierarchy='Four anonymous latent states, 16 explicit own-root ages. Learned observation-conditioned non-self transitions, context-and-age hazards, learned joint state-age initial distribution for unknown prefix. Shared FiLM-conditioned execution trained jointly with high-level factors. Causal forward command likelihood marginalizes state and variable-length segment boundaries; no oracle segmentation or recognition future.',
        gap_contract='Use retained chronological own-root index-derived gaps. Only genuinely consecutive roots advance duration. Across missing roots, reset to a learned unknown-prefix state/age distribution; direct control resets identically. No survival claim or current observation applied to unobserved roots. Float32 stored log gaps reconstruct counts by rounding; only certified one-versus-multiple-root boundary affects propagation. Age support16 is computational truncation, not Fish behavior. Earlier-frame history remains available to both arms across these resets.',
        training=dict(population='Every original 433071 augmented TRAIN decision once per round, actor-stream permutation; natural288801 and augmented-only144270 assessed separately',
            optimizer='AdamW', lr=.0003, weight_decay=.01, clip=5, actor_batch=32, unroll=8,
            loss='Mean normalized observed complete-command NLL, no class weights, no auxiliary, no named behavior labels',
            checkpoint='Original all14439 DEV observed joint NLL: improvement0.0001,patience6,max35rounds. Round0 diagnostic only, never selectable. Preserve all rounds and optimizer/RNG states.',
            allocation='Same data presentations per round and same checkpoint opportunity; compare selected and completed updates and measured costs. H01 has four execution evaluations; compute cost is not identical. This initial pair is not a global experiment cap.'),
        decoder='Marginalize latent explanations then maximize action+every modeled argument jointly; exact finite spatial and retained priority modes. Float64 probability normalization. Shop remains marginalized action bucket with unavailable original purchase arguments, always strict failure. Target identity ambiguity unchanged.',
        metrics=['All original DEV complete commands; natural/augmented/all TRAIN', 'type PRF/confusion and joint FP',
            'all-true-family conditional versus correctly-typed parameters', 'movement continuation/change/startup and blocked attempt destinations/outcomes',
            'category/type/parameter/joint NLL; target rank/probability', '2000 paired whole-group resamples seed20261106 versus direct/G00/L02/JP02',
            'genuine consecutive command windows only', 'state-mode diversity, common-wrong dominance and oracle component coverage diagnostic versus actual causal selection',
            'gap resets, state/age distributions and termination; long duration is not success', 'partial readiness/move-success mask separate from blocked-attempt mask; full legality unassessed'],
        exploratory_continuation='Investigate further only after fresh review. Evidence for duration structure requires H01 versus H00 improving DEV joint movement by at least24 commands and changing destinations by at least12, lower observed jointNLL, no continuation loss over0.5pp, no attack/cast conditional regression over0.02 and no material other-category regression. These allocation diagnostics do not replace original90%-per-supported-category/macro/movement/loss/three-seed targets; no robustness claim from one seed or reused DEV.',
        attribution='First contrast tests anonymous duration/state-conditioned sequence execution versus direct recurrence; capacity is comparable, not exact architecture equivalence. Natural/augmented-only metrics are row-membership strata under augmented traversal, not matched natural-cadence replay. It does not isolate grounding. Persistent particular-entity selection requires a separately controlled, causally bound identity interface with null/unknown/death handling. No claim states equal objectives or learned Fish intent.',
        restrictions='Both75-game partitions sealed; no matches/proposed-action simulations/downloads, bot/runtime/deployment or priority-only fits. Preserve every negative result. Fresh user-requested Solxhigh review after each substantive fit.',
        new_fits=0, reserved_opened=0)
    immutable_json(REPORT/'protocol.json', value)
    return value


def preflight():
    commit, sources = source_gate()
    path = REPORT/'protocol.json'
    plan = json.loads(path.read_text())
    if sources != plan['sources']: raise RuntimeError('Scientific executable closure changed after freeze')
    for key, expected in plan['inputs'].items():
        if digest(ROOT/key) != expected: raise RuntimeError('Protocol input changed: '+key)
    test = subprocess.run([sys.executable, '-m', 'unittest',
        'tools.action_predictor.segment_policy.test_filter', 'tools.action_predictor.segment_policy.test_model',
        'tools.action_predictor.segment_policy.test_entry', '-v'], cwd=ROOT, capture_output=True, text=True)
    if test.returncode: raise RuntimeError('Prerequisite tests failed: '+test.stdout+test.stderr)
    return plan, dict(source_commit=commit, sources=sources, protocol_sha256=digest(path),
                      prerequisite_stdout=test.stdout, prerequisite_stderr=test.stderr)


if __name__ == '__main__': freeze()
