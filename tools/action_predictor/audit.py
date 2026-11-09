"""Audit original replay bytes, strict PRE ordering, and immutable experiment locks."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from .data import FISH_ID, action_name, digest, features


def immutable_json(path, value):
    text = json.dumps(value, indent=2) + '\n'
    path = Path(path)
    if path.exists() and path.read_text() != text:
        raise ValueError(f'Refusing to replace frozen artifact: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def cursor(value):
    parts = value.split(':')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError('Invalid cursor')
    return tuple(map(int, parts))


def validate_decision(decision, turn):
    p, q = decision['audit']['pre_header'], decision['audit']['header']
    before, after = cursor(decision['pre_cursor']), cursor(decision['event_cursor'])
    label, obs = decision['label'], decision['observation']
    if (before >= after or after != (before[0]+1, 0)
            or before != (p['inputPosition'], p['step']['substep'])
            or after != (q['inputPosition'], q['step']['substep'])):
        raise ValueError('Input must strictly precede the predicted root action')
    if (p['phase'] != 10 or p['currentChampion'] != turn['actor']
            or q['step']['actor'] != {'kind': 1, 'index': turn['actor']}
            or q['step']['phase'] != 10
            or obs['perspective'] != {'team': turn['view']['team'], 'champion': turn['actor']}
            or obs['own']['entity'] != {'kind': 1, 'index': turn['actor']}
            or obs['own']['team'] != turn['view']['team']):
        raise ValueError('PRE ownership mismatch')
    if any(label[k] != q['step'][k] for k in ('kind', 'from', 'to')):
        raise ValueError('Recorded action label differs from root event')
    if label['slot'] != q['step'].get('abilitySlot'):
        raise ValueError('Ability slot differs from recorded event')


def original_turns(manifest):
    """Yield original complete Fish turns in exactly the V1 preparation order."""
    source = Path(manifest['source'])
    for record in manifest['recordings']:
        folder = source/'extracted'/record['raw_sha256']
        if digest(folder/'turns.jsonl') != record['turns_sha256']:
            raise ValueError('Extracted turns changed')
        with (folder/'turns.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                turn = json.loads(line)
                if turn.get('record') != 'turn' or turn['view']['team_id'] != FISH_ID:
                    continue
                if not turn['complete'] or turn.get('diagnostic_only'):
                    continue
                if any(d['label']['root_class'] in ('unknown', 'error', 'rollover', 'resign') for d in turn['decisions']):
                    continue
                if turn['decisions']:
                    yield record, turn


def run(data_dir, baseline, out):
    manifest = json.loads((data_dir/'dataset.json').read_text())
    if digest(data_dir/'data.npz') != manifest['data_sha256']:
        raise ValueError('Original prepared data changed')
    frozen = json.loads((Path(manifest['source'])/'frozen.json').read_text())
    if digest(Path(manifest['source'])/'frozen.json') != manifest['source_freeze_sha256']:
        raise ValueError('Source freeze changed')
    original = {r['raw_sha256']: r for r in frozen['recordings']}
    payloads, groups, matches = {}, {}, set()
    verified_bundles = 0
    for r in manifest['recordings']:
        if r['match'] in matches:
            raise ValueError('Duplicate match ID')
        matches.add(r['match'])
        if r['group'] in groups and groups[r['group']] != r['split']:
            raise ValueError('Group crosses splits')
        groups[r['group']] = r['split']
        record = original[r['raw_sha256']]
        if record['split'] != 'exploratory':
            raise ValueError('Original reserved recording reused')
        for alias in record['aliases']:
            path = Path(alias['path'])
            if digest(path) != alias['bundle_sha256']:
                raise ValueError('Source bundle hash mismatch')
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as z:
                    payload = z.read('replay.repl26a')
            else:
                payload = path.read_bytes()
            raw = hashlib.sha256(payload).hexdigest()
            if raw != r['raw_sha256']:
                raise ValueError('Actual replay payload hash mismatch')
            payloads.setdefault(raw, set()).add((r['match'], r['split']))
            verified_bundles += 1
    duplicates = {h: sorted(rows) for h, rows in payloads.items() if len(rows) > 1}
    if duplicates:
        raise ValueError(f'Duplicate payloads: {duplicates}')
    with np.load(data_dir/'data.npz', allow_pickle=False) as archive:
        prepared = {key: archive[key] for key in archive.files}
    offsets = {s: 0 for s in ('train', 'validation', 'test')}
    turns = {s: 0 for s in offsets}
    for record, turn in original_turns(manifest):
        split = record['split']
        previous_event = None
        for decision in turn['decisions']:
            validate_decision(decision, turn)
            if previous_event and cursor(decision['pre_cursor']) < previous_event:
                raise ValueError('Overlapping or out-of-order decisions')
            previous_event = cursor(decision['event_cursor'])
            i = offsets[split]
            x, names = features(decision['observation'])
            if names != manifest['features'] or not np.array_equal(x, prepared[f'{split}_x'][i]):
                raise ValueError('Saved input differs from PRE-only features')
            if manifest['labels'][prepared[f'{split}_y'][i]] != action_name(decision['label']):
                raise ValueError('Saved label differs from recorded root action')
            offsets[split] += 1
        turns[split] += 1
        if prepared[f'{split}_offsets'][turns[split]] != offsets[split]:
            raise ValueError('Sequence boundary mismatch')
    if any(offsets[s] != len(prepared[f'{s}_y']) for s in offsets):
        raise ValueError('Unvalidated saved inputs')
    report = dict(status='passed', bundles_verified=verified_bundles, unique_payloads=len(payloads),
                  cross_split_duplicate_payloads=0, within_split_duplicate_payloads=0,
                  decisions_verified=offsets, turns_verified=turns, whole_groups_verified=len(groups),
                  checks=['Actual unzipped replay SHA256, not ZIP container or claimed identity',
                          'Every PRE cursor strictly precedes its recorded root; actor/phase/label ownership',
                          'Every saved feature equals PRE-only whitelist encoding, every label equals recorded event',
                          'Exact sequence boundaries and chronological action order; no future label inputs',
                          'Original reserved games excluded; original whole-group partitions preserved'],
                  limitation='Snapshot provenance relies on hash-verified prior extraction and its read-before-replayNext implementation; no new game simulation.')
    lock = dict(schema=2, dataset_sha256=digest(data_dir/'dataset.json'), data_sha256=digest(data_dir/'data.npz'),
                baseline_checkpoint_sha256=digest(baseline/'model.pt'), baseline_metrics_sha256=digest(baseline/'metrics.json'),
                test_arrays_sha256={key: hashlib.sha256(prepared[key].tobytes()).hexdigest()
                                    for key in ('test_x', 'test_y', 'test_offsets')},
                recordings=manifest['recordings'],
                policy='Test membership frozen. No development selection on test; training/validation only until candidates are locked.')
    immutable_json(out/'split-lock.json', lock)
    immutable_json(out/'audit.json', report)
    immutable_json(out/'baseline-v1.json', json.loads((baseline/'metrics.json').read_text()))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.data, a.baseline, a.out)
