"""Raw personal-PRE -> stateful actor decisions, with forward replay filtering.

No proposed action is sent to a game. Earlier recorded Fish actions update the
replay filter only AFTER each prediction. Actual-own-action SDK commit is a
separate contract test, not replaced by invented successful executions here.
"""
import gzip
import json
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT, JOBS
from .data import load, targets
from .model import GoalPolicy
from .actor import PolicyActor
from .personal_inputs import PersonalInputs
from .portable_actor import PortableActor
from ..priority_fit_v3 import load_base
from ..proposal_predictor import load_proposal_predictor
from ..proposal_data import evidence
from ..audit import cursor, immutable_json
from ..data import digest
from .. import reliable_train as rt


@torch.no_grad()
def run(identifier):
    torch.set_num_threads(4)
    info = json.loads((REPORT / f'{identifier}.json').read_text())
    path = WORK / f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(path) == info['checkpoint_sha256']
    checkpoint = torch.load(path, weights_only=False); teacher, saved = load_base()
    model = GoalPolicy(teacher, checkpoint['persistent']); model.load_state_dict(checkpoint['state']); model.eval()
    d = load('validation', saved)
    with np.load(WORK / f'runs/{identifier}/validation-predictions.npz') as z:
        predictions = {k:z[k] for k in z.files}
    eligible = [j for j in json.loads(JOBS.read_text()) if j['split'] == 'validation']
    jobs = [next(j for j in eligible if j['record']['engine_version'] == version)
            for version in ('2.0.0', '3.0.0')]
    counts, bindings, timings = Counter(), [], []
    max_nll = 0.; max_portable_nll = 0.
    for job in jobs:
        raw = job['record']['raw_sha256']; turns, supps, route = evidence(job)
        decisions = [(t, x) for t in turns for x in t['decisions']]
        index = Path(job['manifest']['source']) / 'extracted' / raw / 'index.jsonl'
        roots = defaultdict(list)
        for line in index.open():
            t = json.loads(line)
            if t.get('record') == 'turn':
                for r in t['roots']: roots[t['actor']].append((r, t['round'], t['id']))
        for values in roots.values(): values.sort(key=lambda x:cursor(x[0]['event']))
        framepath = BASE.parent / 'v7/games' / raw / 'frames.jsonl.gz'
        with gzip.open(framepath, 'rt') as f:
            frames = {r['event']:r for r in map(json.loads, f)}
        prioritypath = BASE.parent / 'v8/priority' / raw / 'pre.jsonl.gz'
        with gzip.open(prioritypath, 'rt') as f:
            states = {r['event']:{k:r[k] for k in ('pre','actor','team','round','current','scheduled')}
                      for r in map(json.loads, f) if r['record'] == 'priority_pre'}
        streams = [s for s in d['sequences'] if job['offset'] <= s[0] < job['offset'] + job['rows']][:2]
        selected = set(int(i) for s in streams for i in s[:32])
        selected_events = {x['event_cursor'] for _, x in decisions}
        actors, portable_actors, providers, pointers = {}, {}, {}, Counter()
        for local, (t, decision) in enumerate(decisions):
            row = job['offset'] + local
            if row not in selected: continue
            actor = t['actor']; key = (raw, actor)
            if actor not in actors:
                actors[actor] = PolicyActor(model, key)
                portable_actors[actor] = PortableActor.load(WORK / f'exports/{identifier}', WORK / 'exports/P05', key)
                providers[actor] = PersonalInputs(load_proposal_predictor(actor).frozen, actor)
            policy, provider = actors[actor], providers[actor]
            while pointers[actor] < len(roots[actor]):
                r, rnd, ownturn = roots[actor][pointers[actor]]
                if cursor(r['event']) > cursor(decision['pre_cursor']): break
                f = frames.get(r['event'])
                provider.observe(r['event'], r['pre'], r['header']['step'], rnd, ownturn,
                                 f['observation'] if f else None,
                                 f['supplement'] if f else None, route)
                if r['event'] in selected_events: provider.mark_policy_action(r['event'])
                pointers[actor] += 1
            tick = time.perf_counter()
            bundle = provider.prepare(decision['observation'], supps[decision['id']], route,
                                      t['round'], t['id'], decision['pre_cursor'], states[decision['event_cursor']])
            command = policy.decide(**bundle, actor_key=key)
            portable = portable_actors[actor]
            values, phistory = provider.priority.memory.inputs(states[decision['event_cursor']], decision['pre_cursor'], t['round'])
            portable_command = portable.decide(
                {k:v.numpy() for k,v in bundle['inputs'].items()},
                {k:v.numpy() for k,v in bundle['geometry'].items()},
                values[None], phistory[None], actor_key=key)
            assert portable_command == command, (row, portable_command, command)
            timings.append((time.perf_counter() - tick) * 1000)
            family = rt.LABELS.index(command.action)
            assert family == int(predictions['prediction'][row]), (row, family, predictions['prediction'][row])
            if family in (1,2,3,5,6,8,12,13,14):
                assert policy.pending['coordinate'] == int(predictions['proposed_coordinate'][row]), row
            if family == 9: assert command.priority == int(predictions['priority'][row]), row
            # Replay evaluation only: previous actual recorded root is evidence
            # for the NEXT forecast, never a simulated execution of this one.
            target = targets(d, np.array([row]))
            target = {k:target[k] for k in ('y','py','priority_parameter_nll')}
            loss, post = model.observed(policy.pending['step'], **bundle['geometry'], **target)
            portable_loss, portable_post = portable.policy.observed(
                portable.pending['step'], **portable.pending['geometry'],
                **{k:v.numpy() for k,v in target.items()})
            max_portable_nll = max(max_portable_nll, abs(float(portable_loss[0]) - float(loss[0])))
            assert abs(float(portable_loss[0]) - float(loss[0])) < 2e-4
            discrepancy = abs(float(loss[0]) - float(predictions['nll'][row]))
            max_nll = max(max_nll, discrepancy)
            assert discrepancy < 2e-4, (row, discrepancy)
            policy.state = {k:v.detach() for k,v in post.items()}
            policy.pending = None
            portable.state = portable_post; portable.pending = None
            counts['cases'] += 1; counts['engine_' + job['record']['engine_version']] += 1
            counts['forecast_' + command.action] += 1
        bindings.append(dict(raw=raw, index_sha256=digest(index),
                             frames_sha256=digest(framepath), priority_sha256=digest(prioritypath)))
    immutable_json(REPORT / f'{identifier}-actor-roundtrip.json', dict(
        counts=dict(counts), bindings=bindings, max_nll_discrepancy=max_nll,
        max_portable_actor_nll_discrepancy=max_portable_nll,
        portable_actor_commands_exact=True,
        exact_semantic_commands=True, checkpoint_sha256=digest(path),
        actual_raw_PRE_inference_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95))),
        timing_scope='Current personal input construction, frozen M01/P05 distribution, Torch learned goal policy and all-family joint MAP PLUS independent portable actor/P05. Initialization, history replay, SDK dispatch excluded; combined verification cost, not production bot latency or a speed comparison.',
        qualification='First32 selected decisions of first2 actor streams per engine, forward from each first sampled decision with explicit unknown prefix. Cached/full benchmark retains every row separately. Replay teacher forcing and no actual engine execution; does not certify WASI, full legality or closed-loop strength.',
        source_sha256=digest(__file__), actor_sha256=digest(Path(__file__).with_name('actor.py')),
        personal_inputs_sha256=digest(Path(__file__).with_name('personal_inputs.py')),
        new_fits=0, reserved_opened=0))
    print(identifier, dict(counts), max_nll, flush=True)


if __name__ == '__main__': run(sys.argv[1])
