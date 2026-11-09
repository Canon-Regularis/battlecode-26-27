"""No-fit V59/JP02 integration on every original DEV decision.

Forecasts are archived before scoring. This is a decision-level dispatch, not a
new calibrated joint distribution: no hybrid NLL is claimed. Current labels are
used only after a prediction, for history assimilation and subsequent scoring.
"""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import time

import numpy as np
import torch

from .data import ADMIN, FEATURES, descriptor
from .full_action_movement import TurnMovementAdapter, dispatch
from .trajectory_movement_predictor import TrajectoryMovementPredictor
from ..audit import cursor, immutable_json
from ..data import digest
from ..observation_data import compact_supplement, safe_observation
from ..observation_metrics import correctness
from ..priority_regularized.safety import dependency_files
from ..reliable_train import LABELS
from ..rich_data import read_turns
from ..trajectory_history.audit import label, ROOT_NAMES

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'tools/action_predictor/experiments/v74'
WORK = ROOT / '.cambc/action-predictor/v74'
JOBS = ROOT / '.cambc/action-predictor/v7/jobs.json'
BASELINE = ROOT / '.cambc/action-predictor/v27/JP02-validation-predictions.npz'
TARGET = ROOT / '.cambc/action-predictor/v4/validation.npz'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def bind(paths):
    return {str(Path(p).resolve()): digest(p) for p in paths}


def check(bindings):
    for path, expected in bindings.items():
        if digest(path) != expected:
            raise ValueError('Bound file changed: ' + path)


def game_paths(job):
    payload = job['record']['raw_sha256']
    source = Path(job['manifest']['source']) / 'extracted' / payload
    supplement = Path(job['work']) / 'supplement' / payload
    cache = ROOT / '.cambc/action-predictor/v7/games' / payload
    return source, supplement, cache


def freeze():
    if REPORT.exists():
        raise FileExistsError('Preserve existing V74 plan')
    jobs = [j for j in read(JOBS) if j['split'] == 'validation']
    if len(jobs) != 25 or sum(j['rows'] for j in jobs) != 14439:
        raise ValueError('Original DEV membership changed')
    grouping = read(ROOT / 'tools/action_predictor/experiments/v42/r2/evaluator-plan.json')
    movement_groups = {j['group'] for j in grouping['jobs']}
    dev_groups = {j['record']['group'] for j in jobs}
    if movement_groups & dev_groups:
        raise ValueError('V59 movement research games overlap original DEV')
    jp = read(ROOT / 'tools/action_predictor/experiments/v27/JP-results.json')
    if digest(BASELINE) != next(h for p, h in jp['bindings'].items()
                               if p.replace('\\', '/').endswith('v27/JP02-validation-predictions.npz')):
        raise ValueError('Retained baseline changed')
    if digest(TARGET) != '01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed':
        raise ValueError('Canonical DEV changed')
    files = [JOBS, BASELINE, TARGET,
             ROOT / 'tools/action_predictor/experiments/v27/JP-results.json',
             ROOT / 'tools/action_predictor/experiments/v59/result.json',
             ROOT / 'tools/action_predictor/experiments/v59/verification.json',
             ROOT / '.cambc/action-predictor/v59/selected.pt',
             ROOT / 'tools/action_predictor/experiments/v42/r2/evaluator-plan.json',
             ROOT / '.cambc/action-predictor/v7/validation-direction.npy']
    for j in jobs:
        source, supplement, cache = game_paths(j)
        ir, sr, cr = (read(p / 'receipt.json') for p in (source, supplement, cache))
        expected = {source / 'index.jsonl': ir['files']['index.jsonl'],
                    source / 'turns.jsonl': j['record']['turns_sha256'],
                    supplement / 'pre.jsonl': sr['sha256'],
                    cache / 'frames.jsonl.gz': cr['files']['frames.jsonl.gz'],
                    Path(j['shard']): j['shard_sha256']}
        check(expected)
        files.extend(expected)
        files.extend(p / 'receipt.json' for p in (source, supplement, cache))
    sources = dependency_files(ROOT, ('tools.action_predictor.behavior_segments.full_action_evaluate',
                                     'tools.action_predictor.behavior_segments.test_full_action_movement'))
    REPORT.mkdir(parents=True)
    immutable_json(REPORT / 'plan.json', dict(
        sources=bind(sources), inputs=bind(files), jobs=jobs, rows=14439, games=25,
        groups=sorted(dev_groups), movement_research_group_overlap=[],
        intervention='Frozen JP02 action type and every nonmovement argument. V59 replaces only the destination '
                     'of predicted moves before any earlier nonadministrative command in the current own turn. '
                     'Eligibility uses past actual commands only, never the current family or destination.',
        history='Full chronological own turns from the cached actor index. One recurrent step per own turn at '
                'the first nonadministrative PRE, unavailable PREs are masked, administrative-only turns use '
                'a masked step. Every query before that anchor uses the same incoming prior-turn state. '
                'Previous descriptors end at that query PRE, and move vectors come only from the completed '
                'previous own turn. Actor-specific state, resets at 32 own turns from actor stream start.',
        fallback='Original JP02 destination on later within-turn queries and when V59 has no located output. '
                 'All 14439 rows remain in every overall denominator. No dropping unsupported moves.',
        selection='One predeclared frozen dispatch; no fitted weights, temperatures, thresholds or evaluation-based routing.',
        success='Strict complete-command count must exceed JP02, with exact unchanged nonmovement command outcomes. '
                'Report all categories, movement false positives, continuation/change, coverage, paired groups '
                'and 2000 group bootstrap draws. This is exploratory and never automatic promotion.',
        probability='Decision-only destination override after JP02 joint-MAP action selection. It is not joint MAP '
                    'under a new combined distribution. Do not attach the old NLL to the hybrid or claim calibration.',
        limits='Previously exposed five DEV groups, observed past commands, new adapter history clock and selective '
               'frame availability, first-query movement training, missing shop arguments and ambiguous targets. '
               'Group exclusion of V59 updates does not make these untouched evaluation data.',
        seconds_cap=1800, new_fits=0, optimizer_updates=0, reserved_opened=0, subagents=False))


