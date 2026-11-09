"""Matched fitting-only selection of code-conditioned movement corrections."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import torch
from . import code_weight_fit as first, expanded_code_fit as expanded, expanded_code_data
from . import model, data as original
from .code_movement import MovementCorrection, CodeMovementPolicy, supported_log_probabilities
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT = original.ROOT
REPORT = ROOT/'tools/action_predictor/experiments/v51'
WORK = ROOT/'.cambc/action-predictor/v51'
ARMS = ('constant', 'predicted')


def read(path):
    return json.loads(path.read_text())


def bindings(paths):
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def check(value):
    for kind in ('sources', 'inputs', 'bindings'):
        for path, expected in value.get(kind, {}).items():
            if digest(ROOT/path) != expected:
                raise ValueError('Changed binding: '+path)


def freeze():
    REPORT.mkdir(parents=True, exist_ok=True)
    old, architecture, cache, ids = expanded.inputs()
    chosen = read(expanded.REPORT/'selection.json')['selected']
    for name in ('selection', 'refit', 'result'):
        check(read(expanded.REPORT/(name+'.json')))
    check(read(original.REPORT/'S01.json'))
    fold_paths = [expanded.WORK/'tuning'/f"lr{chosen['learning_rate']:g}-fold{k}"/f"epoch-{chosen['epoch']:03d}.pt" for k in range(4)]
    source_names = ('code_movement.py', 'code_movement_fit.py', 'code_movement_verify.py',
                    'code_movement_predictor.py', 'test_code_movement.py')
    inputs = [expanded.REPORT/n for n in ('plan.json', 'result.json', 'verification.json', 'selection.json', 'cache.json', 'data.json')]
    inputs += [expanded.WORK/'selected.pt', *fold_paths, original.REPORT/'S01.json']
    immutable_json(REPORT/'plan.json', dict(
        sources=bindings([Path(__file__).with_name(n) for n in source_names]), inputs=bindings(inputs),
        fold_backbones=[str(p.relative_to(ROOT)) for p in fold_paths],
        full_backbone=str((expanded.WORK/'selected.pt').relative_to(ROOT)),
        seed=51001, epochs=64, evaluate_every=8, batch_windows=32, learning_rate=.003,
        weight_decay=.01, clip=5., tuning_seconds_cap=1200, refit_seconds_cap=600,
        trainable_parameters=3528, arms=list(ARMS),
        design='Freeze V49 context, recurrent code predictor, old movement and goal heads. '
        'Add eight linear 48-to-9 movement residual experts, zero initialized. Treatment weights '
        'experts by predicted soft code probabilities; control uses fitting-training mean probabilities. '
        'Both retain the same V49 baseline logits, which already depend on the predicted code. '
        'This tests extra code-dependent execution, not removal of all code information.',
        data='All1607 existing fitting windows from32games; four whole-game folds. Fold backbone '
        'is matching V49 checkpoint. Held fold validates only its original64windows. No hindsight '
        'code labels, movement labels, future descriptors, identity or direction diagnostics enter inputs.',
        loss='Supported movement cross entropy, divided by actual movement rows in each32-window batch. '
        'No movement rows means skip update. Same permutations/updates across arms. No recurrent updates.',
        selection='One shared epoch for both arms selected by maximum sum of held-fitting correct moves, '
        'then minimum summed NLL, then earlier epoch; epochs0,8,...64 eligible. '
        'Refit both on all fitting windows from the full V49 backbone; evaluate selected pair once.',
        success='Usable movement improvement: predicted arm gains at least3percentage points vsV49, '
        'accuracy at least originalS01, and NLL at most0.01 worse than either. '
        'Additional code benefit: at least1percentage point above constant control and strictly lower NLL. '
        'Report all group/direction/code strata, paired rescues/regressions, and code/goal parity. '
        'These are allocation thresholds, not statistical significance or promotion.',
        limitations='Previously exposed research groups, original backbone/discovery fitting-group exposure, '
        'teacher-forced history, inferred labels, conditional movement only. No strategy or playing-strength '
        'claim. No subagents or playing-bot changes. Original checkpoints preserved.'))


def inputs():
    plan = read(REPORT/'plan.json'); check(plan)
    _, architecture, cache, ids = expanded.inputs()
    return plan, architecture, cache, ids


def backbone(path, architecture):
    net = model.SegmentPolicy(architecture['schema'], 8).eval()
    net.load_state_dict(torch.load(path, map_location='cpu', weights_only=False)['model'])
    return net.requires_grad_(False)


@torch.no_grad()
def frozen_features(net, cache):
    values = []
    captured = []
    handle = net.code.register_forward_pre_hook(lambda module, args: captured.append(args[0]))
    try:
        for start in range(0, len(cache['observed']), 16):
            item = first.take(cache, slice(start, start+16))
            logits = first.code_forward(net, item)
            states = captured.pop(); probabilities = logits.softmax(-1)
            baseline = net.movement(torch.cat((states, probabilities @ net.embeddings), -1))
            values.append(dict(states=states.clone(), probabilities=probabilities, baseline=baseline))
    finally:
        handle.remove()
    return {k: torch.cat([v[k] for v in values]) for k in values[0]}


def prepare():
    plan, architecture, cache, ids = inputs(); WORK.mkdir(parents=True, exist_ok=False)
    windows, maps = expanded_code_data.read()
    assert len(windows) == len(ids) == 1607
    assert all(w['partition'] == 'fit' and w['key'] == ids[i]['key'] for i, w in enumerate(windows))
    support, labels = zip(*(model.move_support(w) for w in windows))
    target = dict(support=torch.stack(support), labels=torch.stack(labels))
    torch.save(target, WORK/'targets.pt')
    torch.set_num_threads(1); parity = []
    for name, path in [*(('fold'+str(k), ROOT/p) for k, p in enumerate(plan['fold_backbones'])), ('full', ROOT/plan['full_backbone'])]:
        net = backbone(path, architecture); features = frozen_features(net, cache)
        assert all(torch.isfinite(v).all() for v in features.values())
        # A full-map forward in each fitting group checks cached recurrent inputs.
        selected = {}; maximum = 0.
        for i, w in enumerate(windows):
            selected.setdefault(w['group'], i)
        for i in selected.values():
            w = windows[i]; args, _ = model.encode_window(w, maps[w['payload']], architecture['schema'])
            with torch.no_grad(): output = net(**args)
            for actual, expected in [(features['baseline'][i], output['move']),
                                     (features['probabilities'][i], output['code'].softmax(-1))]:
                torch.testing.assert_close(actual, expected, atol=2e-6, rtol=2e-5)
                maximum = max(maximum, float((actual-expected).abs().max()))
        torch.save(features, WORK/(name+'-features.pt'))
        parity.append(dict(backbone=name, full_map_windows=len(selected), maximum_error=maximum))
        print('Cached', name, len(windows), 'fitting windows', flush=True)
    immutable_json(REPORT/'cache.json', dict(plan_sha256=digest(REPORT/'plan.json'),
        bindings=bindings([WORK/'targets.pt', *(WORK/(n+'-features.pt') for n in ['full', 'fold0', 'fold1', 'fold2', 'fold3'])]),
        windows=len(windows), movement_rows=int((target['labels']>=0).sum()), parity=parity))


def cached(name):
    receipt = read(REPORT/'cache.json'); check(receipt)
    assert receipt['plan_sha256'] == digest(REPORT/'plan.json')
    return dict(**torch.load(WORK/(name+'-features.pt'), weights_only=True),
                **torch.load(WORK/'targets.pt', weights_only=True))


def head(data, indices, arm):
    mask = data['labels'][indices] >= 0
    mean = data['probabilities'][indices][mask].mean(0)
    if not torch.isfinite(mean).all(): raise ValueError('No fitting movement rows')
    return MovementCorrection(mean, arm == 'predicted')


def forward(net, item):
    return net(item['states'], item['probabilities'], item['baseline'])


@torch.no_grad()
def score(net, data, indices):
    labels, predictions, losses = [], [], []
    for start in range(0, len(indices), 32):
        item = first.take(data, indices[start:start+32]); mask = item['labels'] >= 0
        lp = supported_log_probabilities(forward(net, item), item['support'])[mask]
        y = item['labels'][mask]
        labels.extend(y.tolist()); predictions.extend(lp.argmax(-1).tolist())
        losses.extend((-lp.gather(1, y[:, None]).squeeze(1)).double().tolist())
    return dict(rows=len(labels), correct=sum(a==b for a,b in zip(labels, predictions)),
                nll=sum(losses)/len(labels), labels=labels, predictions=predictions)


def train(net, data, indices, plan, directory, epochs, deadline, validation=None):
    directory.mkdir(parents=True, exist_ok=False)
    optimizer = torch.optim.AdamW(net.parameters(), lr=plan['learning_rate'], weight_decay=plan['weight_decay'])
    rng = np.random.default_rng(plan['seed']); trace = []; updates = 0
    initial = score(net, data, validation) if validation is not None else None
    torch.save(dict(model=net.state_dict(), optimizer=optimizer.state_dict()), directory/'epoch-000.pt')
    for epoch in range(1, epochs+1):
        order = rng.permutation(indices); counts = []; norms = []; total = 0.; rows = 0
        for start in range(0, len(order), plan['batch_windows']):
            if time.perf_counter() >= deadline: raise TimeoutError('Movement fitting budget exceeded')
            item = first.take(data, order[start:start+plan['batch_windows']]); mask = item['labels'] >= 0
            count = int(mask.sum()); counts.append(count)
            if not count: continue
            optimizer.zero_grad(set_to_none=True)
            lp = supported_log_probabilities(forward(net, item), item['support'])[mask]
            objective = -lp.gather(1, item['labels'][mask][:, None]).mean()
            objective.backward(); norm = torch.nn.utils.clip_grad_norm_(net.parameters(), plan['clip'])
            if not torch.isfinite(objective) or not torch.isfinite(norm): raise ValueError('Nonfinite movement fit')
            optimizer.step(); updates += 1; norms.append(float(norm)); total += float(objective.detach())*count; rows += count
        entry = dict(epoch=epoch, updates=updates, order=order.tolist(), denominators=counts,
                     gradient_norms=norms, presentations=rows, online_nll=total/rows)
        if epoch % plan['evaluate_every'] == 0 or epoch == epochs:
            if validation is not None: entry['validation'] = score(net, data, validation)
            torch.save(dict(model=net.state_dict(), optimizer=optimizer.state_dict(), epoch=epoch, updates=updates,
                            rng=rng.bit_generator.state), directory/f'epoch-{epoch:03d}.pt')
            print(directory.name, 'epoch', epoch, 'NLL', round(total/rows, 5),
                  'held correct', entry.get('validation', {}).get('correct'), flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json', dict(initial=initial, epochs=trace))
    return trace


def combine(values):
    n = sum(v['rows'] for v in values)
    return dict(rows=n, correct=sum(v['correct'] for v in values), nll=sum(v['nll']*v['rows'] for v in values)/n)


def choose(candidates):
    return min(candidates, key=lambda c: (-sum(v['correct'] for v in c['arms'].values()),
                                         sum(v['nll'] for v in c['arms'].values()), c['epoch']))


def tune():
    start = time.perf_counter(); plan, architecture, _, ids = inputs(); torch.set_num_threads(1)
    directory = WORK/'tuning'; directory.mkdir(exist_ok=False); values = {}
    for fold in range(4):
        data = cached('fold'+str(fold)); training, held = expanded.partition_indices(ids, fold)
        for arm in ARMS:
            net = head(data, training, arm); values[(arm, fold, 0)] = score(net, data, held)
            trace = train(net, data, training, plan, directory/f'{arm}-fold{fold}', plan['epochs'],
                          start+plan['tuning_seconds_cap'], held)
            for entry in trace:
                if 'validation' in entry: values[(arm, fold, entry['epoch'])] = entry['validation']
    candidates = [dict(epoch=e, arms={a:combine([values[(a,k,e)] for k in range(4)]) for a in ARMS})
                  for e in range(0, plan['epochs']+1, plan['evaluate_every'])]
    chosen = choose(candidates); elapsed = time.perf_counter()-start
    if elapsed >= plan['tuning_seconds_cap']: raise TimeoutError('Movement tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json', dict(plan_sha256=digest(REPORT/'plan.json'), selected=chosen,
        candidates=candidates, seconds=elapsed, outer_evaluation_used=False,
        bindings=bindings([p for p in directory.rglob('*') if p.is_file()])))
    print('SELECTED', json.dumps(chosen), flush=True)


def refit():
    start = time.perf_counter(); plan, architecture, _, ids = inputs(); selection = read(REPORT/'selection.json'); check(selection)
    assert selection['selected'] == choose(selection['candidates'])
    data = cached('full'); indices = np.arange(len(ids)); torch.set_num_threads(1); result = {}
    for arm in ARMS:
        net = head(data, indices, arm)
        trace = train(net, data, indices, plan, WORK/('refit-'+arm), selection['selected']['epoch'],
                      start+plan['refit_seconds_cap'])
        torch.save(dict(correction=net.state_dict(), conditioned=arm=='predicted',
            backbone_sha256=digest(ROOT/plan['full_backbone']), plan_sha256=digest(REPORT/'plan.json'),
            selection_sha256=digest(REPORT/'selection.json'), inference_only=True), WORK/(arm+'.pt'))
        result[arm] = dict(fit=score(net,data,indices), updates=trace[-1]['updates'] if trace else 0)
    paths = [WORK/(a+'.pt') for a in ARMS] + [p for a in ARMS for p in (WORK/('refit-'+a)).iterdir() if p.is_file()]
    elapsed = time.perf_counter()-start
    if elapsed >= plan['refit_seconds_cap']: raise TimeoutError('Movement refit publication budget exceeded')
    immutable_json(REPORT/'refit.json', dict(selection_sha256=digest(REPORT/'selection.json'), arms=result,
        seconds=elapsed, bindings=bindings(paths)))


def policy(arm, plan, architecture):
    saved = torch.load(WORK/(arm+'.pt'), map_location='cpu', weights_only=False)
    assert saved['plan_sha256'] == digest(REPORT/'plan.json')
    assert saved['selection_sha256'] == digest(REPORT/'selection.json')
    assert saved['backbone_sha256'] == digest(ROOT/plan['full_backbone'])
    assert saved['conditioned'] == (arm=='predicted') and saved['inference_only']
    correction = MovementCorrection(saved['correction']['mean_probabilities'], saved['conditioned'])
    correction.load_state_dict(saved['correction'])
    return CodeMovementPolicy(backbone(ROOT/plan['full_backbone'], architecture), correction).eval()


def paired(actual, reference):
    assert [(r['key'],r['event'],r['move_label']) for r in actual] == [(r['key'],r['event'],r['move_label']) for r in reference]
    rows = [(a,b) for a,b in zip(actual,reference) if a['move_label'] is not None]
    return dict(rows=len(rows), rescues=sum(a['move_prediction']==a['move_label'] and b['move_prediction']!=b['move_label'] for a,b in rows),
        regressions=sum(a['move_prediction']!=a['move_label'] and b['move_prediction']==b['move_label'] for a,b in rows))


def gates(predicted, constant, baseline, original_summary):
    p, c, b, o = predicted, constant, baseline, original_summary
    usable = dict(gain_vs_v49=p['movement_accuracy']>=b['movement_accuracy']+.03,
        accuracy_vs_s01=p['movement_accuracy']>=o['movement_accuracy'],
        nll_vs_v49=p['movement_nll']<=b['movement_nll']+.01,
        nll_vs_s01=p['movement_nll']<=o['movement_nll']+.01)
    code = dict(gain_vs_control=p['movement_accuracy']>=c['movement_accuracy']+.01,
                nll_vs_control=p['movement_nll']<c['movement_nll'])
    return dict(movement_checks=usable, additional_code_checks=code,
                movement_improved=all(usable.values()), additional_code_benefit=all(code.values()))


def assess():
    start=time.perf_counter(); plan,architecture,_,ids=inputs(); check(read(REPORT/'refit.json'))
    torch.set_num_threads(4); windows,maps=original.load(); discovery=read(original.REPORT/'discovery.json')
    cache={w['key']:model.encode_window(w,maps[w['payload']],architecture['schema'])[0] for w in windows}
    results={}; predictions={}
    for arm in ARMS:
        net=policy(arm,plan,architecture); results[arm]={}
        for split in ('fit','evaluation'):
            value=evaluate(net,windows,maps,cache,discovery,split,start+600)
            old=read(expanded.WORK/(split+'-predictions.json'))
            for a,b in zip(value['records'],old['records']):
                assert {k:v for k,v in a.items() if k not in ('move_prediction','movement_nll')} == {k:v for k,v in b.items() if k not in ('move_prediction','movement_nll')}
            immutable_json(WORK/f'{arm}-{split}-predictions.json',value)
            results[arm][split]=value['summary']; predictions[(arm,split)]=value
            print(arm,split,json.dumps(value['summary']),flush=True)
    baseline=read(expanded.WORK/'evaluation-predictions.json'); s01=read(original.WORK/'S01-run/evaluation-predictions.json')
    p=predictions[('predicted','evaluation')]; c=predictions[('constant','evaluation')]
    comparisons=dict(v49=paired(p['records'],baseline['records']), constant=paired(p['records'],c['records']), s01=paired(p['records'],s01['records']))
    checks=gates(p['summary'],c['summary'],baseline['summary'],s01['summary'])
    paths=[WORK/(a+'.pt') for a in ARMS]+[WORK/f'{a}-{s}-predictions.json' for a in ARMS for s in ('fit','evaluation')]
    elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Movement assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,
        comparisons=comparisons,**checks,bindings=bindings(paths),seconds=elapsed,promoted=False,
        qualification='Conditional first-move prediction on previously exposed research games, not full-command accuracy or strategy.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','prepare','tune','refit','assess'))
    globals()[parser.parse_args().command]()
