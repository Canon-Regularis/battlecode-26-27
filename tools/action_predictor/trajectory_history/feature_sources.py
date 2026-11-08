"""Hash-bound personal sources for full feature assembly; no optimization."""
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


def load_game(job, record):
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
    by_event = {r['event']:r for rows in actors.values() for r in rows}
    for event, frame in frames.items():
        item = by_event[event]
        label(item['indexed_turn'], item['root'], frame)
    return dict(bindings=bindings, route=route, frames=frames, selected=selected,
                actors=actors, expected=expected, keep=keep)
