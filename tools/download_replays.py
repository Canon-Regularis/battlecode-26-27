"""Bulk-download finished CAMBC matches for one team, across all maps or one map.

Run from any directory; requires the official CAMBC CLI and `cambc login`.
Uses only the Python standard library. See download_replays.md for examples.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from uuid import UUID
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class SharedCooldown:
    """One monotonic deadline shared by listing and download threads."""

    def __init__(self, clock=None, sleep=None):
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.lock = threading.Lock()
        self.deadline = 0.0

    def extend(self, seconds):
        with self.lock:
            self.deadline = max(self.deadline, self.clock() + seconds)

    def wait(self):
        while True:
            with self.lock:
                remaining = self.deadline - self.clock()
            if remaining <= 0:
                return
            # Release the lock while sleeping so other responses can extend the pause.
            self.sleep(remaining)


def find_cli(explicit=None):
    if explicit:
        candidate = shutil.which(explicit) or explicit
        if Path(candidate).is_file():
            return [str(Path(candidate).resolve())]
        raise ValueError(f"CAMBC executable not found: {explicit}")
    for candidate in (ROOT / '.venv/Scripts/cambc.exe', ROOT / '.venv/bin/cambc'):
        if candidate.is_file():
            return [str(candidate)]
    if executable := shutil.which('cambc'):
        return [executable]
    if executable := shutil.which('uv'):
        return [executable, 'run', '--locked', '--project', str(ROOT), 'cambc']
    raise ValueError('CAMBC not found. Run with `uv run --locked python tools/download_replays.py ...` '
                     'or pass --cli PATH_TO_CAMBC.')


def invoke(cli, *args, as_json=False, cooldown=None):
    cooldown = cooldown or SharedCooldown()
    for attempt in range(3):
        cooldown.wait()
        delay = 2 ** attempt
        try:
            result = subprocess.run([*cli, *map(str, args)], cwd=ROOT,
                                    capture_output=True, encoding='utf-8', timeout=180)
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise RuntimeError(f'CAMBC {args[0]} timed out') from None
        else:
            if result.returncode == 0:
                return json.loads(result.stdout) if as_json else result.stdout
            detail = result.stderr.strip() or result.stdout.strip()
            if retry_after := re.search(r'retry after (\d+(?:\.\d+)?) seconds', detail, re.IGNORECASE):
                delay = max(delay, float(retry_after[1]))
            rate_limited = bool(re.search(r'\b429\b|rate.?limit|too many requests', detail, re.IGNORECASE))
            if rate_limited:
                # Publish even the last attempt's limit response to other workers.
                delay = max(delay, 5) if not retry_after else delay
                cooldown.extend(delay)
                print(f'Rate limited: pausing new requests across all workers for {delay:g}s.',
                      file=sys.stderr, flush=True)
            if attempt == 2 or not (rate_limited or any(code in detail for code in ('502', '503', '504'))):
                hint = '\nRun `cambc login` to refresh your session.' if any(
                    word in detail.lower() for word in ('401', 'unauthorized', 'login', 'session expired')) else ''
                raise RuntimeError(f'CAMBC failed: {detail}{hint}')
            if rate_limited:
                continue  # The shared gate handles the delay before the next attempt.
        time.sleep(delay)


def map_name(value):
    name = value.replace('\\', '/').rsplit('/', 1)[-1]
    return name.removesuffix('.map26a').casefold()


def resolve_map(cli, selector, cooldown=None):
    try:
        return str(UUID(selector))
    except ValueError:
        pass
    page, seen, matches = 1, set(), []
    while page:
        if page in seen:
            raise RuntimeError('Map listing repeated a page; refusing an incomplete map lookup')
        seen.add(page)
        response = invoke(cli, 'maps', 'list', '--page', page, '--limit', 50, '--json',
                          as_json=True, cooldown=cooldown)
        matches.extend(m for m in response['maps'] if map_name(m['name']) == map_name(selector))
        page = response.get('nextPage')
    if len(matches) != 1:
        raise ValueError(f'Map {selector!r}: found {len(matches)} exact matches. '
                         'Use `cambc maps list --json` to find a platform map UUID.')
    return matches[0]['mapId']


def iter_matches(cli, team, map_id, kind, cooldown=None):
    cursor, seen_cursors, seen_matches = None, set(), set()
    while True:
        args = ['matches', 'list', '--team', team, '--limit', '50', '--json']
        if map_id is not None:
            args += ['--map', map_id]
        if kind != 'all':
            args += ['--kind', kind]
        if cursor:
            args += ['--cursor', cursor]
        response = invoke(cli, *args, as_json=True, cooldown=cooldown)
        for match in response['matches']:
            if match['matchId'] in seen_matches:
                continue
            seen_matches.add(match['matchId'])
            if match.get('status') == 'finished' and (map_id is None or match['mapId'] == map_id):
                yield match
        cursor = response.get('nextCursor')
        if not cursor:
            return
        if cursor in seen_cursors:
            raise RuntimeError('Match listing repeated a cursor; download may be incomplete')
        seen_cursors.add(cursor)


def valid_bundle(path):
    try:
        with zipfile.ZipFile(path) as archive:
            return (archive.getinfo('replay.repl26a').file_size > 0
                    and archive.testzip() is None)
    except (OSError, KeyError, zipfile.BadZipFile, EOFError):
        return False


def read_hashes(path):
    hashes = set()
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        value = line.split('#', 1)[0].strip().lower()
        if not value:
            continue
        if not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError(f'{path}:{number}: expected one SHA-256 hash per line')
        hashes.add(value)
    return frozenset(hashes)


def replay_hash(path):
    """Hash the raw replay payload, independent of ZIP metadata/compression."""
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as archive, archive.open('replay.repl26a') as payload:
        while chunk := payload.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DownloadResult:
    status: str
    replay_sha256: str | None = None


def download(cli, match_id, path, cooldown=None, exclude_hashes=frozenset(), known_hash=None):
    if valid_bundle(path):
        # Keep existing files, even when their hash is excluded.
        return DownloadResult('skipped', replay_hash(path))
    if known_hash in exclude_hashes:
        return DownloadResult('excluded', known_hash)
    temporary = path.with_suffix('.part')
    try:
        invoke(cli, 'matches', 'download', match_id, '-o', temporary, cooldown=cooldown)
        if not valid_bundle(temporary):
            raise ValueError(f'{match_id}: downloaded file is not a valid replay bundle')
        digest = replay_hash(temporary)
        if digest in exclude_hashes:
            return DownloadResult('excluded', digest)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return DownloadResult('downloaded', digest)


def write_manifest(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def selected_matches(path, team):
    """Read an explicit metadata-only selection across maps."""
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    records = value['matches'] if isinstance(value, dict) else value
    seen = set()
    for match in records:
        match_id = str(UUID(match['matchId']))
        if match_id in seen:
            raise ValueError(f'Duplicate match in selection: {match_id}')
        seen.add(match_id)
        if match.get('status') != 'finished':
            raise ValueError(f'Selection contains an unfinished match: {match_id}')
        if team == 'me' or not any(t['teamId'].casefold() == team.casefold()
                                   or t['name'].casefold() == team.casefold() for t in match['teams']):
            raise ValueError('Selections require an identified team present in every match')
        yield match


async def collect(args, cli, map_id, cooldown=None):
    cooldown = cooldown or SharedCooldown()
    # Only this coroutine updates the manifest. Download tasks operate on distinct files.
    out = args.out.resolve() if args.out else None
    manifest = dict(team=args.team, map_id=map_id, kind=args.kind, matches=[])
    failures = 0
    pending = {}
    excluded_hashes = getattr(args, 'excluded_hashes', frozenset())
    hash_index = None

    def report(index, record):
        match = record['metadata']
        print(f"{index}: {record['status']} {match['matchId']} {match['map']} {match['createdAt']}", flush=True)
        if record.get('error'):
            print(record['error'], file=sys.stderr)

    async def drain():
        nonlocal failures
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            index, record = pending.pop(task)
            try:
                result = task.result()
                record['status'] = result.status
                if result.replay_sha256:
                    record['replay_sha256'] = result.replay_sha256
                    hash_index[record['metadata']['matchId']] = result.replay_sha256
            except (RuntimeError, ValueError, OSError) as error:
                record.update(status='failed', error=str(error))
                failures += 1
            report(index, record)
        write_manifest(out / 'replay-hashes.json', hash_index)
        write_manifest(out / 'manifest.json', manifest)

    matches = iter(selected_matches(args.selection, args.team) if getattr(args, 'selection', None)
                   else iter_matches(cli, args.team, map_id, args.kind, cooldown=cooldown))
    try:
        while not args.limit or len(manifest['matches']) < args.limit:
            # Listing may perform network I/O; keep downloads running during pagination.
            match = await asyncio.to_thread(next, matches, None)
            if match is None:
                break
            match_id = str(UUID(match['matchId']))
            if out is None:
                team = next(t for t in match['teams'] if args.team == 'me'
                            or t['teamId'].casefold() == args.team.casefold()
                            or t['name'].casefold() == args.team.casefold())
                team_dir = 'me' if args.team == 'me' else str(UUID(team['teamId']))
                out = ROOT / 'replays/downloads' / team_dir / (map_id or 'all-maps')
            if hash_index is None:
                index_path = out / 'replay-hashes.json'
                hash_index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
                if not isinstance(hash_index, dict) or any(
                    not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                    for value in hash_index.values()
                ):
                    raise ValueError(f'Invalid replay hash index: {index_path}')
            record = dict(metadata=match, file=f'{match_id}.repl26a', status='pending')
            manifest['matches'].append(record)
            index = len(manifest['matches'])
            if args.dry_run:
                record['status'] = 'excluded' if hash_index.get(match_id) in excluded_hashes else 'dry-run'
                report(index, record)
            else:
                out.mkdir(parents=True, exist_ok=True)
                task = asyncio.create_task(asyncio.to_thread(download, cli, match_id, out / record['file'],
                                                             cooldown=cooldown, exclude_hashes=excluded_hashes,
                                                             known_hash=hash_index.get(match_id)))
                pending[task] = (index, record)
                if len(pending) >= args.workers:
                    await drain()
    finally:
        # Persist completed downloads even if a later listing page fails.
        while pending:
            await drain()
    print(f"Matched {len(manifest['matches'])} finished games; {failures} failed."
          + (f' Output: {out}' if out and not args.dry_run else ''))
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team', required=True, help='Full team name, team UUID, or me')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--map', help='Platform map name (e.g. 00ambush) or UUID')
    selection.add_argument('--all-maps', action='store_true', help='Download across all maps (default)')
    selection.add_argument('--selection', type=Path, help='Frozen finished-match metadata JSON, across maps')
    parser.add_argument('--kind', choices=['ranked', 'unranked', 'tournament', 'all'], default='ranked')
    parser.add_argument('--limit', type=int, default=0, help='Maximum matching games; 0 downloads all (default)')
    parser.add_argument('--out', type=Path, help='Output directory; default: replays/downloads/TEAM/MAP_OR_all-maps')
    parser.add_argument('--dry-run', action='store_true', help='List matching games without writing files')
    parser.add_argument('--cli', help='Path to the official cambc executable')
    parser.add_argument('--workers', type=int, default=4, help='Concurrent downloads (default: 4)')
    parser.add_argument('--exclude-hashes', type=Path,
                        help='Text file of raw replay SHA-256 hashes to exclude (one per line)')
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error('--limit must be >= 0')
    if args.workers < 1:
        parser.error('--workers must be >= 1')
    if args.selection and not args.out:
        parser.error('--selection requires --out')
    try:
        args.excluded_hashes = read_hashes(args.exclude_hashes) if args.exclude_hashes else frozenset()
        cli = find_cli(args.cli)
        cooldown = SharedCooldown()
        map_id = resolve_map(cli, args.map, cooldown=cooldown) if args.map else None
        return asyncio.run(collect(args, cli, map_id, cooldown=cooldown))
    except (RuntimeError, ValueError, OSError, StopIteration) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
