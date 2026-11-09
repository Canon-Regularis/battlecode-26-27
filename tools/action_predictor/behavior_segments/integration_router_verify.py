"""Direct parent checks of router data, training accounting and runtime decisions."""
import argparse
import json
import math
import time
import numpy as np
import torch
from . import integration_router_fit as f
from . import full_action_evaluate as e
from .integration_router import MovementRouter, normalized_router, TrainedMovementRouter, features
from ..audit import immutable_json
from ..data import digest, action_name
from ..rich_data import read_turns


def prefit():
    start = time.perf_counter(); plan = f.inputs(); data = f.load_data()
    records = e.read(f.WORK / 'train-forecasts.json'); xs = []; identities = 0
    with np.load(f.TRAIN_TARGET) as z: target = {k: z[k] for k in ('y', 'py', 'group')}
    local = 0
    for job in plan['jobs']:
        n = job['rows']; span = slice(local, local + n); offset = job['offset']
        with np.load(job['shard']) as z:
            xs.append(z['x'])
            if not np.array_equal(z['y'], target['y'][offset:offset + n]): raise ValueError('Canonical shard labels differ')
            if not np.array_equal(z['group'], target['group'][offset:offset + n]): raise ValueError('Canonical groups differ')
        if not np.all(data['fold'][span] == plan['folds'][job['record']['group']]): raise ValueError('Fold membership differs')
        i = 0
        for t in read_turns(job['manifest'], job['record']):
            for d in t['decisions']:
                r = records[local + i]; row = offset + i
                if (r['row'], r['event'], r['actor'], r['round']) != (row, d['event_cursor'], t['actor'], t['round']):
                    raise ValueError('Forecast identity mismatch')
                if action_name(d['label']) != e.LABELS[target['y'][row]]: raise ValueError('Recorded family mismatch')
                py = target['py'][row]
                if 0 <= py < 289:
                    pos = d['observation']['own']['position']; dest = d['label']['to']
                    if py != (dest['y'] - pos['y'] + 8) * 17 + dest['x'] - pos['x'] + 8:
                        raise ValueError('Recorded coordinate mismatch')
                identities += 1; i += 1
        if i != n: raise ValueError('Missing selected root')
        local += n
    reconstructed = f.make_data(records, 'train', np.concatenate(xs))
    for k, v in reconstructed.items():
        if not np.array_equal(v, data[k]): raise ValueError('Prepared array differs: ' + k)
    # No optimizer or DEV data: reconstruct each train-only fold normalizer.
    folds = []
    for fold in range(4):
        train = (data['fold'] != fold) & data['active']; held = data['fold'] == fold
        if set(data['groups'][train]) & set(data['groups'][held]): raise ValueError('Router fold group leakage')
        net = normalized_router(data['x'][train])
        if not torch.equal(net.output.weight, torch.zeros_like(net.output.weight)): raise ValueError('Nonzero initial weight')
        if not torch.equal(net.output.bias, torch.zeros_like(net.output.bias)): raise ValueError('Nonzero initial bias')
        folds.append(dict(fold=fold, training_disagreements=int(train.sum()), held_rows=int(held.sum())))
    immutable_json(f.REPORT / 'prefit-verification.json', dict(data_sha256=digest(f.REPORT / 'data.json'),
        source_sha256=digest(__file__), canonical_rows=identities, all_features_and_targets_exact=True,
        folds=folds, assessment_loaded=False, optimizer_updates=0, seconds=time.perf_counter() - start))


