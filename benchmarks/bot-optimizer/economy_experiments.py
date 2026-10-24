"""Generic allocation/reduction/layout alternatives motivated by planner profiling.

These are manual candidates, not accepted compiler transformations. In particular,
native attribute maps and fused reductions require stronger effect/type proofs.
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
    for width in (2, 3, 4, 8, 12, 20):
        for variant in ('replace', 'stores', 'update'):
            name = f'allocate_{width}_{variant}'
            cls = f'Row_{width}_{variant}'
            fields = [f'f{i}' for i in range(width)]
            source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass ' + cls + ':\n'
            source += ''.join(f'    {field}: object\n' for field in fields)
            current = optimize_source(source).source
            mapping = '{' + ', '.join(f'{f!r}: {f}' for f in fields) + '}'
            factory = f'def make_{cls}(_cls, {", ".join(fields)}):\n    row = object.__new__(_cls)\n'
            if variant == 'replace':
                factory += f"    object.__setattr__(row, '__dict__', {mapping})\n"
            elif variant == 'update':
                factory += f'    row.__dict__.update({mapping})\n'
            else:
                factory += '    d = row.__dict__\n' + ''.join(f'    d[{f!r}] = {f}\n' for f in fields)
            factory += '    return row\n'
            args = ', '.join(str(i) for i in range(width))
            body = f'def {name}():\n    row = {{constructor}}({args})\n    return row.f0 + row.f{width-1}\n'
            old.append(current + '\n' + body.format(constructor=cls))
            new.append(current + '\n' + factory + body.format(constructor='make_' + cls).replace(
                f'make_{cls}({args})', f'make_{cls}({cls}, {args})'))
            cases.append(name)
    setup = '''from dataclasses import dataclass
from _operator import attrgetter
@dataclass(frozen=True)
class Entry:
    a: int
    b: int
    c: int
GET_A = attrgetter('a')
'''
    old.append(setup)
    new.append(setup)
    for size in (0, 1, 8, 32, 128):
        for variant in ('native', 'eager', 'fused', 'layout'):
            name = f'reduction_{size}_{variant}'
            prepare = f'    rows = tuple(Entry(i, i+1, i+2) for i in range({size}))\n'
            # Include layout conversion and row creation in both sides.
            expression = '    return sum(row.a for row in rows), sum(row.b for row in rows), sum(row.c for row in rows)\n'
            old.append(f'def {name}():\n' + prepare + expression)
            if variant == 'native':
                new.append(f'GET_B = attrgetter("b")\nGET_C = attrgetter("c")\ndef {name}():\n' + prepare +
                           '    return sum(map(GET_A, rows)), sum(map(GET_B, rows)), sum(map(GET_C, rows))\n')
            elif variant == 'eager':
                new.append(f'def {name}():\n' + prepare +
                           '    return sum([row.a for row in rows]), sum([row.b for row in rows]), sum([row.c for row in rows])\n')
            elif variant == 'layout':
                new.append(f'def {name}():\n' + prepare +
                           '    columns = tuple(zip(*((row.a, row.b, row.c) for row in rows)))\n'
                           '    return tuple(map(sum, columns)) if columns else (0, 0, 0)\n')
            else:
                new.append(f'def {name}():\n' + prepare +
                           '    a = b = c = 0\n    for row in rows:\n        a += row.a\n        b += row.b\n        c += row.c\n    return a, b, c\n')
            cases.append(name)
    for size in (8, 128, 4096):
        for divisor in (2, 8, 256):
            name = f'modulo_{size}_{divisor}'
            template = (f'def {name}():\n    count = 0\n    total = 0\n'
                        f'    for i in range(-{size}, {size}):\n'
                        '        count += 1\n        total += (i {operation}) == 0\n'
                        '    return total, count\n')
            old.append(template.format(operation=f'% {divisor}'))
            new.append(template.format(operation=f'& {divisor-1}'))
            cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def allocator_sources():
    """Challenge the accepted factory's remaining fixed builtin lookup cost."""
    old, new, cases = [], [], []
    for width in (1, 2, 3):
        for cached in (False, True):
            name = f'allocator_{width}_{"cached" if cached else "direct"}'
            cls = f'Row_{name}'
            fields = [f'f{i}' for i in range(width)]
            definition = ('@dataclass(frozen=True)\n'
                          f'class {cls}:\n' + ''.join(f'    {f}: object\n' for f in fields))
            args = ', '.join(str(i) for i in range(width))
            body = (f'def {name}():\n    row = {{constructor}}({args})\n'
                    f'    result = row.f0 + row.f{width-1}\n    return result\n')
            old.append(definition + body.format(constructor=cls))
            helper = f'make_{cls}'
            factory = (f'_new_{cls} = object.__new__\n' if cached else '')
            factory += (f'def {helper}(_cls, {", ".join(fields)}):\n'
                        f'    row = {"_new_" + cls if cached else "object.__new__"}(_cls)\n'
                        '    d = row.__dict__\n')
            factory += ''.join(f'    d[{f!r}] = {f}\n' for f in fields)
            factory += '    return row\n'
            new.append(definition + factory + body.format(constructor=helper).replace(
                f'{helper}({args})', f'{helper}({cls}, {args})'))
            cases.append(name)
    inventory = f'from dataclasses import dataclass\nCASES = {tuple(cases)!r}\n'
    baseline = optimize_source(inventory + '\n'.join(old), Options(
        disabled=frozenset({'record-allocator-cache'}))).source
    return baseline, inventory + '\n'.join(new), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--focus', choices=('all', 'allocator'), default='all')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('output must be new')
    cli = executable()
    old, new, cases = allocator_sources() if args.focus == 'allocator' else sources()
    src = output / 'bot/src'
    src.mkdir(parents=True)
    (src/'original.py').write_text(old)
    (src/'optimized.py').write_text(new)
    (src/'main.py').write_text((Path(__file__).parent/'src/main.py').read_text())
    report = {'status': 'running', 'manual_candidates': True, 'setup_included': True, 'datasets': []}
    for game_map in ('collision', 'corners'):
        dest = output / game_map
        run_command([cli, 'run', str(src.parent), str(src.parent), '--release', '--rounds', '1',
                     '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
        replay, = dest.glob('*.repl26a')
        data = summarize(replay, cases)
        data['map'] = game_map
        report['datasets'].append(data)
        for name, rows in data['pairs'].items():
            print(game_map, name, rows[0]['ratio'], flush=True)
        (output/'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (output/'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
