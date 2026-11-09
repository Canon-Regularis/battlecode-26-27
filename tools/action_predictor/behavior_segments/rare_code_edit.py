"""Class-balanced analytic code-head edits, selected only within fitting groups."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from . import model
from .data import ROOT, REPORT as BASE, WORK as BASE_WORK, load
from .study import check, evaluate
from ..audit import immutable_json
from ..data import digest

REPORT = ROOT / 'tools/action_predictor/experiments/v45'
WORK = ROOT / '.cambc/action-predictor/v45'


def metrics(y, prediction, classes=None):
    y, prediction = np.asarray(y), np.asarray(prediction)
    classes = sorted(set(map(int, y))) if classes is None else list(classes)
    per = {}
    for k in classes:
        n, p = int((y == k).sum()), int((prediction == k).sum())
        tp = int(((y == k) & (prediction == k)).sum())
        recall, precision = tp / n if n else 0., tp / p if p else 0.
        per[str(k)] = dict(rows=n, predicted=p, correct=tp, recall=recall,
                           precision=precision, f1=2*tp/(n+p) if n+p else 0.)
    return dict(accuracy=float((y == prediction).mean()), per_code=per,
                balanced_recall=float(np.mean([p['recall'] for p in per.values()])),
                macro_f1=float(np.mean([p['f1'] for p in per.values()])),
                minimum_recall=min(p['recall'] for p in per.values()))


def solve_head(x, y, ridge, classes):
    """Weighted ridge in normalized hidden coordinates, folded into original head."""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.int64)
    if ridge <= 0 or not np.isfinite(x).all():
        raise ValueError('Positive ridge and finite inputs required')
    if set(map(int, y)) != set(classes):
        raise ValueError('Every trained class must have examples in this fold')
    mean, scale = x.mean(0), x.std(0).clip(1e-4)
    z = np.column_stack(((x-mean)/scale, np.ones(len(x))))
    counts = np.bincount(y, minlength=8)
    weights = np.asarray([len(y)/(len(classes)*counts[k]) for k in y])
    target = np.eye(8)[y][:, classes]
    penalty = np.eye(z.shape[1])*ridge
    penalty[-1, -1] = 0.
    coefficients = np.linalg.solve(z.T @ (weights[:, None]*z) + penalty,
                                   z.T @ (weights[:, None]*target))
    # Fixed temperature preserves argmax; absent classes are explicitly unsupported.
    weight = np.zeros((8, x.shape[1]), np.float64)
    bias = np.full(8, -30., np.float64)
    weight[classes] = 4*coefficients[:-1].T/scale
    bias[classes] = 4*coefficients[-1] - weight[classes] @ mean
    return weight, bias


def make_state(base, history_scale, weight=None, bias=None):
    state = {k: v.clone() for k, v in base.items()}
    state['memory.weight_ih'][:, 32:55] *= history_scale
    if weight is not None:
        state['code.weight'] = torch.as_tensor(weight, dtype=base['code.weight'].dtype)
        state['code.bias'] = torch.as_tensor(bias, dtype=base['code.bias'].dtype)
    return state


def folds(groups):
    ordered = sorted(set(groups), key=lambda g: hashlib.sha256(str(g).encode()).hexdigest())
    return {g: i % 4 for i, g in enumerate(ordered)}


def select(banks, y, groups, ridge_values):
    assignment = folds(groups)
    ids = np.asarray([assignment[g] for g in groups])
    classes = sorted(set(map(int, y)))
    results = {}
    for scale, x in banks.items():
        for ridge in ridge_values:
            prediction = np.full(len(y), -1)
            for fold in range(4):
                train, held = ids != fold, ids == fold
                weight, bias = solve_head(x[train], y[train], ridge, classes)
                prediction[held] = (x[held] @ weight.T + bias).argmax(1)
            name = f'history{scale:g}_ridge{ridge:g}'
            results[name] = dict(history_scale=scale, ridge=ridge,
                                 metrics=metrics(y, prediction, classes))
    chosen = min(results, key=lambda k: (-results[k]['metrics']['minimum_recall'],
                                        -results[k]['metrics']['macro_f1'],
                                        -results[k]['metrics']['accuracy'], k))
    return chosen, results, assignment


def freeze():
    REPORT.mkdir(parents=True, exist_ok=True)
    plan = json.loads((BASE/'protocol.json').read_text()); check(plan)
    inputs = [BASE/'protocol.json', BASE/'discovery.json', BASE_WORK/'S01-run/final.pt',
              ROOT/'tools/action_predictor/experiments/v44/result.json']
    inputs += [BASE_WORK/'S01-run'/f'{split}-predictions.json' for split in ('fit', 'evaluation')]
    immutable_json(REPORT/'plan.json', dict(
        sources={str(p.relative_to(ROOT)): digest(p) for p in (
            Path(__file__), Path(__file__).with_name('test_rare_code_edit.py'))},
        inputs={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        history_scales=[1., 5.], ridge_values=[.01, .1, 1., 10., 100.], seconds_cap=900,
        selection='Ten analytic head edits; four whole-group folds inside existing fitting groups. '
        'Maximize minimum supported-class recall, then macro-F1, then accuracy, then name. '
        'Refit selected head on all fitting queries; publish selection before evaluation. '
        'Backbone was previously fitted on these groups, so folds validate head calibration only.',
        objective='Class-balanced squared error to one-hot labels; hidden normalization per training fold; '
        'positive ridge; unpenalized intercept; fixed logit scale4. Fold normalization into code.weight/bias. '
        'No gradient descent or optimizer. Only code head and optionally23GRU history columns change.',
        requirements='All fitting-supported evaluation codes: recall>=.25 and precision>=.10. '
        'Overall code accuracy loss<=.05, movement accuracy loss<=.01, movementNLL increase<=.01, '
        'goalwithin2 loss<=.02 and mean goalerror increase<=.25 vs original S01. '
        'No claim of zero misses; any unseen evaluation code prevents complete coverage.',
        scope='Previously exposed research data; inferred hindsight labels. No subagents, playing-bot edits, '
        'new replay payloads, or automatic promotion. Original and V44 checkpoints preserved.'))


def checks(value, reference, code_metrics, supported, unseen):
    a, b = value['summary'], reference['summary']
    per = code_metrics['per_code']
    return dict(supported_recall=all(per[str(k)]['rows'] > 0 and per[str(k)]['recall'] >= .25 for k in supported),
                supported_precision=all(per[str(k)]['precision'] >= .10 for k in supported),
                complete_code_coverage=not unseen,
                code_accuracy=a['code_accuracy'] >= b['code_accuracy']-.05,
                movement_accuracy=a['movement_accuracy'] >= b['movement_accuracy']-.01,
                movement_nll=a['movement_nll'] <= b['movement_nll']+.01,
                goal_within2=a['goal_within2'] >= b['goal_within2']-.02,
                goal_error=a['mean_goal_error'] <= b['mean_goal_error']+.25)


def run():
    frozen = json.loads((REPORT/'plan.json').read_text())
    for kind in ('sources', 'inputs'):
        for p, h in frozen[kind].items():
            assert digest(ROOT/p) == h, p
    WORK.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter(); deadline = start + frozen['seconds_cap']; torch.set_num_threads(4)
    plan = json.loads((BASE/'protocol.json').read_text()); check(plan)
    discovery = json.loads((BASE/'discovery.json').read_text())
    windows, maps = load(); fitting = [w for w in windows if w['partition'] == 'fit']
    cache = {w['key']: model.encode_window(w, maps[w['payload']], plan['schema'])[0] for w in fitting}
    base = torch.load(BASE_WORK/'S01-run/final.pt', map_location='cpu', weights_only=False)['model']
    net = model.SegmentPolicy(plan['schema'], 8).eval(); capture = {}
    handle = net.code.register_forward_pre_hook(lambda module, args: capture.update(hidden=args[0].detach().numpy()))
    banks, y, groups, identities = {}, [], [], []
    for scale in frozen['history_scales']:
        net.load_state_dict(make_state(base, scale)); hidden = []
        with torch.no_grad():
            for w in fitting:
                if time.perf_counter() >= deadline: raise TimeoutError('Feature budget exceeded')
                net(**cache[w['key']]); take = cache[w['key']]['observed'].bool().numpy()
                hidden.extend(capture['hidden'][take])
                if scale == frozen['history_scales'][0]:
                    for i in np.flatnonzero(take):
                        y.append(discovery['labels'][w['key']][i]); groups.append(w['group'])
                        identities.append([w['key'], int(i)])
        banks[scale] = np.asarray(hidden, np.float64)
    handle.remove(); y = np.asarray(y)
    chosen, candidates, assignment = select(banks, y, groups, frozen['ridge_values'])
    candidate = candidates[chosen]; scale = candidate['history_scale']; supported = sorted(set(map(int, y)))
    weight, bias = solve_head(banks[scale], y, candidate['ridge'], supported)
    state = make_state(base, scale, weight, bias)
    assert all(torch.isfinite(v).all() for v in state.values())
    np.savez_compressed(WORK/'fitting-hidden.npz', **{f'history{s:g}': x for s,x in banks.items()}, labels=y)
    immutable_json(WORK/'fitting-identities.json', dict(identities=identities, groups=groups))
    torch.save(dict(model=state, inference_only=True, selected=chosen, supported_codes=supported,
                    base_checkpoint_sha256=digest(BASE_WORK/'S01-run/final.pt'),
                    plan_sha256=digest(REPORT/'plan.json')), WORK/'selected.pt')
    immutable_json(REPORT/'selection.json', dict(selected=chosen, candidates=candidates,
                   folds=assignment, supported_codes=supported, plan_sha256=digest(REPORT/'plan.json'),
                   checkpoint_sha256=digest(WORK/'selected.pt')))
    print('Selected', chosen, json.dumps(candidate), flush=True)
    net.load_state_dict(state); results = {}
    for split in ('fit', 'evaluation'):
        if split == 'evaluation':
            for w in windows:
                if w['partition'] == split:
                    cache[w['key']] = model.encode_window(w, maps[w['payload']], plan['schema'])[0]
        value = evaluate(net, windows, maps, cache, discovery, split, deadline)
        reference = json.loads((BASE_WORK/'S01-run'/f'{split}-predictions.json').read_text())
        truth = [r['code_label'] for r in value['records']]
        codes = metrics(truth, [r['code_prediction'] for r in value['records']], sorted(set(truth) | set(supported)))
        unseen = sorted(set(truth)-set(supported))
        guards = checks(value, reference, codes, supported, unseen)
        results[split] = dict(summary=value['summary'], codes=codes, unseen_codes=unseen,
                              checks=guards, passed=all(guards.values()))
        immutable_json(WORK/f'{split}-predictions.json', value)
        print(split, json.dumps(results[split]), flush=True)
    for p,h in frozen['inputs'].items(): assert digest(ROOT/p) == h, p
    bindings = {str(p.relative_to(ROOT)): digest(p) for p in WORK.iterdir() if p.is_file()}
    elapsed = time.perf_counter()-start
    if elapsed >= frozen['seconds_cap']: raise TimeoutError('Publication budget exceeded')
    immutable_json(REPORT/'result.json', dict(selected=chosen, results=results, seconds=elapsed,
        selection_sha256=digest(REPORT/'selection.json'), bindings=bindings,
        changed_tensors={k: int((v != base[k]).sum()) for k,v in state.items() if not torch.equal(v,base[k])},
        optimizer_updates=0, analytic_head_fits=41,
        passed=all(v['passed'] for v in results.values()), original_checkpoint_unchanged=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=('freeze','run'))
    freeze() if parser.parse_args().command == 'freeze' else run()
