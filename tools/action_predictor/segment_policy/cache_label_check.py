"""Bounded raw-index versus frozen-label check before any data expansion.

This reads already recorded eligible TRAIN material. It neither creates new
training examples nor substitutes index metadata for fully validated labels.
"""
import json
from pathlib import Path
import numpy as np
from ..data import action_name, digest
from ..audit import immutable_json, cursor
from ..rich_data import read_turns, SPATIAL
from ..learned_policy.sequence_data import ROOT, JOBS, ROOT_NAMES
from .. import reliable_train as rt
from .data import REPORT


def run():
    if digest(JOBS) != '80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba':
        raise RuntimeError('Eligible jobs changed')
    chosen = {}
    for j in json.loads(JOBS.read_text()):
        if j['split'] == 'train': chosen.setdefault(j['record']['engine_version'], j)
    results = []
    for j in chosen.values():
        record = j['record']; payload = record['raw_sha256']
        directory = Path(j['manifest']['source'])/'extracted'/payload
        path = directory/'index.jsonl'
        if digest(path) != json.loads((directory/'receipt.json').read_text())['files']['index.jsonl']:
            raise RuntimeError('Historical index changed')
        roots = {}
        for line in path.open():
            turn = json.loads(line)
            if turn.get('record') != 'turn': continue
            for root in turn['roots']: roots[root['event']] = (turn, root)
        shard = Path(j['shard'])
        if digest(shard) != j['shard_sha256']: raise RuntimeError('Frozen shard changed')
        with np.load(shard) as z: raw = {k: z[k] for k in ('y', 'py', 'priority')}
        count = spatial = priorities = 0
        errors = []
        for turn in read_turns(j['manifest'], record):
            for d in turn['decisions']:
                historical, root = roots[d['event_cursor']]
                step = root['header']['step']
                family = ROOT_NAMES.get(step['kind'], '<unknown>')
                if family == 'cast': family = 'cast_'+str(step['abilitySlot'])
                expected = action_name(d['label'])
                failures = []
                if family != expected or rt.LABELS.index(family) != raw['y'][count]: failures.append('action_type')
                if historical['actor'] != turn['actor'] or root['pre'] != d['pre_cursor']: failures.append('actor_PRE')
                if cursor(root['pre']) >= cursor(root['event']): failures.append('event_order')
                if family in SPATIAL:
                    spatial += 1
                    destination = step.get('to'); own = d['observation']['own'].get('position')
                    py = 290
                    if own and destination:
                        x = destination['x']-own['x']; y = destination['y']-own['y']
                        py = (y+8)*17+x+8 if max(abs(x), abs(y)) <= 8 else 289
                    if destination != d['label'].get('to') or py != raw['py'][count]: failures.append('destination')
                if family == 'priority':
                    priorities += 1
                    if step.get('priority') != raw['priority'][count]: failures.append('priority')
                if failures: errors.append(dict(row=int(j['offset']+count), failures=failures, family=family))
                count += 1
        if count != j['rows']: raise RuntimeError('Canonical row alignment changed')
        results.append(dict(engine=record['engine_version'], rows=count, spatial=spatial, priorities=priorities,
            mismatches=errors, bindings={str(path): digest(path), str(shard): digest(shard)},
            interpretation='Bounded recorded-index/frozen-label consistency, not historical engine legality, ambiguous entity identity resolution or proof that every extra cached root supplies a complete training label.'))
    value = dict(games=results, source_sha256=digest(__file__), jobs_sha256=digest(JOBS),
        new_training_rows=0, new_fits=0, reserved_opened=0, engine_queries=0)
    immutable_json(REPORT/'TRAIN-cache-label-check.json', value)
    if any(g['mismatches'] for g in results): raise RuntimeError('Raw consistency differences preserved for diagnosis')


if __name__ == '__main__': run()
