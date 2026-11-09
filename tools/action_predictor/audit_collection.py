"""Check the additional-data freeze using metadata and payload hashes only."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from .more_replays import ROOT, WORK, REPORTS, frozen, payloads, sha


def run():
    membership = json.loads((REPORTS / 'membership.json').read_text())
    original = json.loads((ROOT / '.cambc/action-predictor/data/dataset.json').read_text())
    existing = json.loads((WORK / 'existing-refresh.json').read_text())
    old_hashes = {r['sha256'] for r in existing['entries']}
    records = membership['records']
    groups = defaultdict(list)
    hashes = set()
    for record in records:
        groups[record['group']].append(record)
        path = Path(record['path'])
        assert sha(path) == record['bundle_sha256'], 'Frozen bundle changed'
        rows, errors = payloads(path)
        assert not errors and len(rows) == 1
        raw = rows[0]['sha256']
        assert raw == record['raw_sha256']
        assert raw not in hashes and raw not in old_hashes, 'Duplicate replay payload'
        hashes.add(raw)
    assert len(records) == len(hashes) == 500 and len(groups) == 100
    assert not set(groups).intersection(r['group'] for r in original['recordings'])
    for group in groups.values():
        assert len(group) == 5
        assert {r['metadata']['position'] for r in group} == {1, 2, 3, 4, 5}
        assert len({r['split'] for r in group}) == 1
    assert membership['inspected_behaviour'] is False
    frozen(REPORTS / 'collection-audit.json', dict(
        membership_sha256=sha(REPORTS / 'membership.json'),
        refreshed_inventory_sha256=sha(WORK / 'existing-refresh.json'),
        unique_new_payloads=500, complete_groups=100,
        old_payload_overlap=0, old_group_overlap=0, cross_split_payload_overlap=0,
        split_counts=dict(Counter(r['split'] for r in records)),
        all_five_positions_retained=True, whole_group_membership=True,
        audit_reads='Metadata, archive integrity and raw payload hashes only.',
        rejected_groups=len(membership['rejected_groups']),
        rejection_reasons=dict(Counter(g['reason'] for g in membership['rejected_groups'])),
    ))
    # This file can be passed directly to the downloader's new --exclude-hashes.
    # Collection was already complete when the option was checked; do not imply
    # that it saved requests in these batches.
    excluded = WORK / 'existing-payload-hashes.txt'
    content = ''.join(h + '\n' for h in sorted(old_hashes))
    if excluded.exists() and excluded.read_text() != content:
        raise ValueError('Frozen exclusion list changed')
    excluded.write_text(content, encoding='utf-8')
    frozen(REPORTS / 'hash-exclusion-review.json', dict(
        option='--exclude-hashes', file=str(excluded.resolve()),
        sha256=sha(excluded), hashes=len(old_hashes), downloader_tests_passed=19,
        network_skip='Only when match-to-payload hash is already indexed.',
        unknown_hash='Downloaded temporarily, hashed, then discarded if excluded.',
        existing_file='Valid cached bundles are preserved even if excluded.',
        used_in_completed_collection=False,
        reason='Final batch completed while the new option was being checked; whole-group raw-payload deduplication was already enforced.',
    ))
    all_known = set(old_hashes)
    for index in (WORK / 'collection').glob('batch-*/replay-hashes.json'):
        all_known.update(json.loads(index.read_text()).values())
    all_known.update(hashes)
    export = WORK / 'all-known-payload-hashes.txt'
    content = ''.join(h + '\n' for h in sorted(all_known))
    if export.exists() and export.read_text() != content:
        raise ValueError('Frozen all-known exclusion list changed')
    export.write_text(content, encoding='utf-8')
    frozen(REPORTS / 'hash-exclusion-export.json', dict(
        file=str(export.resolve()), sha256=sha(export), hashes=len(all_known),
        includes='Pre-existing corpus and every indexed downloaded payload, including rejected groups.',
        option='--exclude-hashes', requires_whole_group_selection=True,
    ))
    print('Collection audit passed: 500 new payloads, 100 whole groups, zero overlap.')


if __name__ == '__main__':
    run()
