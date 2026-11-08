"""PC01: fixed P05 optimization, broader TRAIN population, unchanged controls."""
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head, load as control_data
from ..priority_capacity.measurement import measure
from ..priority_head import flatten
from .guard import checked_execution, committed_sources

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / '.cambc/action-predictor'
OUT = ROOT / 'tools/action_predictor/experiments/v21'
LOCAL = OLD / 'v21'
SEED = 20261120


def source_paths():
    here = Path(__file__).parent
    return [here / n for n in ('__init__.py', 'experiment.py', 'guard.py', 'test_guard.py')] + [
        here.parent / n for n in ('priority_capacity/data.py', 'priority_capacity/measurement.py',
                                 'priority_residual_modes.py', 'priority_modes.py',
                                 'priority_head.py', 'reliable_train.py', 'audit.py', 'data.py')]


def prepare(commit, sources, test_receipts):
    previous = json.loads((ROOT / 'tools/action_predictor/experiments/v19/PC00-data-ready.json').read_text())
    bindings = previous['bindings']
    # Reuse immutable approved caches, without invoking old download/audit/fit entrypoints.
    for relative, expected in bindings.items():
        assert digest(ROOT / relative) == expected, relative
    def path_ending(ending):
        matches = [ROOT / p for p in bindings if p.endswith(ending)]
        assert len(matches) == 1, ending
        return matches[0]
    model, saved, initial_path = head()
    controls = control_data()
    with np.load(path_ending('combined-train.npz')) as z:
        y, priorities, groups = z['y'], z['priority'], z['group']
    natural = np.load(path_ending('natural-mask.npy'))
    fit_groups = np.unique(controls['fit']['group'].numpy())
    pool = np.flatnonzero(natural & (y == 9) & np.isin(groups, fit_groups))
    excluded = np.concatenate([controls[n]['index'].numpy() for n in ('same_fit_groups', 'held_groups')])
    indices = np.setdiff1d(pool, excluded)
    assert len(indices) == 5876 and len(fit_groups) == 55
    assert np.isin(controls['fit']['index'].numpy(), indices).all()
    assert not np.isin(excluded, indices).any()
    assert not set(groups[indices]) & set(controls['held_groups']['group'].tolist())
    with np.load(path_ending('priority-train.npz')) as z:
        values, history = z['values'][indices], z['history'][indices]
    with np.load(path_ending('extra-normalization.npz')) as z:
        mean, std = z['mean'], z['std']
    np.testing.assert_array_equal(mean, saved['extra_mean'].numpy())
    np.testing.assert_array_equal(std, saved['extra_std'].numpy())
    context = np.array(np.load(path_ending('train.npy'), mmap_mode='r')[indices])
    features = (flatten(values, history).astype(np.float32) - mean) / std
    target = priorities[indices].astype(np.int64)
    assert values.dtype == target.dtype == np.int64
    assert np.isfinite(context).all() and np.isfinite(features).all()
    absolute = np.unique(target)
    residual = np.unique((target + values[:, 4])[values[:, 5] == 1])
    assert len(absolute) == 430 and len(residual) == 560
    assert np.isin(target, model.absolute.numpy()).all()
    for name in ('same_fit_groups', 'held_groups'):
        c = controls[name]
        available = c['values'][:, 5].numpy() == 1
        coverage = np.isin(c['target'].numpy(), absolute) | (available & np.isin(
            (c['target'] + c['values'][:, 4]).numpy(), residual))
        assert coverage.all(), name
    plan = dict(id='PC01-broad-natural-P05', source_commit=commit, sources=sources,
        inputs=bindings, initial_checkpoint_sha256=digest(initial_path),
        parent_protocol_sha256=digest(ROOT / 'tools/action_predictor/experiments/v19/PC00-plan.json'),
        hypothesis='Does broader natural TRAIN coverage improve the same head fitting and prevent '
                   'the PC00 control collapse? Changes training population only; coverage and diversity '
                   'are not separately isolated. Chunk accumulation changes finite precision only.',
        cohort=dict(rows=5876, fit_groups=55, absolute_labels=430, available_residual_labels=560,
                    rule='All natural priority rows from PC00 actual fit groups, minus both controls. '
                         'Original128fit rows are included; no row selected by model error.'),
        exposure='Frozen encoder AND warm head, normalization and vocabulary previously saw controls. '
                 'Held out only from NEW optimization, not untouched full-policy generalization.',
        model='Same actual P05 absolute/residual/logistic head, original 128D frozen M01 contexts, '
              '39 normalized causal channels and exact int64 anchors. No new architecture/vocabulary.',
        training=dict(seed=SEED, updates=2000, full_batch_rows=5876, chunks=256,
                      loss='Sum normalized integer NLL over chunks divided by5876; accumulate all '
                           'gradients before ONE optimizer step per update. No resampling.',
                      optimizer='AdamW', lr_first1000=.003, lr_last1000=.001,
                      weight_decay=0, gradient_clip=5, threads=4),
        assessment_steps=[0, 100, 500, 1000, 2000],
        assessment='All broad fit rows, original128fit rows, same two unchanged128controls. '
                   'Exact,NLL,MAE,bounded candidate rank and marginalized explanation shares. '
                   'Fixed final2000; no checkpoint/threshold selection, DEV lookup or promotion.',
        interpretation='Compare broad fitting and control changes against saved PC00. '
                       'Broader population is the named treatment, not one isolated data mechanism. '
                       'Diagnostic-only; no full-policy replacement. Any subsequent integrated '
                       'prediction must re-decode normalized joint command probabilities.',
        continuation='Fresh Solxhigh review after fit; follow fitting/transfer evidence. '
                     'Neither fit success nor failure establishes observation sufficiency. '
                     'Original full benchmark/per-category/three-seed targets remain binding.',
        constraints='EligibleTRAINonly; both75-game partitions sealed. No DEV payloads, matches, '
                    'downloads, bot/runtime/deployment. All old artifacts preserved.',
        new_fits_allocated=1, new_fits=0, reserved_opened=0)
    immutable_json(OUT / 'PC01-plan.json', plan)
    dataset = dict(context=torch.from_numpy(context), features=torch.from_numpy(features),
                   values=torch.from_numpy(values), target=torch.from_numpy(target),
                   index=torch.from_numpy(indices), group=torch.from_numpy(groups[indices]))
    with np.load(path_ending('G00\\train-predictions.npz')) as z:
        baseline_mode, baseline_nll = z['priority'][indices], z['param_nll'][indices]
    LOCAL.mkdir(parents=True, exist_ok=True)
    dataset_path = LOCAL / 'PC01-cohort.npz'
    assert not dataset_path.exists(), 'Preserve prepared cohorts'
    np.savez_compressed(dataset_path, **{k: v.numpy() for k, v in dataset.items()})
    # Required raw-input parity before constructing an optimizer.
    with torch.no_grad():
        outputs = [model(dataset['context'][s:s+256], dataset['features'][s:s+256])
                   for s in range(0, len(indices), 256)]
        raw = torch.cat(outputs)
        modes = torch.cat([model.integer(o, dataset['values'][s:s+256])
                          for s, o in zip(range(0, len(indices), 256), outputs)])
        nll = -model.log_mass(raw, dataset['target'], dataset['values'])
        np.save(LOCAL / 'PC01-initial-raw.npy', raw.numpy())
    mismatch = int((modes.numpy() != baseline_mode).sum())
    discrepancy = float(np.abs(nll.numpy() - baseline_nll).max())
    assert mismatch == 0 and discrepancy <= 2e-5, (mismatch, discrepancy)
    # Accumulation contract: compare full gradient with uneven chunks, no optimizer.
    probe = controls['fit']
    model.zero_grad(set_to_none=True)
    raw = model(probe['context'], probe['features'])
    (-model.log_mass(raw, probe['target'], probe['values']).mean()).backward()
    full = [p.grad.clone() for p in model.parameters()]
    model.zero_grad(set_to_none=True)
    for start in range(0, 128, 41):
        sl = slice(start, start + 41)
        out = model(probe['context'][sl], probe['features'][sl])
        (-model.log_mass(out, probe['target'][sl], probe['values'][sl]).sum() / 128).backward()
    max_gradient_difference = max(float((a - p.grad).abs().max()) for a, p in zip(full, model.parameters()))
    for a, p in zip(full, model.parameters()):
        torch.testing.assert_close(a, p.grad, rtol=2e-5, atol=2e-7)
    model.zero_grad(set_to_none=True)
    current_commit, current_sources = committed_sources(ROOT, source_paths())
    assert current_commit == commit and current_sources == sources
    receipt = dict(passed=True, source_commit=commit, sources=sources,
        protocol_sha256=digest(OUT / 'PC01-plan.json'), cohort_sha256=digest(dataset_path),
        initial_mode_mismatches=mismatch, initial_NLL_max_difference=discrepancy,
        accumulation_gradient_max_difference=max_gradient_difference,
        failure_path_tests=test_receipts, no_optimizer_created_before_preflight=True,
        original128fit_input_rank=int(np.linalg.matrix_rank(np.concatenate((
            probe['context'].numpy(), probe['features'].numpy(), np.ones((128, 1))), 1))),
        broader_input_rank=int(np.linalg.matrix_rank(np.concatenate((
            context, features, np.ones((len(indices), 1))), 1))), new_fits=0, reserved_opened=0)
    immutable_json(OUT / 'PC01-preflight.json', receipt)
    return model, dataset, controls, receipt


