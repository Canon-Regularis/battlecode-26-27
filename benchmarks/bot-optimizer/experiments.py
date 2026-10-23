"""Reproducible competing implementations, measured in the actual Wasm guest.

This is deliberately separate from production passes. No bot sources are changed.
Run: uv run python benchmarks/bot-optimizer/experiments.py --output <new-folder>
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.runtime import executable, run_command


def sources():
    old = ["from _operator import itemgetter, attrgetter\nfrom cambc import ChampionState",
           '''def runtime_info():
    import _imp, sysconfig, sys
    modules = {}
    for name in ('ctypes', '_ctypes', 'wasmtime', '_operator', 'array', '_struct'):
        try:
            module = __import__(name)
            modules[name] = getattr(module.__spec__, 'origin', None)
        except ImportError as error:
            modules[name] = str(error)
    return {'extension_suffixes': _imp.extension_suffixes(), 'platform': sys.platform,
            'shared': sysconfig.get_config_var('Py_ENABLE_SHARED'), 'modules': modules}
''']
    new = old.copy()
    cases = []
    for width in (2, 4, 8, 12, 20):
        fields = [f"f{i}" for i in range(width)]
        params = ', '.join(fields)
        mapping = ', '.join(f"'{f}': {f}" for f in fields)
        guard = "        if type(self) is Row:\n"
        fallback = "        else:\n" + ''.join(
            f"            object.__setattr__(self, '{f}', {f})\n" for f in fields)
        variants = {
            "stores": "            d = self.__dict__\n" + ''.join(
                f"            d['{f}'] = {f}\n" for f in fields),
            "kwargs": "            self.__dict__.update(" + ', '.join(f"{f}={f}" for f in fields) + ")\n",
        }
        for variant, body in variants.items():
            name = f"record{width}_{variant}"
            class_name = f"Row_{name}"
            header = f"class {class_name}:\n    def __init__(self, {params}):\n"
            base_body = guard + f"            self.__dict__.update({{{mapping}}})\n" + fallback
            candidate_body = guard + body + fallback
            call = f"{class_name}({', '.join(str(i) for i in range(width))})"
            function = f"def {name}():\n    row = {call}\n    return row.f0 + row.f{width-1}\n"
            old.append(header + base_body.replace('is Row:', f'is {class_name}:') + function)
            new.append(header + candidate_body.replace('is Row:', f'is {class_name}:') + function)
            cases.append(name)
    for size in (0, 1, 8, 128, 4096):
        name = f"filtered_sum_{size}"
        old.append(f"def {name}():\n    return sum(x*x for x in range({size}) if x & 1)\n")
        new.append(f"def {name}():\n    return sum([x*x for x in range({size}) if x & 1])\n")
        cases.append(name)
    for size in (0, 1, 8, 128):
        setup = f"    rows = [(i % 7, -i, i) for i in range({size})]\n"
        name = f"tuple_key_{size}"
        old.append(f"def {name}():\n" + setup + "    return sorted(rows, key=lambda r: (r[0], r[1]))\n")
        new.append(f"_key_{size} = itemgetter(0, 1)\ndef {name}():\n" + setup + f"    return sorted(rows, key=_key_{size})\n")
        cases.append(name)
    for size in (0, 1, 8, 128):
        name = f"tuple_map_{size}"
        old.append(f"def {name}():\n    return tuple(abs(x) for x in range(-{size}, 0))\n")
        new.append(f"def {name}():\n    return tuple(map(abs, range(-{size}, 0)))\n")
        cases.append(name)
    for size in (1, 4, 8, 32, 128):
        name = f"membership_{size}"
        values = tuple(range(0, size*2, 2))
        old.append(f"def {name}():\n    total=0\n    for x in range(128):\n        total += x in {values!r}\n    return total\n")
        new.append(f"def {name}():\n    total=0\n    for x in range(128):\n        total += x in {{{', '.join(map(str, values))}}}\n    return total\n")
        cases.append(name)
    for label, bit in (('early', 'RECALLING'), ('late', 'TELEPORTING'), ('none', None)):
        name = f'flag_group_{label}'
        setup = f'    state = ChampionState({"ChampionState." + bit if bit else "0"})\n'
        old.append(f'def {name}():\n' + setup +
                   '    return (ChampionState.RECALLING in state or ChampionState.SUBMITTING_GEMS in state or ChampionState.TELEPORTING in state)\n')
        new.append(f'_mask_{label} = ChampionState(ChampionState.RECALLING | ChampionState.SUBMITTING_GEMS | ChampionState.TELEPORTING)\n'
                   f'def {name}():\n' + setup + f'    return state.intersects(_mask_{label})\n')
        cases.append(name)
    inventory = f"CASES = {tuple(cases)!r}\n"
    return '\n'.join([inventory, *old]), '\n'.join([inventory, *new]), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('output must be a new directory')
    cli = executable()
    old, new, cases = sources()
    src = output / 'bot/src'
    src.mkdir(parents=True)
    (src / 'original.py').write_text(old)
    (src / 'optimized.py').write_text(new)
    (src / 'main.py').write_text((Path(__file__).parent / 'src/main.py').read_text())
    report = {'status': 'running', 'description': __doc__, 'datasets': []}
    for game_map in ('collision', 'corners'):
        dest = output / game_map
        run_command([cli, 'run', str(src.parent), str(src.parent), '--release', '--rounds', '1',
                     '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)])
        dataset = summarize(next(dest.glob('*.repl26a')), cases)
        dataset['map'] = game_map
        report['datasets'].append(dataset)
        for name, records in dataset['pairs'].items():
            print(game_map, name, round(records[0]['ratio'], 4))
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
