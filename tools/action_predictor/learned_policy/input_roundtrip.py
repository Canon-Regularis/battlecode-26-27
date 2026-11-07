"""Bounded changed-input parity, reusing recorded personal PREs; no fit/engine."""
import gzip
import json
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
import torch
from .sequence_data import ROOT, BASE, WORK, REPORT, JOBS
from .data import load, causal_inputs, geometry
from .personal_inputs import PersonalInputs
from ..priority_fit_v3 import load_base
from ..proposal_predictor import load_proposal_predictor
from ..proposal_data import evidence
from ..audit import cursor, immutable_json
from ..data import digest


def run():
    torch.set_num_threads(4)
    _, saved = load_base()
    d = load('validation', saved)
    eligible = [j for j in json.loads(JOBS.read_text()) if j['split'] == 'validation']
    jobs = [next(j for j in eligible if j['record']['engine_version'] == v)
            for v in ('2.0.0', '3.0.0')]
    counts, bindings, maxima = Counter(), [], Counter()
    for job in jobs:
        raw = job['record']['raw_sha256']
        turns, supps, route = evidence(job)
        decisions = [(t, x) for t in turns for x in t['decisions']]
        index = Path(job['manifest']['source']) / 'extracted' / raw / 'index.jsonl'
        roots = defaultdict(list)
        for line in index.open():
            t = json.loads(line)
            if t.get('record') == 'turn':
                for r in t['roots']:
                    roots[t['actor']].append((r, t['round'], t['id']))
        for rows in roots.values():
            rows.sort(key=lambda r: cursor(r[0]['event']))
        framepath = BASE.parent / 'v7/games' / raw / 'frames.jsonl.gz'
        frames = {}
        with gzip.open(framepath, 'rt') as f:
            for line in f:
                r = json.loads(line)
                frames[r['event']] = r
        prioritypath = BASE.parent / 'v8/priority' / raw / 'pre.jsonl.gz'
        states = {}
        with gzip.open(prioritypath, 'rt') as f:
            for line in f:
                r = json.loads(line)
                if r['record'] == 'priority_pre':
                    states[r['event']] = {k: r[k] for k in
                        ('pre', 'actor', 'team', 'round', 'current', 'scheduled')}
        # Fixed prefixes plus first occurrence of each supported family/context;
        # this selects evidence to check, never changes any policy prediction.
        selected = set(range(min(16, len(decisions))))
        start = job['offset']; end = start + job['rows']
        for code in np.unique(d['raw']['y'][start:end]):
            selected.add(int(np.flatnonzero(d['raw']['y'][start:end] == code)[0]))
        selected_events = {x['event_cursor'] for _, x in decisions}
        actors, pointers = {}, Counter()
        for local in sorted(selected):
            t, decision = decisions[local]
            actor = t['actor']; row = start + local
            if actor not in actors:
                actors[actor] = PersonalInputs(load_proposal_predictor(actor).frozen, actor)
            provider = actors[actor]
            while pointers[actor] < len(roots[actor]):
                root, rnd, ownturn = roots[actor][pointers[actor]]
                if cursor(root['event']) > cursor(decision['pre_cursor']):
                    break
                f = frames.get(root['event'])
                provider.observe(root['event'], root['pre'], root['header']['step'],
                                 rnd, ownturn,
                                 f['observation'] if f else None,
                                 f['supplement'] if f else None, route)
                if root['event'] in selected_events:
                    provider.mark_policy_action(root['event'])
                pointers[actor] += 1
            current = provider.prepare(decision['observation'], supps[decision['id']],
                                       route, t['round'], t['id'],
                                       decision['pre_cursor'], states[decision['event_cursor']])
            cached = causal_inputs(d, np.array([row]))
            for key, actual in current['inputs'].items():
                expected = cached[key]
                if key == 'entities':
                    expected = expected[:, cached['entity_mask'][0]]
                if key == 'entity_mask':
                    expected = torch.ones_like(actual)
                diff = float((actual.float() - expected.float()).abs().max())
                maxima[key] = max(maxima[key], diff)
                torch.testing.assert_close(actual, expected, atol=1e-6, rtol=0,
                                           msg=lambda msg: f'{row} {key}: {msg}')
            for key, expected in geometry(d, np.array([row])).items():
                torch.testing.assert_close(current['geometry'][key], expected, atol=0, rtol=0)
            assert int(current['priority_mode'][0]) == int(d['priority_mode'][row])
            error = abs(float(current['priority_mode_logp'][0]) - float(d['priority_mode_logp'][row]))
            maxima['priority_mode_logp'] = max(maxima['priority_mode_logp'], error)
            assert error < 2e-5
            counts['cases'] += 1; counts['engine_' + job['record']['engine_version']] += 1
            counts['true_family_' + str(int(d['raw']['y'][row]))] += 1
        bindings.append(dict(raw=raw, index_sha256=digest(index),
                             frames_sha256=digest(framepath),
                             priority_sha256=digest(prioritypath)))
        print('Personal input parity', job['record']['engine_version'], counts['cases'], flush=True)
    immutable_json(REPORT / 'personal-input-roundtrip.json', dict(
        cases=dict(counts), maximum_absolute_difference=dict(maxima), bindings=bindings,
        source_sha256=digest(__file__), adapter_sha256=digest(Path(__file__).with_name('personal_inputs.py')),
        scope='Bounded changed-input check from original personal PREs and chronological own roots, reusing historical extraction. No model-quality claim, full legality or all-row parity claim.',
        new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    run()