def final():
    start = time.perf_counter(); plan = f.inputs(); data = f.load_data(); torch.set_num_threads(1)
    selection = e.read(f.REPORT / 'selection.json'); refit = e.read(f.REPORT / 'refit.json')
    e.check(selection['bindings']); e.check(refit['bindings'])
    if f.select(selection['candidates']) != selection['selected']: raise ValueError('Selection mismatch')
    total = 0; changed = {}; values = []
    for name in [f'fold-{i}' for i in range(4)] + ['refit']:
        full = name == 'refit'; fold = -1 if full else int(name[-1]); held = np.ones(len(data['x']), bool) if full else data['fold'] == fold
        train_mask = data['active'] & (np.ones(len(data['x']), bool) if full else data['fold'] != fold)
        train = np.flatnonzero(train_mask); epoch_count = selection['selected']['epoch'] if full else max(plan['epochs'])
        directory = f.WORK / name; initial = torch.load(directory / 'epoch-00.pt', weights_only=False)
        torch.manual_seed(plan['seed']); expected = normalized_router(data['x'][train])
        for k, v in expected.state_dict().items():
            if not torch.equal(v, initial['model'][k]): raise ValueError('Initialization/normalization mismatch')
        if initial['optimizer']['state']: raise ValueError('Nonempty initial optimizer')
        trace = e.read(directory / 'trace.json'); rng = np.random.default_rng(plan['seed']); updates = 0
        for epoch, entry in enumerate(trace, 1):
            order = rng.permutation(train)
            if entry['epoch'] != epoch or order.tolist() != entry['order']: raise ValueError('Sampler mismatch')
            count = math.ceil(len(train) / plan['batch']); updates += count
            if entry['updates'] != updates or len(entry['gradient_norms']) != count or len(entry['losses']) != count:
                raise ValueError('Update accounting mismatch')
            if not np.isfinite(entry['gradient_norms'] + entry['losses']).all(): raise ValueError('Nonfinite archived training')
            path = directory / f'epoch-{epoch:02d}.pt'
            if path.exists():
                checkpoint = torch.load(path, weights_only=False)
                if checkpoint['rng'] != rng.bit_generator.state: raise ValueError('RNG mismatch')
                if checkpoint['updates'] != updates: raise ValueError('Checkpoint updates mismatch')
                settings = checkpoint['optimizer']['param_groups'][0]
                if settings['lr'] != plan['learning_rate'] or settings['weight_decay'] != plan['weight_decay']:
                    raise ValueError('Optimizer settings mismatch')
                for state in checkpoint['optimizer']['state'].values():
                    if int(state['step']) != updates or not all(torch.isfinite(v).all() for v in state.values() if torch.is_tensor(v)):
                        raise ValueError('Optimizer state mismatch')
        if len(trace) != epoch_count: raise ValueError('Epoch count mismatch')
        total += updates; measured = {}
        for path in directory.glob('epoch-*.pt'):
            saved = torch.load(path, weights_only=False); state = saved['model']
            if not torch.equal(state['mean'], initial['model']['mean']) or not torch.equal(state['scale'], initial['model']['scale']):
                raise ValueError('Normalizer changed during fitting')
            model = MovementRouter(state['mean'], state['scale']); model.load_state_dict(state)
            score = f.scores(model, data)
            if not np.array_equal(score[held], saved['held_scores']): raise ValueError('Saved fold scores differ')
            measured[saved['epoch']] = f.summarize(data, score, held)
        changed[name] = sum(not torch.equal(v, initial['model'][k]) for k, v in state.items())
        if full:
            if measured[epoch_count] != refit['fit']: raise ValueError('Refit summary differs')
        else: values.append(measured)
    candidates = [dict(epoch=epoch, **{k: sum(v[epoch][k] for v in values) for k in values[0][epoch]}) for epoch in plan['epochs']]
    if candidates != selection['candidates'] or total != refit['total_updates']: raise ValueError('Pooled selection/accounting differs')
    selected = torch.load(f.WORK / 'selected.pt', weights_only=False)
    selected_checkpoint = torch.load(f.WORK / 'refit' / f"epoch-{selection['selected']['epoch']:02d}.pt", weights_only=False)
    if any(not torch.equal(v, selected_checkpoint['model'][k]) for k, v in selected['model'].items()): raise ValueError('Selected weights differ')
    result = e.read(f.REPORT / 'result.json'); e.check(result['bindings']); e.check(plan['assessment_inputs'])
    original = e.read(e.WORK / 'forecasts.json'); filtered = e.read(f.WORK / 'validation-forecasts.json')
    with np.load(e.TARGET) as z: current = z['x']
    dev = f.make_data(original, 'validation', current)
    runtime = TrainedMovementRouter(); score = f.scores(runtime.net, dev)
    with np.load(f.WORK / 'validation-router.npz') as z:
        if not np.array_equal(score, z['score']) or not np.array_equal(dev['active'], z['active']): raise ValueError('Assessment scores differ')
    expected = [dict(r, eligible=r['eligible'] and bool(score[i] > 0 and dev['active'][i])) for i, r in enumerate(original)]
    if expected != filtered: raise ValueError('Routing decisions differ')
    measured, arrays = e.calculate(filtered)
    for k in measured:
        if k not in ('new_fits', 'optimizer_updates') and result[k] != measured[k]: raise ValueError('Assessment metrics differ: ' + k)
    if result['routing'] != f.summarize(dev, score, np.ones(len(score), bool)): raise ValueError('Routing counts differ')
    with np.load(f.WORK / 'validation-decisions.npz') as z:
        if any(not np.array_equal(v, z[k]) for k, v in arrays.items()): raise ValueError('Assessment decision archive differs')
    with np.load(e.BASELINE) as z: action = z['prediction']; coordinate = z['proposed_coordinate']
    probes = 0
    for i, r in enumerate(original):
        value = runtime.predict(current[i], r, int(action[i]), int(coordinate[i]), dev['old_mode_logp'][i], dev['type_logp'][i])
        if value['coordinate'] != arrays['proposed_coordinate'][i]: raise ValueError('Runtime/evaluator mismatch')
        probes += 1
    immutable_json(f.REPORT / 'verification.json', dict(result_sha256=digest(f.REPORT / 'result.json'),
        verifier_sha256=digest(__file__), total_optimizer_updates=total, changed_tensors=changed,
        all_fold_scores_exact=True, all_assessment_scores_exact=True, runtime_decisions=probes,
        optimizer_replays=0, subagents=False, seconds=time.perf_counter() - start))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('prefit', 'final'))
    globals()[p.parse_args().command]()
