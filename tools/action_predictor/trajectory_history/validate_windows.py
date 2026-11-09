"""Validate the frozen availability-only proposal; never assembles fit arrays."""
import argparse
import json
from pathlib import Path
import numpy as np
from ..audit import immutable_json
from ..data import digest
from .audit import REPORT, BASE, eligible_jobs, audit_game


def sources():
    return {str(p): digest(p) for p in (Path(__file__), Path(__file__).with_name('audit.py'),
        Path(__file__).with_name('window_inventory.py'), Path(__file__).with_name('test_audit.py'),
        Path(__file__).with_name('test_windows.py'))}


def freeze():
    inventory = REPORT/'window-inventory.json'
    if not json.loads(inventory.read_text())['topology_gate_passed']:
        raise ValueError('Insufficient proposed windows')
    plan = REPORT/'window-inventory-plan.json'
    inputs = {str(p): digest(p) for p in (inventory, plan)}
    for selection in json.loads(plan.read_text())['jobs']:
        p = REPORT/'window-proposals'/(selection['payload']+'.json')
        inputs[str(p)] = digest(p)
        inputs.update(json.loads(p.read_text())['source_bindings'])
    immutable_json(REPORT/'window-validation-plan.json', dict(inputs=inputs, sources=sources(),
        scope='Same frozen proposed roots, partitions and budgets. Validate command/PRE/selected-label parity on all proposed roots, retain actual missing-root gaps. No model fitting or training arrays.',
        reference_audit_source_commit='b3a5be1',
        new_fits=0, new_training_rows=0, reserved_opened=0))


def run():
    path = REPORT/'window-validation-plan.json'; plan = json.loads(path.read_text())
    if sources() != plan['sources']: raise ValueError('Validation sources changed')
    for name, expected in plan['inputs'].items():
        if digest(name) != expected: raise ValueError('Frozen proposal input changed: '+name)
    selections = json.loads((REPORT/'window-inventory-plan.json').read_text())['jobs']
    jobs = {j['record']['raw_sha256']: j for j in eligible_jobs()}
    canonical = BASE/'combined-train.npz'
    canonical_hash = '39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb'
    if digest(canonical) != canonical_hash: raise ValueError('Canonical TRAIN changed')
    with np.load(canonical) as z: priorities = z['priority']
    results = []
    for selection in selections:
        payload = selection['payload']
        proposal = json.loads((REPORT/'window-proposals'/(payload+'.json')).read_text())
        result = audit_game(jobs[payload], selection, priorities, proposal['proposed_extra_events'])
        result['bindings'][str(canonical)] = canonical_hash
        if result['windows'] != proposal['windows'] or result['counts'].get('extra_roots', 0) != proposal['proposed_extra_roots']:
            raise ValueError('Validated label set fails proposed topology')
        immutable_json(REPORT/'validated-windows'/(payload+'.json'), result)
        results.append(result)
        print('Validated window labels', len(results), '/', len(selections), flush=True)
    immutable_json(REPORT/'window-validation.json', dict(plan_sha256=digest(path),
        all_proposed_root_labels_checked=True, topology_reproduced=True, games=results,
        validated_extra_roots=sum(r['counts'].get('extra_roots', 0) for r in results),
        new_training_rows=0, new_fits=0, reserved_opened=0,
        next='Independent review before feature assembly. Need current-observation and prior-command/history feature parity, fit-only preprocessing/components, and frozen matched horizon protocol before optimization.',
        limitations='Recorded-command/observation binding only. No new POST validation, full legality, resolved entity targets or purchase arguments. This is not untouched-test evidence or strategic benefit.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['freeze', 'run'])
    (freeze if p.parse_args().command == 'freeze' else run)()
