"""Two-engine current/history feature parity and missing-frame probe; no fit."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import numpy as np
from ..audit import cursor, immutable_json
from ..data import digest
from ..rich_data import read_turns
from ..observation_data import compact_supplement
from .audit import REPORT, BASE, eligible_jobs, ROOT_NAMES, label
from .feature_inputs import inputs


def game(job, record):
    payload = record['payload']; bindings = dict(record['bindings'])
    for path, expected in bindings.items():
        if digest(path) != expected: raise ValueError('Validated source changed')
    supplements = {}; route = None
    for kind in ('supplement', 'augmentation'):
        path = Path(job['work'])/kind/payload/'pre.jsonl'
        if not path.exists(): continue
        bindings[str(path)] = digest(path)
        for row in map(json.loads, path.open(encoding='utf-8')):
            if row['record'] == 'map':
                if route is not None and route != row['route']: raise ValueError('Public route disagreement')
                route = row['route']
            elif row['record'] == 'pre': supplements[row['id']] = compact_supplement(row)
    if route is None: raise ValueError('Public geometry unavailable')
    frames = {}; selected = {}
    for turn in read_turns(job['manifest'], job['record']):
        for d in turn['decisions']:
            event = d['event_cursor']; selected[event] = len(selected)
            frames[event] = dict(event=event, actor=turn['actor'], round=turn['round'], turn=turn['id'],
                pre=d['pre_cursor'], pre_header=d['audit']['pre_header'], observation=d['observation'],
                supplement=supplements[d['id']])
    with gzip.open(BASE.parent/'v7/games'/payload/'frames.jsonl.gz', 'rt', encoding='utf-8') as f:
        for frame in map(json.loads, f):
            if frame['event'] in frames:
                old = frames[frame['event']]
                if old['observation'] != frame['observation'] or old['supplement'] != frame['supplement']:
                    raise ValueError('Selected/cache source disagreement')
            frames[frame['event']] = frame
    proposal_path = REPORT/'window-proposals'/(payload+'.json')
    proposal = json.loads(proposal_path.read_text()); bindings[str(proposal_path)] = digest(proposal_path)
    keep = set(selected) | set(proposal['proposed_extra_events'])
    actors = defaultdict(list)
    path = Path(job['manifest']['source'])/'extracted'/payload/'index.jsonl'
    for turn in map(json.loads, path.open(encoding='utf-8')):
        if turn.get('record') != 'turn': continue
        for root in turn['roots']:
            step = root['header']['step']; name = ROOT_NAMES.get(step['kind'], '<unknown>')
            if name == 'cast': name = 'cast_'+str(step['abilitySlot'])
            actors[turn['actor']].append(dict(event=root['event'], round=turn['round'], turn=turn['id'],
                step=step, family=name, indexed_turn=turn, root=root))
    shard = Path(job['shard'])
    if digest(shard) != job['shard_sha256']: raise ValueError('Canonical feature shard changed')
    bindings[str(shard)] = digest(shard)
    with np.load(shard) as z: expected = {k: z[k] for k in ('x', 'history')}
    counts = Counter(); availability = Counter()
    for rows in actors.values():
        rows.sort(key=lambda r: cursor(r['event']))
        for ordinal, event in enumerate(rows):
            key = event['event']
            if key not in keep: continue
            frame = frames[key]
            label(event['indexed_turn'], event['root'], frame)
            value = inputs(frame, rows[:ordinal], frames, route, job['manifest']['labels'])
            if not np.isfinite(value['grid']).all(): raise ValueError('Nonfinite candidate features')
            if np.any(value['priority_inputs'][:4]): raise ValueError('Unexpected current-priority input')
            if key in selected:
                ix = selected[key]
                np.testing.assert_array_equal(value['x'], expected['x'][ix])
                np.testing.assert_array_equal(value['history'], expected['history'][ix, -16:])
                counts['selected_exact_current_and_history_parity'] += 1
            else:
                counts['extra_current_features_constructed'] += 1
                available = int(value['history_gaps'][:, 1].sum())
                availability[available] += 1
                counts['extra_missing_any_earlier_observation'] += available < 16
    return dict(payload=payload, engine=record['engine'], counts=dict(counts),
        extra_earlier_observation_availability=dict(availability), bindings=bindings,
        current_priority_policy='Current/scheduled PREpriority uniformly marked unavailable; only strictly earlier recorded integer arguments retained. Proposed treatment, requires review before fit.',
        geometry_scope='Candidate grid constructed from validated personal supplement and public route; finite checked. Exact canonical geometry parity remains required before optimizer updates.')


def run():
    jobs = {j['record']['raw_sha256']:j for j in eligible_jobs()}
    path = REPORT/'window-validation.json'; records = json.loads(path.read_text())['games']
    chosen = {}
    for record in records: chosen.setdefault(record['engine'], record)
    results = [game(jobs[r['payload']], r) for r in chosen.values()]
    immutable_json(REPORT/'feature-probe.json', dict(games=results, validation_sha256=digest(path),
        sources={str(p):digest(p) for p in (Path(__file__), Path(__file__).with_name('feature_inputs.py'), Path(__file__).with_name('audit.py'))},
        new_training_rows=0, new_fits=0, reserved_opened=0,
        limits='Two-engine probe only. Missing observations explicitly masked; no fabricated continuity or reused fitted components. Full corpus, supplemental provenance and candidate-geometry checks still needed.'))
    print('Bounded feature probe completed', flush=True)


if __name__ == '__main__': run()
