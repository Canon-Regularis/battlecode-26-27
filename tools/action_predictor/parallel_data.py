"""Run the existing encoder per game, then concatenate in the original order."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np

from . import rich_data
from .audit import immutable_json
from .data import digest


def shard(manifest, record, work, reports, augmented):
    rich_data.WORK, rich_data.REPORTS = Path(work), Path(reports)
    split = 'train-shard-' + record['raw_sha256']
    one = manifest | dict(recordings=[record | dict(split=split)])
    rich_data.load_manifest = lambda: one
    rich_data.build((split,), augment=augmented)
    return str(Path(work) / (split + ('-aug' if augmented else '') + '.npz'))


def build(manifest, work, reports, splits=('train',), augment=False, workers=4):
    work, reports = Path(work), Path(reports)
    groups = sorted({r['group'] for r in manifest['recordings']})
    group_ids = {g: i for i, g in enumerate(groups)}
    for split in splits:
        output_name = split + ('-aug' if augment else '')
        output = work / (output_name + '.npz')
        receipt_path = work / (output_name + '-data.json')
        if output.exists():
            assert digest(output) == json.loads(receipt_path.read_text())['sha256']
            continue
        records = [r for r in manifest['recordings'] if r['split'] == split]
        small = manifest | dict(recordings=[])
        paths = {}
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(shard, small, r, str(work), str(reports), augment): r for r in records}
            for i, job in enumerate(as_completed(jobs), 1):
                try:
                    paths[jobs[job]['raw_sha256']] = Path(job.result())
                except Exception:
                    for pending in jobs:
                        pending.cancel()
                    raise
                if i % 10 == 0 or i == len(jobs):
                    print('Encoded whole-game shards', output_name, i, '/', len(jobs), flush=True)
        ordered = [paths[r['raw_sha256']] for r in records]
        metadata = [json.loads(p.with_name(p.stem + '-data.json').read_text()) for p in ordered]
        names, labels = metadata[0]['feature_names'], metadata[0]['labels']
        assert all(m['feature_names'] == names and m['labels'] == labels for m in metadata)
        with np.load(ordered[0], allow_pickle=False) as archive:
            keys = archive.files
        arrays = {}
        for key in keys:
            parts = []
            for record, path in zip(records, ordered):
                with np.load(path, allow_pickle=False) as archive:
                    assert archive.files == keys
                    values = archive[key]
                if key == 'group':
                    values = np.full_like(values, group_ids[record['group']])
                parts.append(values)
            arrays[key] = np.concatenate(parts)
        np.savez_compressed(output, **arrays)
        quality = Counter()
        for meta in metadata:
            quality.update(meta['quality'])
        immutable_json(receipt_path, dict(
            sha256=digest(output), rows=len(arrays['y']), quality=quality,
            supplement_code_sha256=digest(Path(rich_data.__file__).with_name('supplement.cjs')),
            feature_names=names, basic_features=200, labels=labels, groups=groups,
        ))
        print(output_name, len(arrays['y']), 'actions; original record order retained.', flush=True)
