"""Bounded TRAIN-only cache inventory for later segment/grounding work.

No new extraction, neural forward, optimizer, inferred intent or proposed-action
simulation. This module is not imported by the frozen two-arm experiment.
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path
from ..audit import immutable_json, cursor
from ..data import digest
from ..rich_data import read_turns
from ..learned_policy.sequence_data import ROOT, BASE, JOBS
from .data import REPORT


def inventory(job):
    payload = job['record']['raw_sha256']
    history = BASE.parent/'v7/games'/payload
    receipt_path = history/'receipt.json'
    receipt = json.loads(receipt_path.read_text())
    frames_path = history/'frames.jsonl.gz'
    if digest(frames_path) != receipt['files']['frames.jsonl.gz']:
        raise RuntimeError('Existing personal frame archive changed')
    source = Path(job['manifest']['source'])/'extracted'/payload
    index_path = source/'index.jsonl'
    expected = json.loads((source/'receipt.json').read_text())['files']['index.jsonl']
    if digest(index_path) != expected: raise RuntimeError('Recorded own-root index changed')
    actual = defaultdict(list)
    for line in index_path.open():
        turn = json.loads(line)
        if turn.get('record') == 'turn':
            for root in turn['roots']: actual[turn['actor']].append(root)
    for roots in actual.values(): roots.sort(key=lambda r: cursor(r['event']))
    selected = {}
    for turn in read_turns(job['manifest'], job['record']):
        for decision in turn['decisions']:
            selected[decision['event_cursor']] = dict(actor=turn['actor'], pre=decision['pre_cursor'],
                                                     observation=decision['observation'])
    historical = {}
    with gzip.open(frames_path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            frame = json.loads(line)
            if frame['event'] in historical: raise RuntimeError('Duplicate cached personal frame')
            if frame['pre_header']['phase'] != 10 or frame['pre_header']['currentChampion'] != frame['actor']:
                raise RuntimeError('Unexpected personal PRE phase/actor')
            historical[frame['event']] = frame
    observations = dict(historical)
    for event, frame in selected.items():
        if event in historical:
            if historical[event]['observation'] != frame['observation']:
                raise RuntimeError('Selected versus historical PRE observation differs')
        observations[event] = frame
    counts = defaultdict(int)
    runs = []
    for actor, roots in actual.items():
        available_run = 0
        remembered = {}
        previous_known = set()
        for root in roots:
            event = root['event']
            if event not in observations:
                if available_run: runs.append(available_run)
                available_run = 0
                counts['unavailable_own_roots'] += 1
                # Identity inventory can carry last observations, but the gap
                # remains explicit; no state survival/continued life is inferred.
                continue
            available_run += 1
            counts['available_personal_PRE_roots'] += 1
            counts['selected_roots'] += event in selected
            counts['additional_already_cached_roots'] += event not in selected
            frame = observations[event]
            if frame['actor'] != actor or frame['pre'] != root['pre']:
                raise RuntimeError('Cache identity differs from historical root')
            obs = frame['observation']
            current = set()
            for entity in obs.get('entities', []):
                key = (entity['entity']['kind'], entity['entity']['index'])
                if key[0] not in (1, 2): continue
                if not entity.get('known', 0) & 1:
                    counts['currently_unknown_identity_entries'] += 1
                    continue
                current.add(key)
                counts['known_entity_tokens'] += 1
                counts['known_camp_tokens'] += key[0] == 2
                counts['known_dead_tokens'] += entity.get('alive') is False or entity.get('health', 1) <= 0
                if key in remembered:
                    counts['reobserved_identity_tokens'] += 1
                    counts['reobserved_after_absence'] += key not in previous_known
                remembered[key] = entity
            previous_known = current
        if available_run: runs.append(available_run)
    return dict(engine=job['record']['engine_version'], group=job['record']['group'] if 'group' in job['record'] else job.get('group'),
        payload_sha256=payload, counts=dict(counts), available_contiguous_run_count=len(runs),
        maximum_available_run=max(runs, default=0), roots_in_runs_at_least16=sum(n for n in runs if n >= 16),
        bindings={str(p): digest(p) for p in (receipt_path, frames_path, index_path)},
        interpretation='Available PRE plus recorded index command is a potential new eligible demonstration row, not yet an independently validated full command label or new training dataset. Entity identity keys are audit-only; no index enters a learned feature.')


def run():
    if digest(JOBS) != '80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba':
        raise RuntimeError('Eligible jobs changed')
    selected = {}
    for job in json.loads(JOBS.read_text()):
        if job['split'] != 'train': continue
        selected.setdefault(job['record']['engine_version'], job)
    if set(selected) != {'2.0.0', '3.0.0'}: raise RuntimeError('Expected historical engines')
    results = [inventory(job) for job in selected.values()]
    immutable_json(REPORT/'TRAIN-cache-opportunities.json', dict(
        selection='First eligible TRAIN game per engine in canonical job order, no target-label or outcome selection',
        games=results, jobs_sha256=digest(JOBS), source_sha256=digest(__file__),
        next='Verify exact label/parameter construction and within-stream identity alignment before any expanded-data or grounded-objective fit. Keep the current H00/H01 frozen comparison unchanged.',
        new_fits=0, reserved_opened=0, engine_queries=0))


if __name__ == '__main__': run()
