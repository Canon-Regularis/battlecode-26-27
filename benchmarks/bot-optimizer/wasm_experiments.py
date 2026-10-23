"""Competing source kernels motivated by inspected CPython Wasm paths.

Manual candidates only. Guards, record allocation and per-call setup are charged.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.runtime import executable, run_command


def sources():
    old, new, cases = [], [], []
    for width in (4, 8, 12, 20):
        for strategy in ('cached', 'unpack', 'literal_update'):
            name = f'large_{width}_{strategy}'
            cls = f'Row_{name}'
            fields = [f'f{i}' for i in range(width)]
            definition = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass ' + cls + ':\n'
            definition += ''.join(f'    {f}: object\n' for f in fields)
            definition = optimize_source(definition).source
            factory = f'NEW_{cls} = object.__new__\ndef make_{cls}(_cls, {", ".join(fields)}):\n'
            factory += f'    row = NEW_{cls}(_cls)\n    d = row.__dict__\n'
            if strategy == 'cached':
                factory += ''.join(f'    d[{f!r}] = {f}\n' for f in fields)
            elif strategy == 'unpack':
                factory += '    ' + ', '.join(f'd[{f!r}]' for f in fields) + ' = ' + ', '.join(fields) + '\n'
            else:
                factory += '    d.update({' + ', '.join(f'{f!r}: {f}' for f in fields) + '})\n'
            factory += '    return row\n'
            args = ', '.join(str(i) for i in range(width))
            body = f'def {name}():\n    row = {{constructor}}({args})\n    return row.f0 + row.f{width-1}\n'
            old.append(definition + body.format(constructor=cls))
            new.append(definition + factory + body.format(constructor=f'make_{cls}').replace(
                f'make_{cls}({args})', f'make_{cls}({cls}, {args})'))
            cases.append(name)
    setup = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Entry:
    a: int
    b: int
    c: int
ROWS = tuple(Entry(i, i+1, i+2) for i in range(32))
def safe(rows, route):
    if not (type(rows) is list or type(rows) is tuple) or type(route) is not tuple or len(route) > 4096:
        return False
    size = len(rows)
    for i in route:
        if type(i) is not int or not -size <= i < size:
            return False
        row = rows[i]
        if type(row) is not Entry or type(row.a) is not int or type(row.b) is not int or type(row.c) is not int:
            return False
    return True
'''
    old.append(setup)
    new.append(setup)
    for size in (0, 1, 4, 8, 32):
        for setup_included in (False, True):
            for strategy in ('guarded_eager', 'guarded_fused', 'unguarded_eager'):
                name = f'reductions_{size}_{int(setup_included)}_{strategy}'
                prepare = (f'    rows = tuple(Entry(i, i+1, i+2) for i in range({size}))\n'
                           if setup_included else '    rows = ROWS\n')
                prepare += f'    route = tuple(range({size}))\n'
                expression = '    return sum(rows[i].a for i in route), sum(rows[i].b for i in route), sum(rows[i].c for i in route)\n'
                old.append(f'def {name}():\n' + prepare + expression)
                guard = ('    if not safe(rows, route):\n' + '    ' + expression
                         if strategy.startswith('guarded') else '')
                if strategy == 'guarded_fused':
                    fast = ('    a = b = c = 0\n    for i in route:\n        row = rows[i]\n'
                            '        a += row.a\n        b += row.b\n        c += row.c\n    return a, b, c\n')
                else:
                    fast = '    return sum([rows[i].a for i in route]), sum([rows[i].b for i in route]), sum([rows[i].c for i in route])\n'
                new.append(f'def {name}():\n' + prepare + guard + fast)
                cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def deferred_sources():
    old, new, cases = ['from dataclasses import dataclass\n'], ['from dataclasses import dataclass\n'], []
    for width in (4, 12):
        for threshold in (-1, 5, 10):
            tag = f'w{width}_t{threshold + 1}'
            name, cls = f'defer_{tag}', f'Row_{tag}'
            fields = [f'f{i}' for i in range(width)]
            definition = f'@dataclass(frozen=True)\nclass {cls}:\n'
            definition += ''.join(f'    {f}: object\n' for f in fields)
            producer = f'def produce_{tag}(seed):\n    f0 = seed % 8\n'
            producer += ''.join(f'    {f} = seed + {i}\n' for i, f in enumerate(fields[1:], 1))
            old.append(definition + producer + f'    return {cls}({", ".join(fields)})\n')
            new.append(definition + producer + f'    return ({", ".join(reversed(fields))})\n')
            common = f'def {name}():\n    kept=[]\n    for seed in range(128):\n'
            old.append(common + f'        row=produce_{tag}(seed)\n        if row.f0 > {threshold}:\n'
                       '            kept.append(row)\n    return tuple(row.f0 for row in kept)\n')
            arguments = ', '.join(f'packed[{-i-1}]' for i in range(width))
            new.append(common + f'        packed=produce_{tag}(seed)\n        if packed[-1] > {threshold}:\n'
                       f'            row={cls}({arguments})\n'
                       '            kept.append(row)\n    return tuple(row.f0 for row in kept)\n')
            cases.append(name)
    lifecycle = '''
@dataclass(frozen=True)
class LifecycleRow:
    a: object
    b: object
    c: object
    d: object
def release_order():
    events=[]
    class Item:
        def __init__(self, n):
            self.n=n
        def __del__(self):
            events.append(self.n)
    row = CONSTRUCTION
    del row
    return tuple(events)
'''
    old.append(lifecycle.replace('CONSTRUCTION', 'LifecycleRow(Item(0), Item(1), Item(2), Item(3))'))
    new.append(lifecycle.replace('CONSTRUCTION', 'tuple(reversed((Item(0), Item(1), Item(2), Item(3))))'))
    cases.append('release_order')
    inventory = f'CASES = {tuple(cases)!r}\n'
    return optimize_source(inventory + '\n'.join(old)).source, optimize_source(inventory + '\n'.join(new)).source, cases


def guard_sources():
    """Identity-only native-map alternatives; never call metaclass equality."""
    old, new, cases = [], ['from operator import is_\n'], []
    for width in (4, 8, 12, 20):
        for mixed in (False, True):
            for fail in (False, True):
                name = f'guards_{width}_{int(mixed)}_{int(fail)}'
                fields = [f'f{i}' for i in range(width)]
                kinds = ['float' if mixed and i % 3 == 0 else 'int' for i in range(width)]
                prepare = ''.join(f'    {field} = {i + 0.5 if kind == "float" else i}\n'
                                  for i, (field, kind) in enumerate(zip(fields, kinds)))
                if fail:
                    prepare += f'    {fields[width // 2]} = None\n'
                groups = []
                for kind in dict.fromkeys(kinds):
                    groups.append(' is '.join([*(f'type({f})' for f, k in zip(fields, kinds) if k == kind), kind]))
                old.append(f'def {name}():\n' + prepare + '    return ' + ' and '.join(groups) + '\n')
                new.append(f'TYPES_{name} = ({", ".join(kinds)})\n'
                           f'def {name}():\n' + prepare + '    return all(map(is_, map(type, ('
                           + ', '.join(fields) + f')), TYPES_{name}))\n')
                cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def fused_sources():
    """Compare actual generated one-loop guards at additional route lengths."""
    old, new, cases = [], [], []
    for limit in (4, 32):
        for size in (0, 1, 2, 3, 4, 5, 6, 8, 12, 16, 32):
            tag = f'fused_{limit}_{size}'
            source = f'''from dataclasses import dataclass
@dataclass(frozen=True)
class Row_{tag}:
    a: int
    b: int
    c: int
ROWS_{tag} = tuple(Row_{tag}(i, i+1, i+2) for i in range(32))
ROUTE_{tag} = tuple(range({size}))
def totals_{tag}(rows, route):
    a = sum(rows[i].a for i in route)
    b = sum(rows[i].b for i in route)
    c = sum(rows[i].c for i in route)
    return a, b, c
def {tag}():
    return totals_{tag}(ROWS_{tag}, ROUTE_{tag})
'''
            baseline = optimize_source(source, Options(disabled=frozenset({'short-int-reductions'}))).source
            generated = optimize_source(source).source.replace(' > 8', f' > {limit}')
            old.append(baseline.replace('_bcopt_', f'_probe_{tag}_'))
            new.append(generated.replace('_bcopt_', f'_probe_{tag}_'))
            cases.append(tag)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def shortcircuit_sources():
    old, new, cases = [], [], []
    for consumer in ('any', 'all'):
        helper = f'consume_{consumer}'
        new.append(f'''def {helper}(items):
    if not (type(items) is list or type(items) is tuple):
        return {consumer}(item < 0 for item in items)
    for item in items:
        try:
            value = item < 0
        except StopIteration as exc:
            raise RuntimeError('generator raised StopIteration') from exc
        try:
            try:
                if {'not ' if consumer == 'all' else ''}value:
                    return {consumer == 'any'}
            finally:
                del value
        except BaseException:
            del item
            raise
    return {consumer == 'all'}
''')
        for size in (0, 1, 4, 8, 16, 32):
            for early in (False, True):
                name = f'{consumer}_{size}_{int(early)}'
                values = [-1 if consumer == 'all' else 1] * size
                if early and size:
                    values[0] *= -1
                setup = f'DATA_{name} = {tuple(values)!r}\n'
                old.append(setup + f'def {name}():\n    return {consumer}(item < 0 for item in DATA_{name})\n')
                new.append(setup + f'def {name}():\n    return {helper}(DATA_{name})\n')
                cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--focus', choices=('initial', 'deferred', 'guards', 'fused', 'shortcircuit'), default='initial')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    output = args.output.resolve()
    old, new, cases = {'initial': sources, 'deferred': deferred_sources, 'guards': guard_sources,
                       'fused': fused_sources, 'shortcircuit': shortcircuit_sources}[args.focus]()
    src = output / 'bot/src'
    src.mkdir(parents=True)
    (src / 'original.py').write_text(old)
    (src / 'optimized.py').write_text(new)
    (src / 'main.py').write_text((Path(__file__).parent / 'src/main.py').read_text())
    report = {'status': 'running', 'manual_candidates': True, 'guard_cost_included': True, 'datasets': []}
    for game_map in ('collision', 'corners'):
        dest = output / game_map
        run_command([executable(), 'run', str(src.parent), str(src.parent), '--release', '--rounds', '1',
                     '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
        replay, = dest.glob('*.repl26a')
        data = summarize(replay, cases)
        data['map'] = game_map
        report['datasets'].append(data)
        for name, rows in data['pairs'].items():
            print(game_map, name, rows[0]['ratio'], flush=True)
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
