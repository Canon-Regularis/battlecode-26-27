"""Bounded identity-memory input parity from existing TRAIN personal caches."""
import gzip
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from .memory import PersonalEntityMemory
from ..entity_set import EntityBank
from ..rich_data import read_turns
from ..audit import cursor, immutable_json
from ..data import digest
from ..learned_policy.sequence_data import BASE, JOBS
from ..segment_policy.data import REPORT


def run():
    if digest(JOBS) != '80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba':
        raise RuntimeError('Eligible membership changed')
    chosen = {}
    for j in json.loads(JOBS.read_text()):
        if j['split'] == 'train': chosen.setdefault(j['record']['engine_version'], j)
    bank = EntityBank(BASE.parent/'v9/entities', 'train', 119)
    results = []
    for j in chosen.values():
        payload = j['record']['raw_sha256']
        history = BASE.parent/'v7/games'/payload
        framepath = history/'frames.jsonl.gz'
        receipt = json.loads((history/'receipt.json').read_text())
        if digest(framepath) != receipt['files']['frames.jsonl.gz']: raise RuntimeError('Existing frames changed')
        observations = {}
        with gzip.open(framepath, 'rt', encoding='utf-8') as f:
            for row in map(json.loads, f): observations[row['event']] = row
        selected = {}; local = 0
        for t in read_turns(j['manifest'], j['record']):
            for d in t['decisions']:
                event = d['event_cursor']; selected[event] = j['offset']+local
                observations[event] = dict(actor=t['actor'], pre=d['pre_cursor'], observation=d['observation'])
                local += 1
        index = Path(j['manifest']['source'])/'extracted'/payload/'index.jsonl'
        actual = defaultdict(list)
        for line in index.open():
            t = json.loads(line)
            if t.get('record') == 'turn':
                actual[t['actor']].extend(t['roots'])
        mismatches = []; counts = defaultdict(int); largest = 0
        for actor, roots in actual.items():
            roots.sort(key=lambda r: cursor(r['event']))
            memory = PersonalEntityMemory()
            first = True
            for ordinal, root in enumerate(roots):
                event = root['event']
                if event not in observations: continue
                frame = observations[event]
                if frame['actor'] != actor or frame['pre'] != root['pre']: raise RuntimeError('Personal PRE identity changed')
                if first: memory.reset(prefix_unavailable=ordinal > 0); first = False
                obs = frame['observation']
                memory.observe_pre(obs, ordinal)
                keys, tokens = memory.snapshot(obs['own'])
                largest = max(largest, len(keys)-2)
                counts['available_PREs'] += 1
                counts['currently_personal_tokens'] += int(tokens[2:, 122].sum())
                counts['stale_memory_tokens'] += int((tokens[2:, 122] == 0).sum())
                if event not in selected: continue
                own = obs['own']
                current = [own, *[e for e in obs['entities'] if e.get('known', 0)&1 and e['entity']['kind'] in (1, 2)]]
                cached, mask = bank.batch(np.array([selected[event]]))
                expected = cached[0, mask[0]].numpy()
                reconstructed = np.stack([tokens[keys.index(memory.key(e)), :119] for e in current])
                if not np.array_equal(expected, reconstructed):
                    mismatches.append(dict(row=int(selected[event]), shape_expected=list(expected.shape), shape_actual=list(reconstructed.shape)))
                counts['selected_rows_checked'] += 1
                counts['current_tokens_checked'] += len(current)
        results.append(dict(engine=j['record']['engine_version'], counts=dict(counts), maximum_remembered_entities=largest,
            mismatches=mismatches, bindings={str(p): digest(p) for p in (framepath, index, history/'receipt.json')}))
    immutable_json(REPORT/'TRAIN-grounding-memory-parity.json', dict(
        games=results, source_sha256=digest(__file__), memory_source_sha256=digest(__file__.replace('cache_parity.py', 'memory.py')),
        scope='First eligible TRAIN game per engine. Current known entity features reproduce the existing V9 cache exactly while identity memory adds explicit stale entries. This validates bounded input construction, not target selection, death availability in every engine/context, complete labels or model performance. Numeric keys never enter neural features.',
        new_fits=0, new_training_rows=0, reserved_opened=0, engine_queries=0))
    if any(g['mismatches'] for g in results): raise RuntimeError('Bounded memory parity failed; evidence preserved')


if __name__ == '__main__': run()
