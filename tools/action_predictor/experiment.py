"""Locked V2 experiment: prepare, fit on train/validation, then finalize on test."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .audit import immutable_json, original_turns, validate_decision
from .data import action_name, digest
from .model import ActionGRU, ActionMLP, CoordinateHead
from .targets import FAMILIES, OFFSETS, recorded_target, spatial_candidates
from .train import Turns, baseline, collate, evaluate

CONFIG = dict(seed=26, epochs=40, patience=6, batch_size=128, lr=.001,
              weight_decay=.0001, target_hidden=64, gradient_clip=1., threads=4)


def setup():
    random.seed(CONFIG['seed'])
    np.random.seed(CONFIG['seed'])
    torch.manual_seed(CONFIG['seed'])
    torch.set_num_threads(CONFIG['threads'])
    torch.use_deterministic_algorithms(True)


def load_original(data, baseline_dir, reports):
    lock = json.loads((reports/'split-lock.json').read_text())
    for path, key in ((data/'dataset.json', 'dataset_sha256'), (data/'data.npz', 'data_sha256'),
                      (baseline_dir/'model.pt', 'baseline_checkpoint_sha256'),
                      (baseline_dir/'metrics.json', 'baseline_metrics_sha256')):
        if digest(path) != lock[key]:
            raise ValueError(f'Frozen baseline/test artifact changed: {path}')
    saved = torch.load(baseline_dir/'model.pt', weights_only=True)
    model = ActionGRU(len(saved['mean']), len(saved['labels']), saved['hidden'])
    model.load_state_dict(saved['state_dict'])
    model.eval()
    return lock, saved, model


@torch.no_grad()
def prepare(data, baseline_dir, out, reports):
    if (out/'targets.npz').exists():
        raise FileExistsError('Target datasets are immutable; choose a fresh output directory')
    setup()
    lock, saved, model = load_original(data, baseline_dir, reports)
    immutable_json(reports/'plan.json', dict(config=CONFIG, split_lock_sha256=digest(reports/'split-lock.json'),
                   experiments=['V1 preserved frozen GRU', 'E1 parameter-matched stateless action MLP',
                                'E2 frozen V1 GRU states + coordinate ranker', 'E3 current state only + coordinate ranker'],
                   selection='Separate validation cross entropy; early stop. No new action-GRU tuning.',
                   target_policy='Recorded move destination and attack/cast aim coordinates; fixed +/-8 window; PRE-only candidates; no original entity IDs inferred as truth.',
                   test_policy='Evaluate locked checkpoints only after fitting is complete. Preserve all V1 test groups.'))
    manifest = json.loads((data/'dataset.json').read_text())
    source = json.loads((Path(manifest['source'])/'frozen.json').read_text())
    records = {r['raw_sha256']: r for r in source['recordings']}
    rows, coverage = {s: [] for s in ('train', 'validation', 'test')}, {s: Counter() for s in ('train', 'validation', 'test')}
    with np.load(data/'data.npz', allow_pickle=False) as archive:
        base = {key: archive[key] for key in archive.files}
    pointers = {s: 0 for s in rows}
    for rec, turn in original_turns(manifest):
        split = rec['split']
        count = len(turn['decisions'])
        i = pointers[split]
        x = torch.from_numpy(base[f'{split}_x'][i:i+count])
        y = torch.from_numpy(base[f'{split}_y'][i:i+count])
        x = (x-saved['mean'])/saved['std']
        previous = torch.cat((torch.tensor([len(saved['labels'])]), y[:-1]))
        states, _ = model.states(x[None], previous[None])
        record = records[rec['raw_sha256']]
        for j, d in enumerate(turn['decisions']):
            validate_decision(d, turn)
            family = action_name(d['label'])
            if family not in FAMILIES:
                continue
            index, reason, entity = recorded_target(d, family, record['width'], record['height'])
            coverage[split][f'{family}/{reason}'] += 1
            if index is None:
                continue
            coverage[split][f'{family}/unique_visible_entity_at_aim' if entity else f'{family}/coordinate_only'] += 1
            grid, mask, _ = spatial_candidates(d['observation'], family, record['width'], record['height'])
            rows[split].append((x[j].numpy(), states[0, j].numpy(), grid, mask, index, FAMILIES.index(family), i+j))
        pointers[split] += count
    arrays = {}
    for s, values in rows.items():
        for j, key in enumerate(('x', 'h', 'grid', 'mask', 'y', 'family', 'action_index')):
            arrays[f'{s}_{key}'] = np.stack([r[j] for r in values])
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out/'targets.npz', **arrays)
    immutable_json(reports/'target-data.json', dict(data_sha256=digest(out/'targets.npz'),
                   baseline_sha256=lock['baseline_checkpoint_sha256'], coverage=coverage,
                   candidate_features=['dx/8', 'dy/8', 'chebyshev/8', 'is_self_cell',
                                       'visible_enemy_count', 'visible_ally_count', 'visible_camp_count',
                                       'enemy_hp_fraction_sum', 'ally_hp_fraction_sum', 'camp_hp_fraction_sum'],
                   coordinate_classes=len(OFFSETS), radius=8,
                   meaning='Exact recorded coordinate conditional on action type. Unique visible occupant is diagnostic only; original entity ID is absent.'))
    print('Target preparation complete', {s: len(r) for s, r in rows.items()}, flush=True)


def target_loader(data, split, history, shuffle=False):
    context = 'h' if history else 'x'
    ds = TensorDataset(*(torch.from_numpy(data[f'{split}_{k}']) for k in (context, 'family', 'grid', 'mask', 'y')))
    return DataLoader(ds, batch_size=CONFIG['batch_size'], shuffle=shuffle)


@torch.no_grad()
def target_evaluate(model, loader, counts=None, action_correct=None):
    model.eval() if model is not None else None
    totals = {f: Counter() for f in FAMILIES}
    multiple = {f: Counter() for f in FAMILIES}
    loss, joint_correct, offset = 0., 0, 0
    for context, family, grid, mask, y in loader:
        if model is not None:
            logits = model(context, family, grid, mask)
        else:
            logits = torch.from_numpy(counts)[family].float().masked_fill(~mask, -1e9)
        prediction = logits.argmax(-1)
        if action_correct is not None:
            joint_correct += int(((prediction == y) & action_correct[offset:offset+len(y)]).sum())
        offset += len(y)
        distance = (torch.from_numpy(OFFSETS)[prediction] - torch.from_numpy(OFFSETS)[y]).abs().max(-1).values
        top3 = (logits.topk(3, dim=-1).indices == y[:, None]).any(-1)
        if model is not None:
            loss += float(nn.functional.cross_entropy(logits, y, reduction='sum'))
        for k, f in enumerate(FAMILIES):
            chosen = family == k
            totals[f].update(support=int(chosen.sum()), correct=int(((prediction == y)&chosen).sum()),
                             top3_correct=int((top3&chosen).sum()), chebyshev_error=int(distance[chosen].sum()))
            chosen = chosen & (mask.sum(-1) > 1)
            multiple[f].update(support=int(chosen.sum()), correct=int(((prediction == y)&chosen).sum()),
                               top3_correct=int((top3&chosen).sum()), chebyshev_error=int(distance[chosen].sum()))
    support = sum(t['support'] for t in totals.values())
    summary = lambda t: dict(support=t['support'], exact_accuracy=t['correct']/t['support'] if t['support'] else None,
                             top3_accuracy=t['top3_correct']/t['support'] if t['support'] else None,
                             mean_chebyshev_error=t['chebyshev_error']/t['support'] if t['support'] else None)
    result = dict(overall=summary(sum(totals.values(), Counter())),
                per_family={f: summary(t) for f, t in totals.items()},
                multiple_candidates_per_family={f: summary(t) for f, t in multiple.items()},
                cross_entropy=loss/support if model is not None else None)
    if action_correct is not None:
        if offset != len(action_correct):
            raise ValueError('Joint target/action alignment mismatch')
        result['joint_type_and_coordinate_accuracy'] = joint_correct/support
    return result


@torch.no_grad()
def action_predictions(model, loader):
    values = []
    for x, y, previous in loader:
        logits, _ = model(x, previous)
        values.append(logits.argmax(-1)[y != -100])
    return torch.cat(values)


def fit_loop(model, train_loader, validate, target=False):
    optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG['lr'], weight_decay=CONFIG['weight_decay'])
    best, epoch_best, state, history = float('inf'), 0, None, []
    for epoch in range(1, CONFIG['epochs']+1):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            if target:
                context, family, grid, mask, y = batch
                logits = model(context, family, grid, mask)
                loss = nn.functional.cross_entropy(logits, y)
            else:
                x, y, previous = batch
                logits, _ = model(x, previous)
                loss = nn.functional.cross_entropy(logits.flatten(0, 1), y.flatten(), ignore_index=-100)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), CONFIG['gradient_clip'])
            optimizer.step()
        val = validate(model)
        history.append(dict(epoch=epoch, validation_cross_entropy=val['cross_entropy']))
        if epoch % 5 == 0:
            print(history[-1], flush=True)
        if val['cross_entropy'] < best-.0001:
            best, epoch_best, state = val['cross_entropy'], epoch, copy.deepcopy(model.state_dict())
        elif epoch-epoch_best >= CONFIG['patience']:
            break
    model.load_state_dict(state)
    return dict(best_epoch=epoch_best, history=history, validation=validate(model))


def fit(data, baseline_dir, out, reports):
    if any(out.glob('*.pt')):
        raise FileExistsError('Preserve fitted checkpoints; choose a fresh experiment directory')
    setup()
    _, saved, _ = load_original(data, baseline_dir, reports)
    plan = json.loads((reports/'plan.json').read_text())
    if plan['config'] != CONFIG:
        raise ValueError('Experiment config changed after lock')
    if digest(out/'targets.npz') != json.loads((reports/'target-data.json').read_text())['data_sha256']:
        raise ValueError('Target data changed')
    original = np.load(data/'data.npz', allow_pickle=False)
    classes = len(saved['labels'])
    # No test split is loaded or scored during fitting.
    ds = {s: Turns(original, s, saved['mean'], saved['std'], classes) for s in ('train', 'validation')}
    loaders = {s: DataLoader(d, batch_size=CONFIG['batch_size'], shuffle=s=='train', collate_fn=collate) for s, d in ds.items()}
    model = ActionMLP(len(saved['mean']), classes)
    info = fit_loop(model, loaders['train'], lambda m: evaluate(m, loaders['validation'], classes))
    torch.save(dict(state_dict=model.state_dict()), out/'action-mlp.pt')
    immutable_json(reports/'E1-action-mlp.json', info | dict(parameters=sum(p.numel() for p in model.parameters()),
                   checkpoint_sha256=digest(out/'action-mlp.pt')))
    targets = np.load(out/'targets.npz', allow_pickle=False)
    for history, name in ((True, 'E2-gru-targets'), (False, 'E3-stateless-targets')):
        setup()
        model = CoordinateHead(96 if history else len(saved['mean']))
        val_loader = target_loader(targets, 'validation', history)
        info = fit_loop(model, target_loader(targets, 'train', history, True),
                        lambda m: target_evaluate(m, val_loader), target=True)
        torch.save(dict(state_dict=model.state_dict(),
                        supported_families=[FAMILIES[i] for i in np.unique(targets['train_family'])],
                        baseline_checkpoint_sha256=digest(baseline_dir/'model.pt')),
                   out/f'{name}.pt')
        immutable_json(reports/f'{name}.json', info | dict(parameters=sum(p.numel() for p in model.parameters()),
                       checkpoint_sha256=digest(out/f'{name}.pt')))
    immutable_json(reports/'candidate-lock.json', dict(plan_sha256=digest(reports/'plan.json'),
                   checkpoints={f: digest(out/f) for f in ('action-mlp.pt', 'E2-gru-targets.pt', 'E3-stateless-targets.pt')},
                   target_data_sha256=digest(out/'targets.npz'), selection='All predefined candidates locked after validation; no test-driven selection.'))


def finalize(data, baseline_dir, out, reports):
    setup()
    lock, saved, gru = load_original(data, baseline_dir, reports)
    candidates = json.loads((reports/'candidate-lock.json').read_text())
    if candidates['plan_sha256'] != digest(reports/'plan.json') or candidates['target_data_sha256'] != digest(out/'targets.npz'):
        raise ValueError('Candidate lock data/plan changed')
    for f, expected in candidates['checkpoints'].items():
        if digest(out/f) != expected:
            raise ValueError('Candidate checkpoint changed')
    original = np.load(data/'data.npz', allow_pickle=False)
    classes = len(saved['labels'])
    ds = {s: Turns(original, s, saved['mean'], saved['std'], classes) for s in ('train', 'test')}
    test = DataLoader(ds['test'], batch_size=128, collate_fn=collate)
    mlp = ActionMLP(len(saved['mean']), classes)
    mlp.load_state_dict(torch.load(out/'action-mlp.pt', weights_only=True)['state_dict'])
    actions = dict(frozen_gru=evaluate(gru, test, classes), stateless_mlp=evaluate(mlp, test, classes),
                   most_common=baseline(ds['train'], ds['test'], classes),
                   previous_action_only=baseline(ds['train'], ds['test'], classes, True))
    targets = np.load(out/'targets.npz', allow_pickle=False)
    target_indices = targets['test_action_index']
    truth = ds['test'].y[target_indices]
    gru_correct = action_predictions(gru, test)[target_indices] == truth
    mlp_correct = action_predictions(mlp, test)[target_indices] == truth
    results = {}
    for history, name in ((True, 'E2-gru-targets'), (False, 'E3-stateless-targets')):
        model = CoordinateHead(96 if history else len(saved['mean']))
        model.load_state_dict(torch.load(out/f'{name}.pt', weights_only=True)['state_dict'])
        results[name] = target_evaluate(model, target_loader(targets, 'test', history),
                                        action_correct=gru_correct if history else mlp_correct)
    counts = np.zeros((4, len(OFFSETS)), dtype=np.int64)
    np.add.at(counts, (targets['train_family'], targets['train_y']), 1)
    results['train_most_common_valid_offset'] = target_evaluate(None, target_loader(targets, 'test', True), counts)
    immutable_json(reports/'final-test.json', dict(labels=saved['labels'], actions=actions, targets=results,
                   original_test_reproduction=actions['frozen_gru']['confusion_matrix'] == json.loads((baseline_dir/'metrics.json').read_text())['test']['confusion_matrix'],
                   baseline_checkpoint_unchanged=digest(baseline_dir/'model.pt') == lock['baseline_checkpoint_sha256'],
                   candidate_lock_sha256=digest(reports/'candidate-lock.json'),
                   limitations=['Per-family target scores condition on recorded family; joint_type_and_coordinate_accuracy also requires the predicted family to be correct, on the same supported target subset.',
                                'Movement lacks terrain/path legality; attack/cast labels are recorded coordinates, not latent intent.',
                                'No original entity ID labels exist. Unique visible coordinate occupants are diagnostics only.',
                                'Existing sampled exploratory corpus, five test groups, historical engine 2/3; no playing-strength claim.']))
    print(json.dumps({n: {k: m[k] for k in ('accuracy', 'macro_f1')} for n, m in actions.items()}, indent=2))
    print(json.dumps({n: m['overall'] for n, m in results.items()}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'fit', 'finalize'])
    p.add_argument('--data', type=Path, default=Path('.cambc/action-predictor/data'))
    p.add_argument('--baseline', type=Path, default=Path('.cambc/action-predictor/run-1'))
    p.add_argument('--out', type=Path, default=Path('.cambc/action-predictor/v3'))
    p.add_argument('--reports', type=Path, default=Path('tools/action_predictor/experiments/v3'))
    args = p.parse_args()
    globals()[args.command](args.data, args.baseline, args.out, args.reports)


if __name__ == '__main__':
    main()
