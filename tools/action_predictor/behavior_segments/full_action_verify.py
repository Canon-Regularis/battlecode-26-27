"""Parent verification: all row identities and scores, bounded fresh inference."""
import json
import time
import numpy as np
import torch
from . import full_action_evaluate as e
from ..audit import immutable_json
from ..data import action_name, digest
from ..rich_data import read_turns


def run():
    start = time.perf_counter(); plan = e.read(e.REPORT / 'plan.json')
    e.check(plan['sources']); e.check(plan['inputs'])
    receipt = e.read(e.REPORT / 'forecast.json'); e.check(receipt['bindings'])
    result = e.read(e.REPORT / 'result.json'); e.check(result['bindings'])
    records = e.read(e.WORK / 'forecasts.json')
    reproduced, arrays = e.calculate(records)
    for k, v in reproduced.items():
        if v != result[k]: raise ValueError('Result arithmetic differs: ' + k)
    with np.load(e.WORK / 'hybrid.npz') as saved:
        if set(saved.files) != set(arrays): raise ValueError('Array schema changed')
        for k, v in arrays.items():
            if not np.array_equal(v, saved[k]): raise ValueError('Decision array differs: ' + k)
    with np.load(e.TARGET) as raw:
        y, py, priority = raw['y'], raw['py'], raw['priority']
    verified = 0; spatial = 0; probability_rows = 0
    for job in plan['jobs']:
        route, selected, frames, actors = e.load_game(job)
        index = {r['event']: (roots, r) for turns in actors.values() for roots in turns for r in roots}
        for t in read_turns(job['manifest'], job['record']):
            for d in t['decisions']:
                i = selected[d['event_cursor']]; row = records[i]
                if row['event'] != d['event_cursor'] or row['actor'] != t['actor'] or row['round'] != t['round']:
                    raise ValueError('Canonical row identity differs')
                if e.LABELS[int(y[i])] != action_name(d['label']):
                    raise ValueError('Canonical command family differs')
                roots, root = index[row['event']]
                before = [r for r in roots if e.cursor(r['event']) < e.cursor(row['event'])]
                expected = not any(r['family'] not in e.ADMIN for r in before)
                if row['eligible'] != expected: raise ValueError('Eligibility uses the wrong chronology')
                position = d['observation']['own'].get('position')
                if 0 <= py[i] < 289:
                    target = d['label']['to']
                    actual = (target['y'] - position['y'] + 8) * 17 + target['x'] - position['x'] + 8
                    if int(py[i]) != actual: raise ValueError('Canonical coordinate differs')
                    spatial += 1
                if y[i] == 9 and int(priority[i]) != root['step']['priority']:
                    raise ValueError('Canonical integer differs')
                p = row['probabilities']
                if p is not None:
                    p = np.array(p)
                    if p.shape != (9,) or not np.isfinite(p).all() or (p < 0).any() or abs(p.sum() - 1) > 2e-6:
                        raise ValueError('Movement probabilities malformed')
                    from .model import OFFSETS
                    if list(OFFSETS[int(p.argmax())]) != row['movement']: raise ValueError('Movement mode differs')
                    allowed = {(0, 0)} | {(v['x'] - position['x'], v['y'] - position['y'])
                                           for v in frames[row['event']]['supplement']['movement']}
                    if any(p[k] != 0 for k, offset in enumerate(OFFSETS) if offset not in allowed):
                        raise ValueError('Movement probability outside PRE support')
                    probability_rows += 1
                verified += 1
        print('Verified canonical rows', verified, '/14439', flush=True)
    # Rerun the first game of each historical engine version without updates.
    torch.set_num_threads(1); predictor = e.TrajectoryMovementPredictor(); probes = []
    for version in sorted({j['record']['engine_version'] for j in plan['jobs']}):
        job = next(j for j in plan['jobs'] if j['record']['engine_version'] == version)
        actual = e.forecast_game(job, predictor)
        expected = e.read(e.WORK / (job['record']['raw_sha256'] + '.json'))
        # JSON normalization accounts only for tuple/list serialization.
        if json.loads(json.dumps(actual)) != expected: raise ValueError('Fresh streaming inference differs')
        probes.append(dict(engine=version, rows=len(actual['records']), actor_turns=actual['counts']['actor_turns']))
        print('Fresh inference reproduced', version, probes[-1], flush=True)
    e.check(plan['inputs'])
    immutable_json(e.REPORT / 'verification.json', dict(
        result_sha256=digest(e.REPORT / 'result.json'), forecast_sha256=digest(e.REPORT / 'forecast.json'),
        plan_sha256=digest(e.REPORT / 'plan.json'), verifier_sha256=digest(__file__),
        canonical_rows=verified, canonical_spatial_rows=spatial, supported_probability_rows=probability_rows,
        exact_metrics_and_decisions=True, fresh_inference=probes, weights_unchanged=True,
        optimizer_updates=0, subagents=False, seconds=time.perf_counter() - start))


if __name__ == '__main__': run()
