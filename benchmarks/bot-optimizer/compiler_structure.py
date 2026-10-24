"""Measure a single-pass name collector without changing emitted bot sources."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import optimize_folder
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.analysis import Bindings


def previous_names(tree):
    """Pre-refactor collector, retained only as the benchmark baseline."""
    result = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    result.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
    result.update(n.name for n in ast.walk(tree)
                  if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
    result.update(a.asname or a.name for n in ast.walk(tree)
                  if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names)
    result.update(Bindings(tree.body).counts)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.update(Bindings(node.body).counts)
    return result


def manifest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*.py'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    holders = [module for name, module in sys.modules.items()
               if name.startswith('tools.bot_optimizer') and getattr(module, 'used_names', None) is used_names]
    timings = {'baseline': [], 'candidate': []}
    expected = None
    for repeat in range(3):
        for mode in (('baseline', 'candidate') if repeat % 2 == 0 else ('candidate', 'baseline')):
            for module in holders:
                module.used_names = previous_names if mode == 'baseline' else used_names
            output = args.output / f'{mode}-{repeat}'
            start = time.perf_counter()
            optimize_folder(args.bot, output)
            timings[mode].append(time.perf_counter() - start)
            actual = manifest(output)
            if expected is None:
                expected = actual
            assert actual == expected, 'Generated Python sources differ'
    report = {'status': 'complete', 'seconds': timings, 'python_source_sha256': expected,
              'sources_identical': True, 'guest_fuel_measurement': False,
              'median_speedup': statistics.median(timings['baseline']) / statistics.median(timings['candidate'])}
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'python_source_sha256'}, indent=2))


if __name__ == '__main__':
    main()
