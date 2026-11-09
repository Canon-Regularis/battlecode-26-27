"""Availability-only alternative to a prefix cap; no model or label selection.

This proposes cached roots, not validated training examples. It leaves the
failed chronological-cap audit, partitions, budgets and feasibility gate intact.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
from ..audit import cursor, immutable_json
from ..data import digest
from ..rich_data import read_turns
from .audit import REPORT, BASE, eligible_jobs, window_counts


def complete_blocks(roots, available, horizon=32):
    """Nonoverlapping blocks anchored at each genuine available run's start."""
    block = []
    for ordinal, event, round_number in roots:
        if event not in available:
            block = []
            continue
        if block and ordinal != block[-1][0]+1: block = []
        block.append((ordinal, event, round_number))
        if len(block) == horizon:
            yield block
            block = []


def select_blocks(blocks, selected, budget):
    """Earliest blocks first; skip an over-budget block rather than cutting it."""
    extra = set(); retained = []
    for actor, block in sorted(blocks, key=lambda item: cursor(item[1][0][1])):
        addition = {event for _, event, _ in block} - selected - extra
        if len(extra) + len(addition) > budget: continue
        extra.update(addition)
        retained.append((actor, block))
    return extra, retained


def freeze():
    audit = REPORT/'cache-feasibility.json'
    plan = json.loads((REPORT/'cache-plan-r3.json').read_text())
    if json.loads(audit.read_text())['feasibility_gate_passed']:
        raise ValueError('This diagnostic addresses the failed prefix cap')
    immutable_json(REPORT/'window-inventory-plan.json', dict(source_sha256=digest(__file__),
        previous_audit_sha256=digest(audit), previous_plan_sha256=digest(REPORT/'cache-plan-r3.json'),
        jobs=plan['jobs'], feasibility=plan['feasibility'],
        rule='Same60games/group partitions/per-gamebudgets. All original selected roots retained. Enumerate nonoverlapping32root blocks from genuine available runs, then greedily include earliest blocks whose previously unselected roots fit the cap. No label, loss, destination, outcome or learned score consulted.',
        population='Enriches long available contexts, not natural action-cadence sampling. Any future study must disclose this and keep original DEV as secondary regression panel.',
        scope='Metadata topology/proposal only; uncapped cached labels not certified. No fitting, arrays, lowered threshold, additional games or reserved access.',
        new_fits=0, new_training_rows=0, reserved_opened=0))


def run():
    plan_path = REPORT/'window-inventory-plan.json'; plan = json.loads(plan_path.read_text())
    if digest(__file__) != plan['source_sha256']: raise ValueError('Frozen source changed')
    audit_path = REPORT/'cache-feasibility.json'
    if digest(audit_path) != plan['previous_audit_sha256']: raise ValueError('Audit changed')
    prior = {r['payload']: r for r in json.loads(audit_path.read_text())['games']}
    jobs = {j['record']['raw_sha256']: j for j in eligible_jobs()}
    results = []
    for selection in plan['jobs']:
        payload = selection['payload']; job = jobs[payload]; old = prior[payload]
        source = Path(job['manifest']['source'])/'extracted'/payload
        frame_path = BASE.parent/'v7/games'/payload/'frames.jsonl.gz'
        index_path = source/'index.jsonl'
        for p in (frame_path, index_path):
            if digest(p) != old['bindings'][str(p)]: raise ValueError('Bound cache/index changed')
        selected = {d['event_cursor'] for t in read_turns(job['manifest'], job['record']) for d in t['decisions']}
        available = set(selected)
        with gzip.open(frame_path, 'rt', encoding='utf-8') as f:
            for row in map(json.loads, f): available.add(row['event'])
        actors = defaultdict(list)
        with index_path.open(encoding='utf-8') as f:
            for turn in map(json.loads, f):
                if turn.get('record') != 'turn': continue
                actors[turn['actor']].extend((r['event'], turn['round']) for r in turn['roots'])
        roots = {actor: [(i, event, rnd) for i, (event, rnd) in enumerate(sorted(rows, key=lambda r: cursor(r[0])))]
                 for actor, rows in actors.items()}
        blocks = [(actor, block) for actor, rows in roots.items() for block in complete_blocks(rows, available)]
        extra, retained = select_blocks(blocks, selected, selection['max_extra_roots'])
        # Recompute the identical original gate's run-anchored metrics on the
        # resulting union, rather than equating proposed blocks with gate counts.
        keep = selected | extra; streams = []
        for rows in roots.values():
            stream = []
            for ordinal, event, rnd in rows:
                if event in keep: stream.append((ordinal, rnd))
                elif stream: streams.append(stream); stream = []
            if stream: streams.append(stream)
        result = dict(**selection, proposed_extra_roots=len(extra),
            uncapped_available_blocks32=len(blocks), selected_blocks32=len(retained),
            windows=window_counts(streams), proposed_extra_events=sorted(extra, key=cursor),
            source_bindings={str(p): old['bindings'][str(p)] for p in (frame_path, index_path)},
            label_validation_pending=True)
        immutable_json(REPORT/'window-proposals'/(payload+'.json'), result)
        results.append(result)
        print('Window inventory', len(results), '/', len(plan['jobs']), flush=True)
    totals = {}
    for split in ('fit', 'tuning', 'assessment'):
        subset = [r for r in results if r['partition'] == split]
        totals[split] = dict(proposed_extra_roots=sum(r['proposed_extra_roots'] for r in subset),
            uncapped_windows32=sum(r['uncapped_available_blocks32'] for r in subset),
            windows32=sum(r['windows']['32']['windows'] for r in subset),
            groups_with_windows32=sum(r['windows']['32']['windows'] > 0 for r in subset),
            across_rounds=sum(r['windows']['32']['across_rounds'] for r in subset))
    gate = (totals['fit']['windows32'] >= 1000 and totals['fit']['groups_with_windows32'] >= 30 and
            totals['assessment']['windows32'] >= 200 and totals['assessment']['groups_with_windows32'] >= 10)
    immutable_json(REPORT/'window-inventory.json', dict(plan_sha256=digest(plan_path), totals=totals,
        topology_gate_passed=gate, label_validation_pending=True, new_fits=0, new_training_rows=0,
        reserved_opened=0, interpretation='Availability-only gate. Does not authorize fitting or certify label/features for proposed extra roots.'))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['freeze', 'run'])
    (freeze if p.parse_args().command == 'freeze' else run)()