def load_game(job):
    source, supplement, cache = game_paths(job)
    supplements = {}; route = None
    for row in map(json.loads, (supplement / 'pre.jsonl').open(encoding='utf-8')):
        if row['record'] == 'map': route = row['route']
        elif row['record'] == 'pre': supplements[row['id']] = compact_supplement(row)
    if route is None: raise ValueError('Missing public map')
    selected = {}; frames = {}; identities = {}
    for t in read_turns(job['manifest'], job['record']):
        for d in t['decisions']:
            event = d['event_cursor']
            if event in selected: raise ValueError('Duplicate selected event')
            selected[event] = job['offset'] + len(selected)
            identities[event] = (t, d)
            frames[event] = dict(event=event, actor=t['actor'], round=t['round'], turn=t['id'],
                                 pre=d['pre_cursor'], pre_header=d['audit']['pre_header'],
                                 observation=d['observation'], supplement=supplements[d['id']])
    if len(selected) != job['rows']: raise ValueError('Row mapping changed')
    with gzip.open(cache / 'frames.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for f in map(json.loads, stream):
            if f['event'] in frames:
                old = frames[f['event']]
                if old['observation'] != f['observation'] or old['supplement'] != f['supplement']:
                    raise ValueError('Selected/cache frame mismatch')
            frames[f['event']] = f
    actors = defaultdict(list); indexed = {}
    own_actors = {t['actor'] for t, _ in identities.values()}
    for t in map(json.loads, (source / 'index.jsonl').open(encoding='utf-8')):
        if t.get('record') != 'turn' or t['actor'] not in own_actors or not t['roots']: continue
        rows = []
        for root in t['roots']:
            step = root['header']['step']; family = ROOT_NAMES.get(step['kind'], '<unknown>')
            if family == 'cast': family += '_' + str(step['abilitySlot'])
            r = dict(event=root['event'], family=family, step=step, root=root, turn=t)
            if root['event'] in indexed: raise ValueError('Duplicate indexed event')
            indexed[root['event']] = r; rows.append(r)
        actors[t['actor']].append(rows)
    for event, f in frames.items():
        if event not in indexed: continue
        r = indexed[event]; label(r['turn'], r['root'], f)
        safe_observation(f['observation'], f['actor'], f['observation']['own']['team'], f['supplement'])
    if not set(selected).issubset(indexed): raise ValueError('Missing selected roots')
    for rows in actors.values(): rows.sort(key=lambda rs: cursor(rs[0]['event']))
    return route, selected, frames, actors


def prior_inputs(roots, prior_frame, current_frame, route):
    if roots is None: return [0.] * len(FEATURES), [0.] * len(FEATURES), []
    if current_frame and cursor(roots[-1]['event']) >= cursor(current_frame['pre']):
        raise ValueError('Previous command reaches current PRE')
    values, mask = descriptor(roots, prior_frame, current_frame, route)
    moves = [(r['step']['to']['x'] - r['step']['from']['x'],
              r['step']['to']['y'] - r['step']['from']['y']) for r in roots if r['family'] == 'move']
    return values, mask, moves


def forecast_game(job, predictor):
    route, selected, frames, actors = load_game(job)
    records = []; counts = defaultdict(int)
    for actor, turns in sorted(actors.items()):
        adapter = TurnMovementAdapter(predictor); prev_roots = None; prev_frame = None
        last_selected = max(cursor(e) for e in selected if frames[e]['actor'] == actor)
        for roots in turns:
            if cursor(roots[0]['event']) > last_selected: break
            adapter.begin_turn(); anchor_frame = None
            for r in roots:
                event = r['event']; is_selected = event in selected
                # For unselected commands, only the next turn's state is needed.
                # The current family is never consulted to gate a selected query.
                query = is_selected or (not adapter.seen_nonadmin and r['family'] not in ADMIN)
                if not query: continue
                f = frames.get(event); current = None if f is None else {
                    'observation': f['observation'], 'supplement': f['supplement']}
                previous, mask, moves = prior_inputs(prev_roots, prev_frame, f, route)
                value = adapter.predict(current, route, r['turn']['round'], previous, mask, moves)
                if is_selected:
                    records.append(dict(row=selected[event], payload=job['record']['raw_sha256'],
                        actor=actor, event=event, round=r['turn']['round'],
                        eligible=value['eligible'], movement=value['movement'],
                        history_turns=0 if adapter.state is None else adapter.state['turns'],
                        probabilities=None if value['forecast'] is None else value['forecast']['movement_probabilities']))
                # Assimilation happens only after this root's prediction is saved.
                if not adapter.seen_nonadmin and r['family'] not in ADMIN:
                    anchor_frame = f; counts['observed_anchors' if f else 'missing_anchors'] += 1
                adapter.observe(r['family'])
            previous, mask, moves = prior_inputs(prev_roots, prev_frame, None, route)
            counts['admin_only_turns'] += int(not adapter.seen_nonadmin)
            adapter.finish_turn(route, roots[0]['turn']['round'], previous, mask, moves)
            prev_roots, prev_frame = roots, anchor_frame
            counts['actor_turns'] += 1
    if sorted(r['row'] for r in records) != list(range(job['offset'], job['offset'] + job['rows'])):
        raise ValueError('Forecast row coverage differs')
    return dict(records=sorted(records, key=lambda r: r['row']), counts=dict(counts))


def forecast():
    start = time.perf_counter(); plan = read(REPORT / 'plan.json')
    check(plan['sources']); check(plan['inputs']); WORK.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1); predictor = TrajectoryMovementPredictor(); records = []; games = []
    for i, j in enumerate(plan['jobs'], 1):
        if time.perf_counter() - start >= plan['seconds_cap']: raise TimeoutError('Frozen forecast cap')
        value = forecast_game(j, predictor)
        path = WORK / (j['record']['raw_sha256'] + '.json'); immutable_json(path, value)
        records.extend(value['records']); games.append(dict(payload=j['record']['raw_sha256'], **value['counts']))
        print('Full-action forecast', i, '/25', len(value['records']), value['counts'], flush=True)
    records.sort(key=lambda r: r['row'])
    if [r['row'] for r in records] != list(range(plan['rows'])): raise ValueError('Incomplete full DEV')
    immutable_json(WORK / 'forecasts.json', records)
    elapsed = time.perf_counter() - start
    if elapsed >= plan['seconds_cap']: raise TimeoutError('Forecast publication cap')
    immutable_json(REPORT / 'forecast.json', dict(plan_sha256=digest(REPORT / 'plan.json'),
        bindings=bind(WORK.glob('*.json')), games=games, seconds=elapsed, new_fits=0))


