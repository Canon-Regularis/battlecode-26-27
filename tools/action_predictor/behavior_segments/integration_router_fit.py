"""Fitting-game-selected training of a frozen-policy movement router (V75)."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch

from . import full_action_evaluate as e
from .integration_router import features, normalized_router, MovementRouter, FEATURE_COUNT
from ..audit import immutable_json
from ..data import digest
from ..priority_regularized.safety import dependency_files
from ..trajectory_history.feature_sources import load_game as restored_game

ROOT = e.ROOT; REPORT = ROOT / 'tools/action_predictor/experiments/v75'; WORK = ROOT / '.cambc/action-predictor/v75'
TRAIN_TARGET = ROOT / '.cambc/action-predictor/v5/combined-train.npz'
TRAIN_BASELINE = ROOT / '.cambc/action-predictor/v27/JP02-train-predictions.npz'


def inputs():
    plan = e.read(REPORT / 'plan.json'); e.check(plan['sources']); e.check(plan['training_inputs'])
    return plan


def freeze():
    if REPORT.exists(): raise FileExistsError('Preserve V75')
    old = e.read(ROOT / 'tools/action_predictor/experiments/v42/r2/evaluator-plan.json')
    chosen = {j['payload'] for j in old['jobs'] if j['partition'] == 'fit'}
    jobs = [j for j in e.read(e.JOBS) if j['split'] == 'train' and j['record']['raw_sha256'] in chosen]
    if len(jobs) != 32: raise ValueError('Fitting-only game membership changed')
    groups = sorted({j['record']['group'] for j in jobs}, key=lambda g: hashlib.sha256(('router75:' + g).encode()).hexdigest())
    if len(groups) != 32: raise ValueError('Expected one fitting game per group')
    folds = {g: i % 4 for i, g in enumerate(groups)}
    records_path = ROOT / 'tools/action_predictor/experiments/v32/window-validation.json'
    records = {r['payload']: r for r in e.read(records_path)['games']}
    paths = [e.JOBS, TRAIN_TARGET, TRAIN_BASELINE, records_path,
             ROOT / 'tools/action_predictor/experiments/v42/r2/evaluator-plan.json',
             ROOT / 'tools/action_predictor/experiments/v59/result.json',
             ROOT / '.cambc/action-predictor/v59/selected.pt',
             ROOT / 'tools/action_predictor/experiments/v74/verification.json',
             ROOT / '.cambc/action-predictor/v7/train-direction.npy']
    paths += [ROOT / f'.cambc/action-predictor/v26/family-cache/train/{k}.npy'
              for k in ('type_logp', 'mode_joint_logp')]
    for j in jobs:
        r = records[j['record']['raw_sha256']]
        if r['partition'] != 'fit': raise ValueError('Protected fitting boundary')
        e.check(r['bindings']); paths.extend(r['bindings'])
        paths += [Path(j['shard']), Path(j['record']['augmented_path'])]
        for kind in ('supplement', 'augmentation'):
            path = Path(j['work']) / kind / j['record']['raw_sha256'] / 'pre.jsonl'
            if path.exists(): paths.append(path)
        paths.append(ROOT / 'tools/action_predictor/experiments/v32/window-proposals' / (r['payload'] + '.json'))
    # Validate retained predictor and canonical population against prior receipts.
    jp = e.read(ROOT / 'tools/action_predictor/experiments/v27/JP-results.json')
    for path in (TRAIN_BASELINE, TRAIN_TARGET):
        key = str(path.relative_to(ROOT)).replace('\\', '/')
        expected = next(h for p, h in jp['bindings'].items() if p.replace('\\', '/') == key)
        if digest(path) != expected: raise ValueError('Historical training binding changed')
    dev = e.read(ROOT / 'tools/action_predictor/experiments/v74/plan.json')
    if set(groups) & set(dev['groups']): raise ValueError('DEV group overlap')
    assessment = [e.BASELINE, e.TARGET, ROOT / '.cambc/action-predictor/v74/forecasts.json',
                  ROOT / 'tools/action_predictor/experiments/v74/forecast.json',
                  ROOT / '.cambc/action-predictor/v7/validation-direction.npy']
    assessment += [ROOT / f'.cambc/action-predictor/v26/family-cache/validation/{k}.npy'
                   for k in ('type_logp', 'mode_joint_logp')]
    roots = ('tools.action_predictor.behavior_segments.integration_router_fit',
             'tools.action_predictor.behavior_segments.test_integration_router')
    REPORT.mkdir(parents=True)
    immutable_json(REPORT / 'plan.json', dict(sources=e.bind(dependency_files(ROOT, roots)),
        training_inputs=e.bind(paths), assessment_inputs=e.bind(assessment), jobs=jobs, folds=folds,
        seed=75001, epochs=[0, 4, 8, 16, 32], learning_rate=.003, weight_decay=.01, clip=5., batch=128,
        features=FEATURE_COUNT, parameters=FEATURE_COUNT + 1, preparation_seconds_cap=2400, fitting_seconds_cap=300,
        intervention='Train one 273-input tanh linear router to predict V59-minus-JP02 complete-command correctness. '
                     'Inputs are canonical253PRE features,9V59 probabilities,11confidence/offset/history summaries. '
                     'Both experts and action choices frozen. Route only eligible located predicted-move disagreements '
                     'with positive expected gain. Zero initialization/ties choose JP02.',
        objective='Mean squared error on every eligible predicted-move disagreement, including both-wrong targets0. '
                  'Targets+1 rescue,-1 regression,0 tie. No class balancing, current label input or DEV gradient.',
        selection='Four whole-game folds,24train/8held. Mean/std fit only active training queries within each fold. '
                  'Pool complete-command counts over all held rows at epochs0,4,8,16,32; require no change-count loss '
                  'and continuation loss <=0.5percentage points vsJP02. Choose most correct,then earlier epoch. '
                  'Epoch0 exact baseline eligible. One fresh full32game refit for selected duration.',
        history='Exactly V74 chronological adapter, cached PRE masks, prior-turn commands and32turn resets. '
                'Training loader adds canonical augmented selected PREs; same predict-before-assimilate ordering.',
        evaluation='After selection and full refit, apply once to all14439 archived V74 DEV forecasts. '
                   'No threshold search, repeats or DEV-derived routing. Report every category, paired groups, '
                   'rescue/regression,changes/continuation,false positives,coverage and baseline/unconditional references.',
        limits='Router folds exclude their own updates, but frozen V59/JP02 experts previously trained on these '
               'fitting groups. Not end-to-end out-of-fold forecasts. Original DEV repeatedly exposed, teacher-forced '
               'history,missing observations,shops and ambiguous targets. Decision routing is not calibrated joint MAP.',
        subagents=False, reserved_opened=0, promoted=False))


def load_training_game(job):
    records = e.read(ROOT / 'tools/action_predictor/experiments/v32/window-validation.json')['games']
    r = next(r for r in records if r['payload'] == job['record']['raw_sha256'])
    if r['partition'] != 'fit' or job['split'] != 'train': raise ValueError('Not fitting data')
    v = restored_game(job, r); actors = {}
    for actor, roots in v['actors'].items():
        if not any(f['actor'] == actor for event, f in v['frames'].items() if event in v['selected']): continue
        turns = defaultdict(list)
        for root in roots:
            turns[root['turn']].append(dict(event=root['event'], family=root['family'], step=root['step'],
                                           root=root['root'], turn=root['indexed_turn']))
        actors[actor] = sorted(turns.values(), key=lambda rs: e.cursor(rs[0]['event']))
    return v['route'], {event: job['offset'] + i for event, i in v['selected'].items()}, v['frames'], actors


def training_forecast(job, predictor):
    # Same streaming algorithm as V74, with only the augmented fitting loader changed.
    route, selected, frames, actors = load_training_game(job); records = []
    for actor, turns in sorted(actors.items()):
        adapter = e.TurnMovementAdapter(predictor); prev_roots = None; prev_frame = None
        last = max(e.cursor(event) for event in selected if frames[event]['actor'] == actor)
        for roots in turns:
            if e.cursor(roots[0]['event']) > last: break
            adapter.begin_turn(); anchor = None
            for r in roots:
                event = r['event']; scored = event in selected
                if not (scored or (not adapter.seen_nonadmin and r['family'] not in e.ADMIN)): continue
                f = frames.get(event); current = None if f is None else dict(observation=f['observation'], supplement=f['supplement'])
                previous, mask, moves = e.prior_inputs(prev_roots, prev_frame, f, route)
                value = adapter.predict(current, route, r['turn']['round'], previous, mask, moves)
                if scored:
                    records.append(dict(row=selected[event], payload=job['record']['raw_sha256'], actor=actor,
                        event=event, round=r['turn']['round'], eligible=value['eligible'], movement=value['movement'],
                        history_turns=0 if adapter.state is None else adapter.state['turns'],
                        probabilities=None if value['forecast'] is None else value['forecast']['movement_probabilities']))
                if not adapter.seen_nonadmin and r['family'] not in e.ADMIN: anchor = f
                adapter.observe(r['family'])
            previous, mask, moves = e.prior_inputs(prev_roots, prev_frame, None, route)
            adapter.finish_turn(route, roots[0]['turn']['round'], previous, mask, moves)
            prev_roots, prev_frame = roots, anchor
    if sorted(r['row'] for r in records) != list(range(job['offset'], job['offset'] + job['rows'])):
        raise ValueError('Training forecast coverage changed')
    return sorted(records, key=lambda r: r['row'])


def make_data(records, split, current):
    indices = np.array([r['row'] for r in records]); n = len(indices)
    baseline = TRAIN_BASELINE if split == 'train' else e.BASELINE
    with np.load(baseline) as z: old = {k: z[k][indices] for k in ('prediction', 'proposed_coordinate', 'coordinate', 'priority')}
    family = ROOT / f'.cambc/action-predictor/v26/family-cache/{split}'
    type_lp = np.load(family / 'type_logp.npy', mmap_mode='r')[indices, 8]
    conditional_lp = np.load(family / 'mode_joint_logp.npy', mmap_mode='r')[indices, 8] - type_lp
    alternative = old['proposed_coordinate'].copy(); x = np.zeros((n, FEATURE_COUNT), np.float32); active = np.zeros(n, bool)
    for i, r in enumerate(records):
        alternative[i] = e.dispatch(int(old['prediction'][i]), int(alternative[i]), r['movement'], r['eligible'])
        active[i] = alternative[i] != old['proposed_coordinate'][i]
        if active[i]: x[i] = features(current[i], r['probabilities'], int(old['proposed_coordinate'][i]),
                                     conditional_lp[i], type_lp[i], r['history_turns'])
    # Targets are introduced only after the complete inference feature arrays exist.
    target = TRAIN_TARGET if split == 'train' else e.TARGET
    with np.load(target) as z: raw = {k: z[k][indices] for k in ('y', 'py', 'priority', 'group')}
    a = e.correctness(raw, old)[1]; conditional = old['coordinate'].copy()
    conditional[(raw['y'] == 8) & active] = alternative[(raw['y'] == 8) & active]
    b = e.correctness(raw, dict(old, coordinate=conditional))[1]
    gain = b.astype(np.float32) - a.astype(np.float32)
    if np.any(gain[~active]): raise ValueError('Unroutable target gain')
    direction = np.load(ROOT / f'.cambc/action-predictor/v7/{split}-direction.npy', mmap_mode='r')[indices]
    return dict(x=x, active=active, gain=gain, baseline=a, alternative=b, indices=indices,
                y=raw['y'], direction=direction, groups=raw['group'], proposed=old['proposed_coordinate'],
                alternative_coordinate=alternative, old_mode_logp=conditional_lp, type_logp=type_lp)


def prepare():
    start = time.perf_counter(); plan = inputs(); WORK.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1); predictor = e.TrajectoryMovementPredictor(); records = []; xs = []; fold_rows = []
    for i, job in enumerate(plan['jobs'], 1):
        if time.perf_counter() - start >= plan['preparation_seconds_cap']: raise TimeoutError('Preparation cap')
        rows = training_forecast(job, predictor); immutable_json(WORK / (job['record']['raw_sha256'] + '.json'), rows)
        records.extend(rows)
        with np.load(job['shard']) as z: xs.append(z['x'])
        fold_rows.extend([plan['folds'][job['record']['group']]] * len(rows))
        print('Router fitting forecasts', i, '/32', len(records), 'rows', flush=True)
    if [r['row'] for r in records] != sorted(r['row'] for r in records): raise ValueError('Canonical job order changed')
    immutable_json(WORK / 'train-forecasts.json', records)
    data = make_data(records, 'train', np.concatenate(xs)); data['fold'] = np.array(fold_rows)
    np.savez_compressed(WORK / 'train-data.npz', **data)
    elapsed = time.perf_counter() - start
    if elapsed >= plan['preparation_seconds_cap']: raise TimeoutError('Preparation publication cap')
    immutable_json(REPORT / 'data.json', dict(plan_sha256=digest(REPORT / 'plan.json'),
        bindings=e.bind(WORK.glob('*')), rows=len(records), active=int(data['active'].sum()),
        target_counts={str(g): int(((data['gain'] == g) & data['active']).sum()) for g in (-1, 0, 1)}, seconds=elapsed))


def load_data():
    receipt = e.read(REPORT / 'data.json'); e.check(receipt['bindings'])
    with np.load(WORK / 'train-data.npz') as z: return {k: z[k] for k in z.files}


@torch.no_grad()
def scores(net, data):
    return net(torch.from_numpy(data['x'])).numpy()


def summarize(data, score, mask):
    use = (score > 0) & data['active']; correct = data['baseline'].astype(np.int32) + use * data['gain'].astype(np.int32)
    changes = mask & (data['y'] == 8) & (data['direction'] == 3)
    continues = mask & (data['y'] == 8) & (data['direction'] == 2)
    return dict(rows=int(mask.sum()), complete=int(correct[mask].sum()), baseline=int(data['baseline'][mask].sum()),
        changes=int(correct[changes].sum()), baseline_changes=int(data['baseline'][changes].sum()),
        continuations=int(correct[continues].sum()), baseline_continuations=int(data['baseline'][continues].sum()),
        continuation_rows=int(continues.sum()), routed_disagreements=int((use & mask).sum()),
        rescues=int((use & mask & (data['gain'] == 1)).sum()), regressions=int((use & mask & (data['gain'] == -1)).sum()))


def train_one(data, fitting, held, plan, epochs, directory, deadline):
    directory.mkdir(parents=True, exist_ok=False); train = np.flatnonzero(fitting & data['active'])
    if len(train) == 0: raise ValueError('No active training rows')
    torch.manual_seed(plan['seed']); net = normalized_router(data['x'][train]); opt = torch.optim.AdamW(
        net.parameters(), lr=plan['learning_rate'], weight_decay=plan['weight_decay'])
    rng = np.random.default_rng(plan['seed']); trace = []; measurements = {}; updates = 0
    def save(epoch):
        score = scores(net, data)
        measurements[epoch] = summarize(data, score, held)
        torch.save(dict(model=net.state_dict(), optimizer=opt.state_dict(), rng=rng.bit_generator.state,
                        updates=updates, epoch=epoch, held_scores=score[held]), directory / f'epoch-{epoch:02d}.pt')
    save(0)
    for epoch in range(1, epochs + 1):
        order = rng.permutation(train); norms = []; losses = []
        for begin in range(0, len(order), plan['batch']):
            if time.perf_counter() >= deadline: raise TimeoutError('Fitting cap')
            ids = order[begin:begin + plan['batch']]; prediction = net(torch.from_numpy(data['x'][ids]))
            loss = ((prediction - torch.from_numpy(data['gain'][ids])) ** 2).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); norm = torch.nn.utils.clip_grad_norm_(net.parameters(), plan['clip'])
            if not torch.isfinite(loss) or not torch.isfinite(norm): raise ValueError('Nonfinite routing update')
            opt.step(); updates += 1; norms.append(float(norm)); losses.append(float(loss.detach()))
        trace.append(dict(epoch=epoch, order=order.tolist(), gradient_norms=norms, losses=losses, updates=updates))
        if epoch in plan['epochs'] or epoch == epochs: save(epoch)
    immutable_json(directory / 'trace.json', trace)
    return net, measurements, updates


def select(candidates):
    eligible = [c for c in candidates if c['changes'] >= c['baseline_changes'] and
                c['continuations'] >= c['baseline_continuations'] - .005 * c['continuation_rows']]
    return min(eligible, key=lambda c: (-c['complete'], c['epoch']))


def fit():
    start = time.perf_counter(); plan = inputs(); data = load_data(); torch.set_num_threads(1)
    deadline = start + plan['fitting_seconds_cap']; all_values = []; updates = 0
    for fold in range(4):
        _, values, count = train_one(data, data['fold'] != fold, data['fold'] == fold, plan, max(plan['epochs']),
                                     WORK / f'fold-{fold}', deadline)
        all_values.append(values); updates += count
        print('Router fold', fold, values, flush=True)
    candidates = [dict(epoch=epoch, **{k: sum(v[epoch][k] for v in all_values) for k in all_values[0][epoch]})
                  for epoch in plan['epochs']]
    selected = select(candidates)
    bound = e.bind(p for p in WORK.glob('fold-*/*') if p.is_file())
    immutable_json(REPORT / 'selection.json', dict(plan_sha256=digest(REPORT / 'plan.json'),
        data_sha256=digest(REPORT / 'data.json'), candidates=candidates, selected=selected, bindings=bound,
        updates=updates, assessment_used=False))
    net, values, count = train_one(data, np.ones(len(data['x']), bool), np.ones(len(data['x']), bool),
                                  plan, selected['epoch'], WORK / 'refit', deadline)
    torch.save(dict(model=net.state_dict(), selected_epoch=selected['epoch'],
                    selection_sha256=digest(REPORT / 'selection.json')), WORK / 'selected.pt')
    elapsed = time.perf_counter() - start
    if elapsed >= plan['fitting_seconds_cap']: raise TimeoutError('Refit publication cap')
    immutable_json(REPORT / 'refit.json', dict(selection_sha256=digest(REPORT / 'selection.json'),
        bindings=e.bind([WORK / 'selected.pt', *(WORK / 'refit').glob('*')]), fit=values[selected['epoch']],
        refit_updates=count, total_updates=updates + count, seconds=elapsed, assessment_used=False))
    print('SELECTED', selected, 'total updates', updates + count, flush=True)


def assess():
    plan = inputs(); e.check(plan['assessment_inputs']); e.check(e.read(REPORT / 'refit.json')['bindings'])
    saved = torch.load(WORK / 'selected.pt', weights_only=False); state = saved['model']
    net = MovementRouter(state['mean'], state['scale']); net.load_state_dict(state); net.eval()
    records = e.read(ROOT / '.cambc/action-predictor/v74/forecasts.json')
    with np.load(e.TARGET) as z: current = z['x']
    data = make_data(records, 'validation', current); score = scores(net, data)
    np.savez_compressed(WORK / 'validation-router.npz', score=score, active=data['active'])
    filtered = [dict(r, eligible=r['eligible'] and bool(score[i] > 0 and data['active'][i])) for i, r in enumerate(records)]
    immutable_json(WORK / 'validation-forecasts.json', filtered)
    result, arrays = e.calculate(filtered); np.savez_compressed(WORK / 'validation-decisions.npz', **arrays)
    result['routing'] = summarize(data, score, np.ones(len(score), bool))
    result['coverage_note'] = 'Inherited eligible_queries now counts admitted disagreements, not original V74 interface coverage.'
    result['selected_epoch'] = saved['selected_epoch']; result['new_fits'] = 5
    result['optimizer_updates'] = e.read(REPORT / 'refit.json')['total_updates']
    immutable_json(REPORT / 'result.json', dict(result, refit_sha256=digest(REPORT / 'refit.json'),
        bindings=e.bind(WORK.glob('validation-*'))))
    print(json.dumps(dict(routing=result['routing'], baseline=result['baseline']['complete'],
                         hybrid=result['hybrid']['complete'], improved=result['improved']), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('freeze', 'prepare', 'fit', 'assess'))
    globals()[p.parse_args().command]()
