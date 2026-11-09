"""Static public maps aligned to the unchanged V5 training/V4 validation rows."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
import torch.nn.functional as F

from .more_replays import ROOT, WORK as MORE, REPORTS as MORE_REPORTS, frozen, sha, log_command
from .more_train import OLD
from . import rich_data
from .data import action_name
from .audit import validate_decision

WORK = ROOT / '.cambc/action-predictor/v6'
REPORTS = ROOT / 'tools/action_predictor/experiments/v6'
CHANNELS = ['in_bounds', 'walls', 'holes', 'bushes', 'altars', 'ally_spawn', 'enemy_spawn', 'camp_spawn']


def sources():
    old = json.loads((ROOT / '.cambc/action-predictor/data/dataset.json').read_text())
    new = json.loads((MORE / 'training-source.json').read_text())
    membership = json.loads((MORE_REPORTS / 'membership.json').read_text())
    allowed = {r['raw_sha256'] for r in membership['records'] if r['split'] == 'train'}
    assert {r['raw_sha256'] for r in new['recordings']} == allowed
    blocks = []
    for name, manifest, work, split, augmented in [
        ('old_train', old, OLD, 'train', True),
        ('new_train', new, MORE, 'train', True),
        ('validation', old, OLD, 'validation', False),
    ]:
        additions = json.loads((work / 'augmentation.json').read_text()) if augmented else {}
        records = [r | additions.get(r['raw_sha256'], {}) for r in manifest['recordings'] if r['split'] == split]
        blocks.append(dict(name=name, manifest=manifest, work=work, records=records,
                           groups=sorted({r['group'] for r in manifest['recordings']})))
    return blocks


def extract_map(record, block, reader, assets):
    raw = record['raw_sha256']
    directory = WORK / 'maps' / raw
    directory.mkdir(parents=True, exist_ok=True)
    output, receipt = directory / 'map.json', directory / 'receipt.json'
    code = Path(__file__).with_name('public_map.cjs')
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        assert saved['code_sha256'] == sha(code) and saved['output_sha256'] == sha(output)
    else:
        payload = block['work'] / 'supplement' / raw / 'raw.bin'
        assert sha(payload) == raw
        assert not output.exists(), 'Incomplete map output requires inspection'
        query = dict(raw=str(payload), raw_sha256=raw, reader=str(reader), assets=str(assets), output=str(output))
        query_path = directory / 'query.json'
        frozen(query_path, query)
        command = ['node', str(code), str(query_path)]
        log_command(command, purpose='Public STATIC terrain/objective layout only; TRAIN or original validation',
                    query_sha256=sha(query_path))
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError(result.stderr[-3000:])
        frozen(receipt, dict(code_sha256=sha(code), output_sha256=sha(output), raw_sha256=raw))
    data = json.loads(output.read_text())
    with (block['work'] / 'supplement' / raw / 'pre.jsonl').open() as stream:
        route = json.loads(stream.readline())['route']
    assert data['route'] == route, 'Static geometry differs from baseline inputs'
    q = json.loads((block['work'] / 'supplement' / raw / 'query.json').read_text())
    team = q['turns'][0]['team']
    assert team in (0, 1)
    return raw, data, team


def raster(data, team):
    route = data['route']; w, h = route['width'], route['height']
    result = np.zeros((8, h, w), dtype=np.uint8)
    result[0] = 1
    for channel, key in [(1, 'walls'), (2, 'holes'), (3, 'bushes')]:
        result[channel].reshape(-1)[data[key]] = 1
    for channel, points in [(4, route['altars']), (7, data['camps'])]:
        for point in points:
            result[channel, point['y'], point['x']] = 1
    for channel, side in [(5, team), (6, 1 - team)]:
        area = route['spawns'][side]
        result[channel, area['minY']:area['maxY'], area['minX']:area['maxX']] = 1
    return result


def align(block, raw_arrays, start, map_ids, layouts, row_maps, row_xy, row_known):
    names = json.loads((block['work'] / 'train-data.json').read_text())['feature_names']
    ix, iy, ik = [names.index(name) for name in ('relative_map_x', 'relative_map_y', 'position_known')]
    labels = block['manifest']['labels']
    offset = len(json.loads((OLD / 'train-data.json').read_text())['groups']) if block['name'] == 'new_train' else 0
    cursor = start
    for record in block['records']:
        raw = record['raw_sha256']; turns = rich_data.read_turns(block['manifest'], record)
        expected_xy, expected_known, expected_y, expected_round = [], [], [], []
        for turn in turns:
            for decision in turn['decisions']:
                validate_decision(decision, turn)
                position = decision['observation']['own'].get('position')
                known = isinstance(position, dict) and all(type(position.get(k)) is int for k in ('x', 'y'))
                expected_xy.append([position['x'], position['y']] if known else [0, 0])
                expected_known.append(known)
                expected_y.append(labels.index(action_name(decision['label'])))
                expected_round.append(turn['round'])
        count = len(expected_y); stop = cursor + count
        route = layouts[raw]['route']; w, h = route['width'], route['height']
        known = raw_arrays['x'][cursor:stop, ik] > .5
        xy = np.rint(raw_arrays['x'][cursor:stop][:, [ix, iy]] * np.array([w, h])).astype(np.int16)
        assert np.array_equal(known, expected_known)
        assert np.array_equal(xy, np.asarray(expected_xy)), 'Map position differs from personal PRE'
        assert np.array_equal(raw_arrays['y'][cursor:stop], expected_y), 'Action row alignment differs'
        assert np.array_equal(raw_arrays['round'][cursor:stop], expected_round)
        group = block['groups'].index(record['group']) + offset
        assert np.all(raw_arrays['group'][cursor:stop] == group)
        row_maps[cursor:stop] = map_ids[raw]
        row_xy[cursor:stop] = xy
        row_known[cursor:stop] = known
        cursor = stop
    return cursor


def prepare():
    WORK.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    if (REPORTS / 'data-ready.json').exists():
        assert sha(WORK / 'maps.npz') == json.loads((REPORTS / 'data-ready.json').read_text())['maps_sha256']
        return
    blocks = sources()
    old = blocks[0]['manifest']; reader = Path(old['source']).parents[2] / 'tools/replay_eval'
    assets = next(Path(old['source']).parents[1].glob('asset-cache-5/*/visualiser/assets'))
    layouts, teams = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(extract_map, r, b, reader, assets) for b in blocks for r in b['records']]
        for i, job in enumerate(as_completed(jobs), 1):
            raw, data, team = job.result(); layouts[raw] = data; teams[raw] = team
            if i % 50 == 0 or i == len(jobs):
                print('STATIC public maps', i, '/', len(jobs), flush=True)
    unique, map_ids = {}, {}
    for block in blocks:
        for record in block['records']:
            raw = record['raw_sha256']; image = raster(layouts[raw], teams[raw])
            key = hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()
            if key not in unique:
                unique[key] = (len(unique), image)
            map_ids[raw] = unique[key][0]
    images = [item[1] for item in unique.values()]
    max_h, max_w = max(x.shape[1] for x in images), max(x.shape[2] for x in images)
    atlas = np.zeros((len(images), 8, max_h + 22, max_w + 22), dtype=np.uint8)
    global_atlas = []; sizes = []
    for i, image in enumerate(images):
        h, w = image.shape[1:]; sizes.append([w, h]); atlas[i, :, 11:11+h, 11:11+w] = image
        tensor = torch.from_numpy(image).float()[None]
        coarse = F.adaptive_avg_pool2d(tensor, (32, 32))
        coarse[:, 4:] = F.adaptive_max_pool2d(tensor[:, 4:], (32, 32))
        global_atlas.append(coarse[0].numpy())
    arrays = dict(atlas=atlas, global_atlas=np.stack(global_atlas), sizes=np.array(sizes, dtype=np.int16))
    total_rows = {}
    for split, path, selected in [('train', MORE / 'combined-train.npz', blocks[:2]),
                                  ('validation', OLD / 'validation.npz', blocks[2:])]:
        with np.load(path, allow_pickle=False) as archive:
            raw = {k: archive[k] for k in ('x', 'y', 'round', 'group')}
        n = len(raw['y']); row_maps = np.zeros(n, np.uint16); row_xy = np.zeros((n, 2), np.int16); row_known = np.zeros(n, bool)
        cursor = 0
        for block in selected:
            cursor = align(block, raw, cursor, map_ids, layouts, row_maps, row_xy, row_known)
        assert cursor == n
        arrays.update({split+'_map_id': row_maps, split+'_xy': row_xy, split+'_known': row_known})
        total_rows[split] = n
        print('Map/PRE alignment passed', split, n, 'rows', flush=True)
    np.savez_compressed(WORK / 'maps.npz', **arrays)
    frozen(REPORTS / 'data-ready.json', dict(
        maps_sha256=sha(WORK / 'maps.npz'), channels=CHANNELS, map_layouts=len(images), rows=total_rows,
        train_sha256=sha(MORE / 'combined-train.npz'), validation_sha256=sha(OLD / 'validation.npz'),
        membership_sha256=sha(MORE_REPORTS / 'membership.json'), new_reserved_games_opened=0,
        provenance='Every auxiliary row checked against its cached personal PRE position, action label, round and whole-group ID. Static map only; map ID is a lookup index and is never a neural input.',
    ))


class MapInputs:
    def __init__(self, arrays, split):
        self.atlas = torch.from_numpy(arrays['atlas'])
        self.global_atlas = torch.from_numpy(arrays['global_atlas'])
        self.sizes = torch.from_numpy(arrays['sizes']).long()
        self.map_id = torch.from_numpy(arrays[split+'_map_id'].astype(np.int64))
        self.xy = torch.from_numpy(arrays[split+'_xy'].astype(np.int64))
        self.known = torch.from_numpy(arrays[split+'_known'])

    def batch(self, indices):
        ids, xy, known = self.map_id[indices], self.xy[indices], self.known[indices]
        local = self.atlas[ids[:, None, None, None], torch.arange(8)[None, :, None, None],
                           xy[:, 1, None, None, None] + torch.arange(23)[None, None, :, None],
                           xy[:, 0, None, None, None] + torch.arange(23)[None, None, None, :]].float()
        local *= known[:, None, None, None]
        global_map = torch.cat((self.global_atlas[ids], torch.zeros(len(ids), 1, 32, 32)), 1)
        at = (xy * 32 // self.sizes[ids]).clamp(0, 31)
        selected = torch.nonzero(known).flatten()
        global_map[selected, 8, at[selected, 1], at[selected, 0]] = 1
        return local, global_map


if __name__ == '__main__':
    log_command(['.venv-action-predictor/Scripts/python.exe', '-m', 'tools.action_predictor.spatial_data'],
                purpose='Public map extraction and alignment; no new reserved games opened')
    prepare()