def metrics(raw, prediction, coordinate, priority, selected=None):
    selected = np.ones(len(raw['y']), bool) if selected is None else selected
    parameter, joint = correctness(raw, dict(prediction=prediction, coordinate=coordinate, priority=priority))
    n = int(selected.sum()); matrix = np.bincount(raw['y'][selected] * 15 + prediction[selected], minlength=225).reshape(15, 15)
    f1 = 2 * matrix.diagonal() / np.maximum(matrix.sum(0) + matrix.sum(1), 1)
    return dict(rows=n, complete=int(joint[selected].sum()), accuracy=float(joint[selected].mean()) if n else None,
        macro_f1=float(f1[1:].mean()), categories={name: dict(
            rows=int((selected & (raw['y'] == k)).sum()),
            complete=int((joint & selected & (raw['y'] == k)).sum()),
            conditional_correct=int((parameter & selected & (raw['y'] == k)).sum()) if k != 11 else None)
            for k, name in enumerate(LABELS)}, movement_type_false_positives=int((selected & (prediction == 8) & (raw['y'] != 8)).sum())), joint


def calculate(records):
    with np.load(TARGET) as z: raw = {k: z[k] for k in ('y', 'py', 'priority', 'group')}
    with np.load(BASELINE) as z: old = {k: z[k] for k in z.files}
    if [r['row'] for r in records] != list(range(len(raw['y']))): raise ValueError('Row ordering mismatch')
    eligible = np.array([r['eligible'] for r in records]); available = np.array([r['movement'] is not None for r in records])
    proposed = np.array([dispatch(int(old['prediction'][i]), int(old['proposed_coordinate'][i]),
                                 r['movement'], r['eligible']) for i, r in enumerate(records)])
    conditional = old['coordinate'].copy()
    # Labels enter reporting here, after every forecast has been archived.
    for i in np.flatnonzero((raw['y'] == 8) & eligible & available):
        conditional[i] = dispatch(8, int(conditional[i]), records[i]['movement'], True)
    base, a = metrics(raw, old['prediction'], old['coordinate'], old['priority'])
    hybrid, b = metrics(raw, old['prediction'], conditional, old['priority'])
    strict_proposed = (old['prediction'] == raw['y']) & (raw['y'] != 11)
    spatial = raw['py'] >= 0
    strict_proposed[spatial] &= (proposed[spatial] == raw['py'][spatial]) & (raw['py'][spatial] < 289)
    strict_proposed[raw['y'] == 9] &= old['priority'][raw['y'] == 9] == raw['priority'][raw['y'] == 9]
    if not np.array_equal(b, strict_proposed): raise ValueError('Decision/conditional score disagreement')
    if int(a.sum()) != 12137 or base['categories']['move']['complete'] != 1364: raise ValueError('JP02 reproduction failed')
    if not np.array_equal(a[raw['y'] != 8], b[raw['y'] != 8]): raise ValueError('Nonmovement outcome changed')
    if not np.array_equal(proposed[old['prediction'] != 8], old['proposed_coordinate'][old['prediction'] != 8]):
        raise ValueError('Nonmovement argument changed')
    groups = np.unique(raw['group']); per_group = []
    for g in groups:
        m = raw['group'] == g
        per_group.append(dict(group=int(g), rows=int(m.sum()), baseline=int(a[m].sum()), hybrid=int(b[m].sum()),
                              rescues=int((m & b & ~a).sum()), regressions=int((m & a & ~b).sum())))
    rng = np.random.default_rng(74001); draws = rng.integers(0, len(groups), size=(2000, len(groups)))
    ns = np.array([v['rows'] for v in per_group]); ds = np.array([v['hybrid'] - v['baseline'] for v in per_group])
    intervals = ds[draws].sum(1) / ns[draws].sum(1)
    direction = np.load(ROOT / '.cambc/action-predictor/v7/validation-direction.npy')
    cohorts = {}
    for name, mask in dict(eligible=eligible & available, fallback=~(eligible & available),
                           changes=(raw['y'] == 8) & (direction == 3),
                           continuations=(raw['y'] == 8) & (direction == 2)).items():
        cohorts[name] = dict(baseline=metrics(raw, old['prediction'], old['coordinate'], old['priority'], mask)[0],
                             hybrid=metrics(raw, old['prediction'], conditional, old['priority'], mask)[0])
    result = dict(baseline=base, hybrid=hybrid, rescues=int((b & ~a).sum()), regressions=int((a & ~b).sum()),
        eligible_queries=int(eligible.sum()), located_eligible_queries=int((eligible & available).sum()),
        routed_predicted_moves=int(((old['prediction'] == 8) & eligible & available).sum()),
        changed_commands=int((proposed != old['proposed_coordinate']).sum()), groups=per_group, cohorts=cohorts,
        paired95_accuracy_difference=np.quantile(intervals, [.025, .975]).tolist(),
        improved=int(b.sum()) > int(a.sum()), nonmovement_outcomes_unchanged=True,
        probability_metrics=None, promoted=False, new_fits=0, optimizer_updates=0, reserved_opened=0)
    arrays = dict(prediction=old['prediction'], proposed_coordinate=proposed, coordinate=conditional,
                  priority=old['priority'], eligible=eligible, available=available, baseline_correct=a, hybrid_correct=b)
    return result, arrays


def assess():
    plan = read(REPORT / 'plan.json'); check(plan['sources']); check(plan['inputs'])
    forecasts = read(REPORT / 'forecast.json'); check(forecasts['bindings'])
    if forecasts['plan_sha256'] != digest(REPORT / 'plan.json'): raise ValueError('Plan mismatch')
    result, arrays = calculate(read(WORK / 'forecasts.json'))
    path = WORK / 'hybrid.npz'
    if path.exists(): raise FileExistsError('Preserve scored predictions')
    np.savez_compressed(path, **arrays)
    immutable_json(REPORT / 'result.json', dict(result, plan_sha256=digest(REPORT / 'plan.json'),
        forecast_sha256=digest(REPORT / 'forecast.json'), bindings=bind([path])))
    print(json.dumps({k: result[k] for k in ('baseline', 'hybrid', 'rescues', 'regressions', 'improved')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('freeze', 'forecast', 'assess'))
    globals()[p.parse_args().command]()
