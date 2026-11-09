"""Offline tests: python -m unittest discover -s tools -p test_download_replays.py"""
import contextlib
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
import zipfile

import download_replays as downloader

MAP = '1efbe907-7c38-4e98-9d3b-0df7d68d2861'
MATCH = '01a1b172-0001-71d6-aec1-e0dc92bcf385'


def bundle(path):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('replay.repl26a', b'replay payload')


class DownloadTests(unittest.TestCase):
    def test_hash_file_accepts_bom_comments_and_uppercase_but_rejects_bad_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hashes.txt'
            path.write_text('\ufeff# Already collected\n' + 'AB' * 32 + '\n\n', encoding='utf-8')
            self.assertEqual(downloader.read_hashes(path), {'ab' * 32})
            path.write_text('not-a-hash\n')
            with self.assertRaisesRegex(ValueError, 'expected one SHA-256'):
                downloader.read_hashes(path)

    def test_payload_hash_ignores_zip_container_differences(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = [Path(directory) / name for name in ('one.zip', 'two.zip')]
            bundle(first)
            with zipfile.ZipFile(second, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.comment = b'different metadata'
                archive.writestr('replay.repl26a', b'replay payload')
            self.assertNotEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(downloader.replay_hash(first), downloader.replay_hash(second))

    def test_exclusions_discard_unseen_payload_then_skip_network_on_rerun(self):
        duplicate_hash = hashlib.sha256(b'replay payload').hexdigest()
        matches = [dict(matchId=f'01a1b172-0001-71d6-aec1-e0dc92bcf38{i}', map='00ambush',
                        createdAt='2026-11-06') for i in range(2)]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'replays'
            hashes = Path(directory) / 'hashes.txt'
            hashes.write_text(duplicate_hash + '\n')
            flags = ['--team', 'Team', '--map', MAP, '--out', str(out), '--exclude-hashes', str(hashes)]

            def fake_invoke(*args, **kwargs):
                with zipfile.ZipFile(Path(args[-1]), 'w') as archive:
                    payload = b'replay payload' if args[3] == matches[0]['matchId'] else b'new replay'
                    archive.writestr('replay.repl26a', payload)

            for run in range(2):
                with patch.object(downloader, 'find_cli', return_value=['cli']), \
                     patch.object(downloader, 'iter_matches', return_value=iter(matches)), \
                     patch.object(downloader, 'invoke', side_effect=fake_invoke) as invoke, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(downloader.main(flags), 0)
                self.assertEqual(invoke.call_count, 2 if run == 0 else 0)
                manifest = json.loads((out / 'manifest.json').read_text())
                self.assertEqual([r['status'] for r in manifest['matches']],
                                 ['excluded', 'downloaded' if run == 0 else 'skipped'])
                self.assertEqual(manifest['matches'][0]['replay_sha256'], duplicate_hash)
                self.assertEqual(len(list(out.glob('*.repl26a'))), 1)
                self.assertEqual(list(out.glob('*.part')), [])
            index = json.loads((out / 'replay-hashes.json').read_text())
            self.assertEqual(index[matches[0]['matchId']], duplicate_hash)
            self.assertEqual(index[matches[1]['matchId']], hashlib.sha256(b'new replay').hexdigest())

    def test_known_exclusion_and_existing_files_do_not_download(self):
        digest = hashlib.sha256(b'replay payload').hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.repl26a'
            with patch.object(downloader, 'invoke') as invoke:
                result = downloader.download(['cli'], MATCH, path, exclude_hashes={digest}, known_hash=digest)
                self.assertEqual(result.status, 'excluded')
                self.assertFalse(path.exists())
                bundle(path)
                original = path.read_bytes()
                result = downloader.download(['cli'], MATCH, path, exclude_hashes={digest})
                self.assertEqual(result.status, 'skipped')
                self.assertEqual(path.read_bytes(), original)
                invoke.assert_not_called()

    def test_all_maps_paginate_without_map_filter_and_keep_finished_games(self):
        first = dict(matchId=MATCH, status='finished', mapId=MAP)
        second = dict(first, matchId='01a1b172-0001-71d6-aec1-e0dc92bcf386', mapId='other-map')
        with patch.object(downloader, 'invoke', side_effect=[
            {'matches': [first, dict(first, matchId='running', status='running')], 'nextCursor': 'next'},
            {'matches': [first, second], 'nextCursor': None},
        ]) as invoke:
            self.assertEqual(list(downloader.iter_matches(['cli'], 'Team', None, 'ranked')), [first, second])
            for call in invoke.call_args_list:
                self.assertNotIn('--map', call.args)
                self.assertIn('--team', call.args)
                self.assertIn('--kind', call.args)

    def test_all_maps_cli_defaults_output_and_total_limit(self):
        team_id = '1890540d-1ffc-4847-adbf-d0d08772f268'
        matches = [dict(matchId=f'01a1b172-0001-71d6-aec1-e0dc92bcf38{i}', map=name,
                        mapId=map_id, createdAt='2026-11-06', status='finished',
                        teams=[dict(teamId=team_id, name='Team')])
                   for i, (name, map_id) in enumerate([('00ambush', MAP), ('00anvil', 'other-map')])]
        for flags in ([], ['--all-maps']):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as directory:
                with patch.object(downloader, 'ROOT', Path(directory)), \
                     patch.object(downloader, 'find_cli', return_value=['cli']), \
                     patch.object(downloader, 'resolve_map') as resolve_map, \
                     patch.object(downloader, 'invoke', return_value={'matches': matches, 'nextCursor': None}), \
                     patch.object(downloader, 'download', return_value=downloader.DownloadResult('downloaded')) as download, \
                     contextlib.redirect_stdout(io.StringIO()):
                    result = downloader.main(['--team', 'Team', '--limit', '2', *flags])
                self.assertEqual(result, 0)
                resolve_map.assert_not_called()
                self.assertEqual(download.call_count, 2)
                out = Path(directory) / 'replays/downloads' / team_id / 'all-maps'
                manifest = json.loads((out / 'manifest.json').read_text())
                self.assertIsNone(manifest['map_id'])
                self.assertEqual([r['metadata']['map'] for r in manifest['matches']], ['00ambush', '00anvil'])

    def test_cooldown_never_shortens_and_rechecks_extensions(self):
        now, waits = [0.0], []

        def sleep(seconds):
            waits.append(seconds)
            now[0] += seconds
            if len(waits) == 1:
                cooldown.extend(3)

        cooldown = downloader.SharedCooldown(clock=lambda: now[0], sleep=sleep)
        cooldown.extend(10)
        cooldown.extend(2)
        cooldown.wait()
        self.assertEqual(waits, [10, 3])
        self.assertEqual(now[0], 13)

    def test_rate_limit_blocks_other_workers_before_cli_launch(self):
        release = threading.Event()
        first_waiting, both_waiting = threading.Event(), threading.Event()
        lock = threading.Lock()
        calls, sleepers = 0, 0

        def sleep(seconds):
            nonlocal sleepers
            with lock:
                sleepers += 1
                first_waiting.set()
                if sleepers == 2:
                    both_waiting.set()
            if not release.wait(5):
                raise AssertionError('Cooldown was not released')

        cooldown = downloader.SharedCooldown(clock=lambda: 10 if release.is_set() else 0, sleep=sleep)

        def run(*args, **kwargs):
            nonlocal calls
            with lock:
                calls += 1
                count = calls
            if count == 1:
                return SimpleNamespace(returncode=1, stderr='HTTP 429; retry after 5 seconds', stdout='')
            return SimpleNamespace(returncode=0, stdout='ok')

        with patch.object(downloader.subprocess, 'run', side_effect=run), \
             contextlib.redirect_stderr(io.StringIO()), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(downloader.invoke, ['cli'], 'matches', cooldown=cooldown)
            try:
                self.assertTrue(first_waiting.wait(5))
                second = pool.submit(downloader.invoke, ['cli'], 'maps', cooldown=cooldown)
                self.assertTrue(both_waiting.wait(5))
                self.assertEqual(calls, 1)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5), 'ok')
            self.assertEqual(second.result(timeout=5), 'ok')
            self.assertEqual(calls, 3)

    def test_last_rate_limit_attempt_still_pauses_other_requests(self):
        now, waits = [0.0], []

        def sleep(seconds):
            waits.append(seconds)
            now[0] += seconds

        cooldown = downloader.SharedCooldown(clock=lambda: now[0], sleep=sleep)
        error = SimpleNamespace(returncode=1, stderr='HTTP 429; retry after 7 seconds', stdout='')
        success = SimpleNamespace(returncode=0, stdout='ok')
        with patch.object(downloader.subprocess, 'run', side_effect=[error, error, error, success]), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError):
                downloader.invoke(['cli'], 'matches', cooldown=cooldown)
            self.assertEqual(downloader.invoke(['cli'], 'maps', cooldown=cooldown), 'ok')
        self.assertEqual(waits, [7, 7, 7])

    def test_concurrent_downloads_are_bounded_and_failures_are_recorded(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        active, maximum = 0, 0
        matches = [dict(matchId=f'01a1b172-0001-71d6-aec1-e0dc92bcf38{i}',
                        map='00ambush', createdAt='2026-11-06') for i in range(4)]

        def fake_download(cli, match_id, path, cooldown=None, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                # A sequential implementation cannot pass this rendezvous.
                barrier.wait(timeout=5)
                if match_id == matches[0]['matchId']:
                    raise RuntimeError('test failure')
                bundle(path)
                return downloader.DownloadResult('downloaded', downloader.replay_hash(path))
            finally:
                with lock:
                    active -= 1

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(downloader, 'find_cli', return_value=['cli']), \
                 patch.object(downloader, 'iter_matches', return_value=iter(matches)), \
                 patch.object(downloader, 'download', side_effect=fake_download), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                result = downloader.main(['--team', 'Team', '--map', MAP, '--out', directory,
                                          '--workers', '2'])
            manifest = json.loads((Path(directory) / 'manifest.json').read_text())
            self.assertEqual(result, 1)
            self.assertEqual(maximum, 2)
            self.assertEqual([r['metadata'] for r in manifest['matches']], matches)
            self.assertEqual([r['status'] for r in manifest['matches']],
                             ['failed', 'downloaded', 'downloaded', 'downloaded'])
            self.assertEqual(len(list(Path(directory).glob('*.repl26a'))), 3)

    def test_listing_failure_drains_downloads_and_saves_manifest(self):
        def matches():
            yield dict(matchId=MATCH, map='00ambush', createdAt='2026-11-06')
            raise RuntimeError('page unavailable')

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(downloader, 'find_cli', return_value=['cli']), \
                 patch.object(downloader, 'iter_matches', return_value=matches()), \
                 patch.object(downloader, 'download', return_value=downloader.DownloadResult('downloaded')), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                result = downloader.main(['--team', 'Team', '--map', MAP, '--out', directory])
            self.assertEqual(result, 1)
            manifest = json.loads((Path(directory) / 'manifest.json').read_text())
            self.assertEqual(manifest['matches'][0]['status'], 'downloaded')

    def test_map_lookup_paginates_and_accepts_filename(self):
        with patch.object(downloader, 'invoke', side_effect=[
            {'maps': [], 'nextPage': 2},
            {'maps': [{'name': '00ambush', 'mapId': MAP}], 'nextPage': None},
        ]) as invoke:
            self.assertEqual(downloader.resolve_map(['cli'], '00ambush.map26a'), MAP)
            self.assertEqual(invoke.call_args.args[4], 2)

    def test_uuid_needs_no_map_lookup(self):
        with patch.object(downloader, 'invoke') as invoke:
            self.assertEqual(downloader.resolve_map(['cli'], MAP), MAP)
            invoke.assert_not_called()

    def test_matches_paginate_deduplicate_and_filter(self):
        match = dict(matchId=MATCH, status='finished', mapId=MAP)
        with patch.object(downloader, 'invoke', side_effect=[
            {'matches': [match, dict(match, matchId='unfinished', status='running')], 'nextCursor': 'next'},
            {'matches': [match, dict(match, matchId='wrong-map', mapId='other')], 'nextCursor': None},
        ]) as invoke:
            self.assertEqual(list(downloader.iter_matches(['cli'], 'Team', MAP, 'ranked')), [match])
            self.assertIn('next', invoke.call_args.args)
            self.assertIn('--map', invoke.call_args.args)

    def test_repeated_cursor_fails_instead_of_looping(self):
        with patch.object(downloader, 'invoke', return_value={'matches': [], 'nextCursor': 'same'}):
            with self.assertRaisesRegex(RuntimeError, 'repeated a cursor'):
                list(downloader.iter_matches(['cli'], 'Team', MAP, 'all'))

    def test_download_resume_and_corrupt_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'match.repl26a'
            path.write_bytes(b'broken')
            def fake_invoke(*args, **kwargs):
                bundle(Path(args[-1]))
            with patch.object(downloader, 'invoke', side_effect=fake_invoke) as invoke:
                self.assertEqual(downloader.download(['cli'], MATCH, path).status, 'downloaded')
                self.assertEqual(downloader.download(['cli'], MATCH, path).status, 'skipped')
                self.assertEqual(invoke.call_count, 1)
            self.assertFalse(path.with_suffix('.part').exists())

    def test_failed_download_preserves_existing_file_and_cleans_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'match.repl26a'
            path.write_bytes(b'previous')
            def fake_invoke(*args, **kwargs):
                Path(args[-1]).write_bytes(b'invalid response')
            with patch.object(downloader, 'invoke', side_effect=fake_invoke):
                with self.assertRaises(ValueError):
                    downloader.download(['cli'], MATCH, path)
            self.assertEqual(path.read_bytes(), b'previous')
            self.assertFalse(path.with_suffix('.part').exists())

    def test_limit_and_dry_run_create_no_files(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'output'
            match = dict(matchId=MATCH, map='00ambush', createdAt='2026-11-06')
            with patch.object(downloader, 'find_cli', return_value=['cli']), \
                 patch.object(downloader, 'iter_matches', return_value=iter([match, match])), \
                 patch.object(downloader, 'download') as download, \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                result = downloader.main(['--team', 'Team', '--map', MAP, '--out', str(out),
                                          '--limit', '1', '--dry-run'])
            self.assertEqual(result, 0)
            self.assertIn('Matched 1 finished games', stdout.getvalue())
            self.assertFalse(out.exists())
            download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
