"""Read immutable extracted replays; never use POST state or future actions."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

FISH_ID = '1890540d-1ffc-4847-adbf-d0d08772f268'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 0.0


def features(obs):
    """Fixed relative features. Unknown entities contribute nothing, including counts."""
    own = obs['own']
    pos = own.get('position', {'x': 0, 'y': 0})
    hp = max(number(own.get('maxHealth')), 1)
    values = [number(own.get('health')) / hp, math.log1p(max(0, number(own.get('gems')))),
              number(own.get('alive')), number(own.get('attackRange')) / 10,
              number(own.get('channelTimer')) / 10]
    names = ['health_fraction', 'log_gems', 'alive', 'attack_range', 'channel_timer']
    for i in range(13):
        names.append(f'champion_{i}')
        values.append(float(own.get('type') == i))
    for i in range(5):
        names.append(f'channel_{i}')
        values.append(float(own.get('channelType') == i))
    for i in range(16):
        names.append(f'flag_{i}')
        values.append(float(bool(int(own.get('roundFlags', 0)) & (1 << i))))
    for slot in range(2):
        for key in ('cooldowns', 'charges'):
            names.append(f'{key}_{slot}')
            values.append(number((own.get(key) or [0, 0])[slot]) / 10)
        props = (own.get('abilityProps') or [{}, {}])[slot]
        for kind in range(8):
            names.append(f'ability_{slot}_type_{kind}')
            values.append(float(props.get('type') == kind))
    items = own.get('items', [])
    for i in range(84):
        names.append(f'item_{i}')
        values.append(math.log1p(max(0, number(items[i] if i < len(items) else 0))))
    for category in ('enemy', 'ally', 'camp'):
        visible = []
        for e in obs.get('entities', []):
            if not int(e.get('known', 0)) & 1 or not e.get('position'):
                continue
            if e.get('health', 0) <= 0:
                continue
            kind = e['entity']['kind']
            cat = 'camp' if kind == 2 else ('ally' if e.get('team') == own.get('team') else 'enemy')
            if kind not in (1, 2) or cat != category:
                continue
            dx = number(e['position']['x']) - number(pos['x'])
            dy = number(e['position']['y']) - number(pos['y'])
            visible.append((max(abs(dx), abs(dy)), dx, dy, e))
        visible.sort(key=lambda x: x[:3])
        names.append(f'{category}_visible_count')
        values.append(min(len(visible), 50) / 10)
        for i in range(3):
            names.extend(f'{category}_{i}_{k}' for k in ('present', 'dx', 'dy', 'distance', 'hp', 'attack_range'))
            if i >= len(visible):
                values.extend([0.] * 6)
            else:
                dist, dx, dy, e = visible[i]
                values.extend([1., dx / 32, dy / 32, dist / 32,
                               number(e.get('health')) / max(number(e.get('maxHealth')), 1),
                               number(e.get('attackRange')) / 10])
    return np.array(values, dtype=np.float32), names


def action_name(label):
    name = label['root_class']
    return f'{name}_{label["slot"]}' if label.get('slot') is not None else name


def prepare(source, output, seed=26):
    source, output = Path(source), Path(output)
    if any((output/name).exists() for name in ('data.npz', 'dataset.json')):
        raise FileExistsError('Prepared datasets are immutable; choose a fresh output directory')
    output.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((source / 'frozen.json').read_text())
    records = [r for r in frozen['recordings'] if r['split'] == 'exploratory'
               and any(v['team_id'] == FISH_ID for v in r['views'])]
    groups = sorted({r['group'] for r in records}, key=lambda g: hashlib.sha256(f'{seed}|{g}'.encode()).hexdigest())
    if len(groups) < 7:
        raise ValueError('At least seven independent match groups required')
    ntest = max(1, round(len(groups) * .15))
    nval = max(1, round(len(groups) * .15))
    splits = {g: ('test' if i < ntest else 'validation' if i < ntest+nval else 'train') for i, g in enumerate(groups)}
    sequences, provenance, seen = [], [], set()
    for record in records:
        raw = record['raw_sha256']
        if raw in seen:
            raise ValueError('Duplicate replay identity')
        seen.add(raw)
        folder = source / 'extracted' / raw
        receipt = json.loads((folder / 'receipt.json').read_text())
        path = folder / 'turns.jsonl'
        if receipt['status'] != 'complete' or receipt['recording'] != record or digest(path) != receipt['files']['turns.jsonl']:
            raise ValueError(f'Invalid extraction receipt: {record["match"]}')
        if receipt['config']['freeze'] != frozen['freeze_sha256']:
            raise ValueError('Extraction freeze mismatch')
        count = 0
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                turn = json.loads(line)
                if turn.get('record') != 'turn':
                    continue
                if turn['view']['team_id'] != FISH_ID or not turn['complete'] or turn.get('diagnostic_only'):
                    continue
                xs, ys = [], []
                for decision in turn['decisions']:
                    obs = decision['observation']
                    if obs['perspective']['team'] != turn['view']['team'] or obs['own']['entity']['index'] != turn['actor']:
                        raise ValueError('Personal observation actor/team mismatch')
                    if decision['label']['root_class'] in ('unknown', 'error', 'rollover', 'resign'):
                        xs = []
                        break
                    x, names = features(obs)
                    xs.append(x)
                    ys.append(action_name(decision['label']))
                if xs:
                    sequences.append((splits[record['group']], np.stack(xs), ys))
                    count += 1
        provenance.append({k: record[k] for k in ('match', 'group', 'raw_sha256', 'engine_version', 'map_hash')}
                          | {'split': splits[record['group']], 'turns': count,
                             'turns_sha256': receipt['files']['turns.jsonl']})
        if len(provenance) % 20 == 0:
            print(f'Prepared {len(provenance)}/{len(records)} recordings', flush=True)
    # Vocabulary is learned exclusively from training games. Zero is an unseen action.
    labels = ['<unknown>'] + sorted({y for s, _, ys in sequences if s == 'train' for y in ys})
    ids = {label: i for i, label in enumerate(labels)}
    arrays, statistics = {}, {}
    for split in ('train', 'validation', 'test'):
        selected = [(x, ys) for s, x, ys in sequences if s == split]
        offsets = np.cumsum([0] + [len(x) for x, _ in selected])
        arrays[f'{split}_x'] = np.concatenate([x for x, _ in selected])
        arrays[f'{split}_y'] = np.array([ids.get(y, 0) for _, ys in selected for y in ys], dtype=np.int64)
        arrays[f'{split}_offsets'] = offsets
        statistics[split] = dict(groups=sum(s == split for s in splits.values()),
                                 games=sum(r['split'] == split for r in provenance), turns=len(selected),
                                 actions=int(offsets[-1]), unknown_actions=int((arrays[f'{split}_y'] == 0).sum()))
    np.savez_compressed(output / 'data.npz', **arrays)
    manifest = dict(schema=1, fish_team_id=FISH_ID, source=str(source.resolve()), seed=seed,
                    source_freeze_sha256=digest(source/'frozen.json'), data_sha256=digest(output/'data.npz'),
                    labels=labels, features=names, statistics=statistics, recordings=provenance,
                    sequence_boundary='Complete sampled personal turn; hidden state resets each turn.',
                    scope='Next action TYPE including cast slot; no movement destination or target prediction.',
                    sampling='Existing lowest-hash samples, up to 32 turns per actor per game. Metrics are sample-weighted.',
                    evaluation='New group-disjoint split of previously exploratory games, not a pristine external test. Original reserved games excluded.')
    (output / 'dataset.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(statistics, indent=2), flush=True)
    return manifest
