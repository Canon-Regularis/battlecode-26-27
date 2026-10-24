"""Run optimizer unit tests in isolated module processes with live progress.

Examples:
    uv run python -m tools.bot_optimizer.test_runner --jobs 3
    uv run python -m tools.bot_optimizer.test_runner test_cancelled_products test_runtime

Each unique unittest ID runs once. Tests from one module stay together to retain
module/class fixture semantics. This runner does not launch Wasm benchmarks.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'tools.bot_optimizer.tests.'


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


class ProgressResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.stream.writeln(f'START {test.id()}')
        self.stream.flush()

    def stopTest(self, test):
        self.stream.writeln(f'DONE  {test.id()} ({time.monotonic()-self.started:.2f}s)')
        self.stream.flush()
        super().stopTest(test)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tests', nargs='*', help='Module, class or test selectors; short test_* module names are accepted')
    parser.add_argument('--jobs', type=int, default=min(3, os.process_cpu_count() or 1))
    parser.add_argument('--output', type=Path, help='New directory for per-module logs and results.json')
    parser.add_argument('--list', action='store_true', help='Show selected modules/counts without running tests')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    loader = unittest.TestLoader()
    if args.tests:
        names = [PREFIX+name if name.startswith('test_') else name for name in args.tests]
        suite = loader.loadTestsFromNames(names)
    else:
        suite = loader.discover(str(ROOT/'tools/bot_optimizer/tests'), top_level_dir=str(ROOT))
    if loader.errors:
        parser.error('\n'.join(loader.errors))
    if args.worker:
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0, resultclass=ProgressResult).run(suite)
        return 0 if result.wasSuccessful() else 1
    cases = list(flatten(suite))
    unique = {test.id(): test for test in cases}
    if not unique:
        parser.error('No tests selected')
    groups = {}
    for name, test in unique.items():
        groups.setdefault(test.__class__.__module__, []).append(name)
    print(f'{len(unique)} unique tests in {len(groups)} modules; '
          f'{len(cases)-len(unique)} duplicate discoveries removed; '
          f'{min(args.jobs, len(groups))} workers.', flush=True)
    if args.list:
        for module, names in sorted(groups.items()):
            print(f'{module}: {len(names)} tests')
        return 0
    output = args.output or ROOT/'replays/optimizer-tests'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+f'-{os.getpid()}')
    output.mkdir(parents=True, exist_ok=False)
    print(f'Logs: {output}', flush=True)
    lock = threading.Lock()
    def emit(text):
        with lock:
            print(text, flush=True)
    def run(module, names):
        label = module.removeprefix(PREFIX)
        log = output/(module+'.log')
        start = time.monotonic()
        command = [sys.executable, '-u', '-m', 'tools.bot_optimizer.test_runner', '--worker', *names]
        with log.open('w') as stream:
            with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True) as process:
                for line in process.stdout:
                    stream.write(line)
                    stream.flush()
                    emit(f'[{label}] {line.rstrip()}')
                code = process.wait()
        return dict(module=module, tests=names, returncode=code,
                    elapsed_seconds=time.monotonic()-start, log=str(log))
    started = time.monotonic()
    results = []
    # Larger modules first reduces the tail when task sizes are comparable.
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(run, module, names)
                   for module, names in sorted(groups.items(), key=lambda pair: -len(pair[1]))]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            emit(f'Completed {len(results)}/{len(groups)} modules: {row["module"]} '
                 f'({row["elapsed_seconds"]:.1f}s, exit {row["returncode"]})')
    failed = [row['module'] for row in results if row['returncode']]
    report = dict(status='failed' if failed else 'passed', tests=len(unique), modules=len(groups),
                  duplicate_discoveries=len(cases)-len(unique), jobs=min(args.jobs, len(groups)),
                  elapsed_seconds=time.monotonic()-started, failed_modules=failed,
                  results=sorted(results, key=lambda row: row['module']))
    (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'{report["status"].upper()}: {len(unique)} tests, '
          f'{report["elapsed_seconds"]:.1f}s. Results: {output/"results.json"}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
