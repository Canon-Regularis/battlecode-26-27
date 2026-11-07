"""Snapshot collection and controlled-retrain source files without opening games."""
import json
from pathlib import Path
import shutil
import sys

from .more_replays import ROOT, WORK, REPORTS, frozen, sha, log_command


def run():
    old = json.loads((ROOT / '.cambc/action-predictor/data/dataset.json').read_text())
    source_root = Path(old['source']).parents[2]
    files = list((ROOT / 'tools/action_predictor').glob('*.py'))
    files += list((ROOT / 'tools/action_predictor').glob('*.cjs'))
    files += [ROOT / 'tools/download_replays.py', ROOT / 'uv.lock', ROOT / 'pyproject.toml']
    files += [source_root / 'tools/replay_eval' / name for name in (
        'frozen_v1_5/micro_playback.cjs', 'frozen_v1_5/playback.cjs',
        'decisions/destinations_static.cjs')]
    snapshots = []
    for path in files:
        digest = sha(path)
        saved = WORK / 'provenance/sources' / (digest + '_' + path.name)
        saved.parent.mkdir(parents=True, exist_ok=True)
        if not saved.exists():
            shutil.copyfile(path, saved)
        assert sha(saved) == digest
        snapshots.append(dict(source=str(path), sha256=digest, snapshot=str(saved)))
    catalogues = {p.name: sha(p) for p in WORK.glob('candidate-groups*.json')}
    assets = next(Path(old['source']).parents[1].glob('asset-cache-5/*/visualiser/assets'))
    engine_files = {str(p.relative_to(assets)): sha(p) for p in assets.rglob('*') if p.is_file()}
    output = 'source-provenance-final.json' if '--final' in sys.argv else 'source-provenance.json'
    frozen(REPORTS / output, dict(
        source_snapshots=snapshots, candidate_catalogues=catalogues,
        official_reader_assets=str(assets), official_asset_hashes=engine_files,
        collection_commands=str(WORK / 'commands.jsonl'),
        user_updated_downloader_during_collection=True,
        downloader_history='Initial source hash is in runtime-provenance.json; final source hash is in membership.json. Per-batch old source snapshots were not captured.',
        preparation_workers=4, augmentation_workers=2, training_cpu_threads=4,
        preparation_note='Resumed completed, hash-checked TRAIN extraction receipts with four workers. Sampling, encoding and model training procedure unchanged.',
        test_policy='No test behaviour, features or labels read.',
    ))
    log_command(['.venv-action-predictor/Scripts/python.exe', '-m',
                 'tools.action_predictor.more_provenance', *(['--final'] if '--final' in sys.argv else [])],
                purpose='Snapshot source provenance; no replay behaviour read')
    print('Source snapshots and pinned reader-asset hashes retained.')


if __name__ == '__main__':
    run()