def execute(test_receipts):
    assert len(test_receipts) == 1 and test_receipts[0]['returncode'] == 0
    assert test_receipts[0]['command'] == [sys.executable, '-m', 'unittest',
        'tools.action_predictor.priority_broad.test_guard',
        'tools.action_predictor.priority_capacity.test_measurement']
    commit, sources = committed_sources(ROOT, source_paths())
    rt.setup(SEED)
    model, fit, controls, preflight = prepare(commit, sources, test_receipts)
    assert preflight['passed'] and preflight['source_commit'] == commit
    assert preflight['protocol_sha256'] == digest(OUT / 'PC01-plan.json')
    assert committed_sources(ROOT, source_paths()) == (commit, sources)
    directory = LOCAL / 'runs/PC01'
    assert not directory.exists(), 'Never restart or overwrite an attempted fit'
    directory.mkdir(parents=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.003, weight_decay=0)
    parameters = list(model.parameters())
    assert len(parameters) == 2 and all(p.requires_grad for p in parameters)
    assert {id(p) for p in parameters} == {id(p) for g in optimizer.param_groups for p in g['params']}
    cohorts = dict(broad_fit=fit, original_fit=controls['fit'],
                   same_fit_groups=controls['same_fit_groups'], held_groups=controls['held_groups'])
    trace = []
    tick = time.perf_counter()
    gradient_receipt = None

    def assess(step):
        torch.save(dict(head_state=model.state_dict(), optimizer=optimizer.state_dict(), step=step,
                        torch_rng=torch.get_rng_state(), source_commit=commit,
                        protocol_sha256=digest(OUT / 'PC01-plan.json'),
                        preflight_sha256=digest(OUT / 'PC01-preflight.json')),
                   directory / f'step-{step:04d}.pt')
        row = dict(step=step, seconds=time.perf_counter()-tick, cohorts={})
        with torch.no_grad():
            for name, d in cohorts.items():
                predictions = {}
                raw_outputs = []
                for start in range(0, len(d['target']), 256):
                    sl = slice(start, start+256)
                    raw = model(d['context'][sl], d['features'][sl])
                    p, _ = measure(model, raw, d['values'][sl], d['target'][sl])
                    raw_outputs.append(raw.numpy())
                    for key, value in p.items():
                        predictions.setdefault(key, []).append(value.numpy())
                predictions = {key: np.concatenate(value) for key, value in predictions.items()}
                np.save(directory / f'{name}-step-{step:04d}-raw.npy', np.concatenate(raw_outputs))
                np.savez_compressed(directory / f'{name}-step-{step:04d}-predictions.npz', **predictions)
                error = np.abs(predictions['integer'] - d['target'].numpy())
                row['cohorts'][name] = dict(rows=len(error), exact=int((error == 0).sum()),
                    accuracy=float((error == 0).mean()), mean_NLL=float(predictions['nll'].mean()),
                    MAE=float(error.mean()), mean_bounded_candidate_rank=float(predictions['rank'].mean()),
                    mean_marginalized_explanation_shares=predictions['credit'].mean(0).tolist())
        trace.append(row)
        print('PC01', step, {name:(v['exact'],v['mean_NLL']) for name,v in row['cohorts'].items()}, flush=True)

    assess(0)
    try:
        for step in range(1, 2001):
            if step == 1001:
                for group in optimizer.param_groups:
                    group['lr'] = .001
            optimizer.zero_grad(set_to_none=True)
            for start in range(0, len(fit['target']), 256):
                sl = slice(start, start+256)
                raw = model(fit['context'][sl], fit['features'][sl])
                loss = -model.log_mass(raw, fit['target'][sl], fit['values'][sl]).sum()/len(fit['target'])
                assert torch.isfinite(loss)
                loss.backward()
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in parameters)
            if step == 1:
                gradient_receipt = dict(optimizer_inclusion_exact=True,
                    parameter_gradient_norms={name:float(p.grad.norm()) for name,p in model.named_parameters()})
            torch.nn.utils.clip_grad_norm_(parameters, 5)
            optimizer.step()
            if step in (100, 500, 1000, 2000):
                assess(step)
            elif step % 100 == 0:
                print('PC01 progress',step,'seconds',round(time.perf_counter()-tick,2),flush=True)
    except BaseException:
        (directory / f'failure-{time.time_ns()}.txt').write_text(traceback.format_exc())
        raise
    immutable_json(OUT / 'PC01.json', dict(source_commit=commit, sources=sources, trace=trace,
        protocol_sha256=digest(OUT/'PC01-plan.json'), preflight_sha256=digest(OUT/'PC01-preflight.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()},
        cohort_sha256=digest(LOCAL/'PC01-cohort.npz'), gradient_receipt=gradient_receipt,
        fixed_final_step=2000, optimizer_updates=2000, trainable_parameters=sum(p.numel() for p in parameters),
        seconds=time.perf_counter()-tick, new_fits=1, reserved_opened=0,
        diagnostic_only=True, complete_policy_replaced=False, selected_checkpoint_changed=False))
    print('PC01 completed; fresh Solxhigh review required.', flush=True)


if __name__ == '__main__':
    # This is the sole entrypoint. A failed test/source/data check cannot reach optimizer creation.
    committed_sources(ROOT, source_paths())
    checked_execution([[sys.executable, '-m', 'unittest',
                        'tools.action_predictor.priority_broad.test_guard',
                        'tools.action_predictor.priority_capacity.test_measurement']], execute, ROOT)
