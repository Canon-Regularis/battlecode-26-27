"""Bounded cached-PRE audit. Never invokes an engine or creates training arrays."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from ..audit import cursor, immutable_json
from ..data import action_name, digest
from ..rich_data import read_turns, SPATIAL
from ..targets import point
from ..learned_policy.sequence_data import ROOT, BASE, JOBS, ROOT_NAMES

REPORT = ROOT/'tools/action_predictor/experiments/v32'
PLAN = REPORT/'cache-plan-r2.json'
JOBS_HASH = '80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba'


def eligible_jobs():
    if digest(JOBS) != JOBS_HASH: raise ValueError('Eligible membership changed')
    return [j for j in json.loads(JOBS.read_text()) if j['split'] == 'train']


def freeze():
    jobs = eligible_jobs()
    groups = sorted({j['record']['group'] for j in jobs},
        key=lambda g: hashlib.sha256(('history32-v1:'+g).encode()).hexdigest())
    # Freeze all sibling games into the same partition BEFORE reading payloads.
    mapping = {g: ('fit' if i < 56 else 'tuning' if i < 75 else 'assessment') for i, g in enumerate(groups)}
    if len(groups) != 94: raise ValueError('Unexpected eligible group count')
    chosen = []
    limits = dict(fit=40, tuning=10, assessment=10)
    quotas = dict(fit=1625, tuning=1500, assessment=2000)
    for split, limit in limits.items():
        for group in [g for g in groups if mapping[g] == split][:limit]:
            j = min((j for j in jobs if j['record']['group'] == group), key=lambda j: j['record']['raw_sha256'])
            chosen.append(dict(payload=j['record']['raw_sha256'], group=group,
                partition=split, max_extra_roots=quotas[split]))
    immutable_json(PLAN, dict(jobs_sha256=JOBS_HASH,
        source_sha256=digest(__file__), group_partitions=mapping, jobs=chosen,
        selection='Hashed group order, then lowest payload hash per group; no labels/outcomes used. All sibling games share partition.',
        scope='Audit60eligibleTRAINgames, at most100000candidateadditionalroots, no new training arrays. Existing selected roots retained. Per-game extra cap applied in event order before inspecting labels; excluded roots remain genuine gaps.',
        feasibility=dict(fit_windows32=1000, fit_groups=30, assessment_windows32=200, assessment_groups=10),
        limitations='These partitions are pre-exposed research groups, not untouched certification. Any later clean fitting contrast must refit preprocessing and components on fit groups only. No cached pretrained priority distribution may silently enter.',
        new_fits=0, reserved_opened=0))


def label(turn, root, frame):
    actor = turn['actor']; obs = frame['observation']; own = obs['own']
    header = root['header']; step = header['step']
    if (frame['actor'] != actor or frame['pre'] != root['pre'] or
            own['entity'] != dict(kind=1, index=actor) or
            cursor(root['pre']) >= cursor(root['event'])):
        raise ValueError('Actor/PRE ordering mismatch')
    if 'pre_header' in frame:
        h = frame['pre_header']
        if h['phase'] != 10 or h['currentChampion'] != actor or h['team'] != own['team']:
            raise ValueError('Not a personal decision PRE')
    # Header describes the event's resulting state: end legitimately enters
    # phase13. The recorded command carries its own originating phase/round.
    if step['phase'] != 10 or step['actor'] != own['entity']:
        raise ValueError('Command actor/phase mismatch')
    if frame.get('round', turn['round']) != turn['round'] or step['round'] != turn['round']:
        raise ValueError('Round mismatch')
    name = ROOT_NAMES.get(step['kind'])
    if name == 'cast': name = 'cast_'+str(step.get('abilitySlot'))
    if name not in ('move', 'blocked', 'attack', 'cast_0', 'cast_1', 'end', 'priority',
                    'recall', 'submit', 'shop', 'ward', 'cancel', 'altar', 'teleport'):
        return None
    if name in SPATIAL and not point(step.get('to')): raise ValueError('Missing recorded coordinate')
    if name == 'priority' and type(step.get('priority')) is not int: raise ValueError('Missing priority integer')
    if name == 'move' and step.get('from') != own.get('position'): raise ValueError('Move origin differs from PRE')
    return dict(family=name, destination=step.get('to') if name in SPATIAL else None,
        priority=step.get('priority') if name == 'priority' else None,
        complete_arguments=name != 'shop')


def window_counts(streams):
    out = {}
    for horizon in (8, 16, 32):
        windows = crossing = roots = 0
        for stream in streams:
            for start in range(0, len(stream)-horizon+1, horizon):
                block = stream[start:start+horizon]
                if any(b[0] != a[0]+1 for a, b in zip(block, block[1:])):
                    raise ValueError('Window stitches a gap')
                windows += 1
                crossing += block[-1][1] > block[0][1]
                roots += horizon
        out[str(horizon)] = dict(windows=windows, across_rounds=crossing, roots=roots)
    return out


def audit_game(job, selection):
    payload = job['record']['raw_sha256']; bindings = {}
    def checked(path, expected=None):
        value = digest(path)
        if expected is not None and value != expected: raise ValueError('Source changed: '+str(path))
        bindings[str(path)] = value
        return path
    source = Path(job['manifest']['source'])/'extracted'/payload
    receipt = json.loads(checked(source/'receipt.json').read_text())
    if receipt['recording']['raw_sha256'] != payload: raise ValueError('Index receipt identity mismatch')
    index = checked(source/'index.jsonl', receipt['files']['index.jsonl'])
    cache = BASE.parent/'v7/games'/payload
    receipt = json.loads(checked(cache/'receipt.json').read_text())
    if receipt['raw_sha256'] != payload: raise ValueError('Frame receipt identity mismatch')
    frames = checked(cache/'frames.jsonl.gz', receipt['files']['frames.jsonl.gz'])
    selected = {}; observations = {}
    for t in read_turns(job['manifest'], job['record']):
        for d in t['decisions']:
            event = d['event_cursor']
            if event in selected: raise ValueError('Duplicate selected root')
            selected[event] = d
            observations[event] = dict(actor=t['actor'], pre=d['pre_cursor'], round=t['round'], observation=d['observation'])
    turns_path = Path(job['record']['augmented_path']) if 'augmented_path' in job['record'] else source/'turns.jsonl'
    checked(turns_path, job['record'].get('augmented_sha256', job['record']['turns_sha256']))
    teams = {f['observation']['own']['team'] for f in observations.values()}
    if len(teams) != 1: raise ValueError('Ambiguous recorded Fish ownership')
    seen = set()
    with gzip.open(frames, 'rt', encoding='utf-8') as f:
        for frame in map(json.loads, f):
            event = frame['event']
            if event in seen: raise ValueError('Duplicate cached root')
            seen.add(event)
            if frame['observation']['own']['team'] not in teams: raise ValueError('Wrong team frame')
            if event in observations and observations[event]['observation'] != frame['observation']:
                raise ValueError('Selected/cache observation disagreement')
            observations[event] = frame
    extras = sorted(set(observations)-set(selected), key=cursor)
    keep = set(selected) | set(extras[:selection['max_extra_roots']])
    actual = defaultdict(list); events = set()
    for line in index.open(encoding='utf-8'):
        turn = json.loads(line)
        if turn.get('record') != 'turn': continue
        for root in turn['roots']:
            if root['event'] in events: raise ValueError('Duplicate indexed root')
            events.add(root['event'])
            actual[turn['actor']].append((turn, root))
    if set(observations)-events: raise ValueError('Frame lacks indexed command')
    counts = Counter(); families = Counter(); streams = []; checked_selected = set()
    for actor, roots in sorted(actual.items()):
        roots.sort(key=lambda pair: cursor(pair[1]['event']))
        stream = []
        for ordinal, (turn, root) in enumerate(roots):
            event = root['event']
            if event not in keep:
                if stream: streams.append(stream); stream = []
                continue
            target = label(turn, root, observations[event])
            if target is None:
                counts['unmodeled_roots'] += 1
                if stream: streams.append(stream); stream = []
                continue
            if event in selected:
                d = selected[event]; expected = d['label']
                if (target['family'] != action_name(expected) or
                    (target['family'] in SPATIAL and target['destination'] != expected.get('to')) or
                    (target['family'] == 'priority' and target['priority'] != expected.get('priority'))):
                    raise ValueError('Selected command parity failed')
                checked_selected.add(event)
            counts['selected_roots' if event in selected else 'extra_roots'] += 1
            counts['unavailable_shop_arguments'] += not target['complete_arguments']
            families[target['family']] += 1
            stream.append((ordinal, turn['round']))
        if stream: streams.append(stream)
    if checked_selected != set(selected) or len(selected) != job['rows']:
        raise ValueError('Selected coverage mismatch')
    return dict(**selection, engine=job['record']['engine_version'], counts=dict(counts), families=dict(families),
        candidate_extra_roots_before_cap=len(extras), windows=window_counts(streams),
        max_run=max(map(len, streams), default=0), bindings=bindings,
        label_scope='Recorded command header and personal PRE identity/chronology validated; selected labels matched. No new POST/outcome verification, hidden intent, full engine legality or resolved entity target identity claimed. Shop arguments unavailable.',
        new_training_rows=0)


def run():
    plan_path = PLAN; plan = json.loads(plan_path.read_text())
    if plan['source_sha256'] != digest(__file__): raise ValueError('Frozen audit source changed')
    jobs = {j['record']['raw_sha256']: j for j in eligible_jobs()}
    results = []
    for selection in plan['jobs']:
        job = jobs[selection['payload']]
        if job['record']['group'] != selection['group']: raise ValueError('Group mismatch')
        result = audit_game(job, selection)
        immutable_json(REPORT/'games'/(selection['payload']+'.json'), result)
        results.append(result)
        print('Validated', len(results), '/', len(plan['jobs']), selection['partition'], flush=True)
    totals = {}
    for split in ('fit', 'tuning', 'assessment'):
        subset = [r for r in results if r['partition'] == split]
        totals[split] = dict(extra_roots=sum(r['counts'].get('extra_roots', 0) for r in subset),
            windows32=sum(r['windows']['32']['windows'] for r in subset),
            groups_with_windows32=sum(r['windows']['32']['windows'] > 0 for r in subset),
            windows32_across_rounds=sum(r['windows']['32']['across_rounds'] for r in subset))
    gate = (totals['fit']['windows32'] >= 1000 and totals['fit']['groups_with_windows32'] >= 30 and
            totals['assessment']['windows32'] >= 200 and totals['assessment']['groups_with_windows32'] >= 10)
    immutable_json(REPORT/'cache-feasibility.json', dict(plan_sha256=digest(plan_path), totals=totals,
        feasibility_gate_passed=gate, games=results, new_fits=0, new_training_rows=0, reserved_opened=0,
        next='Review label/provenance and capacity evidence before any training-array assembly or temporal fit. This gate is feasibility, not benefit or untouched-test evidence.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['freeze', 'run'])
    (freeze if p.parse_args().command == 'freeze' else run)()
