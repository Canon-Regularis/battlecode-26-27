"""PD00: score every original P05 checkpoint on identical TRAIN priority rows.

This is descriptive posthoc analysis, not checkpoint selection or a new fit.
Only TRAIN payloads are consumed; original DEV scores are copied from P05.json.
"""
import json
import time
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_head import flatten
from ..priority_residual_modes import AnchoredPriorityModes

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / '.cambc/action-predictor'
OUT = ROOT / 'tools/action_predictor/experiments/v20'
LOCAL = OLD / 'v20/PD00'


def run():
    torch.set_num_threads(4)
    assert not (OUT / 'PD00.json').exists(), 'Preserve completed analyses'
    prior = json.loads((ROOT / 'tools/action_predictor/experiments/v19/PC00-data-ready.json').read_text())
    inputs = {k: v for k, v in prior['bindings'].items() if any(
        term in k for term in ('train.npy', 'extra-normalization.npz', 'priority-train.npz',
                              'combined-train.npz', 'natural-mask.npy',
                              'G00\\train-predictions.npz', 'P05\\model.pt'))}
    required = ('context', 'normalizer', 'priority', 'dataset', 'natural', 'baseline', 'model')
    needles = ('train.npy', 'extra-normalization.npz', 'priority-train.npz', 'combined-train.npz',
               'natural-mask.npy', 'G00\\train-predictions.npz', 'P05\\model.pt')
    paths = {}
    for name, needle in zip(required, needles):
        matches = [ROOT / key for key in inputs if key.endswith(needle)]
        assert len(matches) == 1, (name, matches)
        paths[name] = matches[0]
    for relative, expected in inputs.items():
        assert digest(ROOT / relative) == expected, relative
    old_report = ROOT / 'tools/action_predictor/experiments/v8/P05.json'
    report = json.loads(old_report.read_text())
    saved = torch.load(paths['model'], weights_only=True, map_location='cpu')
    assert digest(paths['model']) == report['checkpoint_sha256']
    directory = paths['model'].parent
    epoch_paths = {row['epoch']: directory / f"epoch-{row['epoch']}.pt" for row in report['history']}
    source_paths = [Path(__file__), Path(__file__).with_name('__init__.py'),
                    ROOT / 'tools/action_predictor/priority_head.py',
                    ROOT / 'tools/action_predictor/priority_residual_modes.py',
                    ROOT / 'tools/action_predictor/priority_modes.py']
    bindings = {**inputs, str(old_report.relative_to(ROOT)): digest(old_report),
                **{str(p.relative_to(ROOT)): digest(p) for p in source_paths},
                **{str(p.relative_to(ROOT)): digest(p) for p in epoch_paths.values()}}
    immutable_json(OUT / 'PD00-plan.json', dict(
        id='PD00-original-P05-TRAIN-trajectory', bindings=bindings,
        purpose='Determine whether original full-data fitting continues after DEV selection. '
                'Same natural/augmented TRAIN rows and normalized integer likelihood at every checkpoint.',
        operations='Read-only frozen-model inference on all TRAIN priority rows. No fitting, '
                   'no DEV payload read, no replacement checkpoint or treatment selection.',
        metrics='Exact integer, NLL, MAE, target probability; natural and augmented denominators '
                'plus fixed natural-frequency strata 1-9 /10-99 /100+ and anchor availability. '
                'Whole-group descriptive train aggregates, not out-of-sample estimates.',
        claims='TRAIN is in-sample for encoder/head. Historical DEV losses copied only; '
               'online original TRAIN losses are not static checkpoint losses. No strategy/intent inference.',
        original_selected_epoch=report['best_epoch'], new_fits=0, reserved_opened=0))
    with np.load(paths['dataset']) as z:
        indices = np.flatnonzero(z['y'] == 9)
        target, group = z['priority'][indices].astype(np.int64), z['group'][indices]
    natural = np.load(paths['natural'])[indices]
    context = np.array(np.load(paths['context'], mmap_mode='r')[indices])
    with np.load(paths['normalizer']) as z:
        mean, std = z['mean'], z['std']
    np.testing.assert_array_equal(mean, saved['extra_mean'].numpy())
    np.testing.assert_array_equal(std, saved['extra_std'].numpy())
    with np.load(paths['priority']) as z:
        values, history = z['values'][indices], z['history'][indices]
    features = (flatten(values, history).astype(np.float32) - mean) / std
    with np.load(paths['baseline']) as z:
        old_mode, old_nll = z['priority'][indices], z['param_nll'][indices]
    state = saved['head_state']
    model = AnchoredPriorityModes(torch.nn.Linear(128, 2), state['absolute'],
                                np.ones(len(state['absolute'])), state['residual'],
                                np.ones(len(state['residual'])))
    model.requires_grad_(False)
    assert np.isin(target, state['absolute'].numpy()).all()
    count_values, counts = np.unique(target[natural], return_counts=True)
    count_lookup = dict(zip(count_values.tolist(), counts.tolist()))
    frequency = np.array([count_lookup.get(int(t), 0) for t in target], dtype=np.int64)
    masks = dict(augmented=np.ones(len(indices), bool), natural=natural,
                 augmentation_only=~natural, natural_freq_1_to_9=natural & (frequency < 10),
                 natural_freq_10_to_99=natural & (frequency >= 10) & (frequency < 100),
                 natural_freq_100_plus=natural & (frequency >= 100),
                 natural_anchor_available=natural & (values[:, 5] == 1),
                 natural_anchor_unavailable=natural & (values[:, 5] == 0))
    LOCAL.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(LOCAL / 'row-table.npz', index=indices, target=target, group=group,
                        natural=natural, target_natural_frequency=frequency)
    outputs, rows = {}, []
    started = time.perf_counter()
    for epoch, path in epoch_paths.items():
        loaded = torch.load(path, weights_only=True, map_location='cpu')
        model.load_state_dict(loaded['head'])
        integer, nll = [], []
        with torch.inference_mode():
            for start in range(0, len(indices), 256):
                sl = slice(start, start + 256)
                raw = model(torch.from_numpy(context[sl]), torch.from_numpy(features[sl]))
                v, t = torch.from_numpy(values[sl]), torch.from_numpy(target[sl])
                integer.append(model.integer(raw, v).numpy())
                nll.append((-model.log_mass(raw, t, v)).numpy())
        integer, nll = np.concatenate(integer), np.concatenate(nll)
        output = LOCAL / f'epoch-{epoch}-predictions.npz'
        np.savez_compressed(output, integer=integer, nll=nll)
        outputs[str(output.relative_to(ROOT))] = digest(output)
        error = np.abs(integer - target)
        score = {}
        for label, mask in masks.items():
            n = int(mask.sum())
            score[label] = dict(rows=n, groups=int(len(np.unique(group[mask]))),
                exact=int(((error == 0) & mask).sum()),
                accuracy=float((error[mask] == 0).mean()) if n else None,
                mean_NLL=float(nll[mask].mean()) if n else None,
                MAE=float(error[mask].mean()) if n else None)
        row = dict(epoch=epoch, train=score,
                   historical_DEV_joint_NLL=report['history'][epoch - 1]['joint_nll'],
                   historical_online_TRAIN_fullrow_objective=report['history'][epoch - 1]['priority_train_objective_fullrow_mean'])
        if epoch == report['best_epoch']:
            assert all(torch.equal(v, state[k]) for k, v in model.state_dict().items())
            row['selected_baseline_mode_mismatches'] = int((integer != old_mode).sum())
            row['selected_baseline_max_NLL_difference'] = float(np.abs(nll - old_nll).max())
            assert row['selected_baseline_mode_mismatches'] == 0
            assert row['selected_baseline_max_NLL_difference'] <= 2e-5
        rows.append(row)
        print(json.dumps(dict(epoch=epoch, natural=score['natural'], augmented=score['augmented'])), flush=True)
    immutable_json(OUT / 'PD00.json', dict(
        id='PD00', plan_sha256=digest(OUT / 'PD00-plan.json'), history=rows,
        outputs={**outputs, str((LOCAL / 'row-table.npz').relative_to(ROOT)): digest(LOCAL / 'row-table.npz')},
        inference_analysis_seconds=time.perf_counter() - started,
        diagnostic_only=True, checkpoint_selection_unchanged=True, new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    run()
