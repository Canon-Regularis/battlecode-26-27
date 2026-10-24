"""Research-only native scans for the compensated-sum binary-grid certificate."""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement


CERTIFICATE = '''def certify(values):
    import sys as _sys
    import builtins as _b
    from math import frexp as _frexp
    if (_sys.implementation.name != 'cpython' or _sys.version_info[:2] != (3, 13)
            or _sys.float_info.radix != 2 or _sys.float_info.mant_dig != 53
            or _sys.float_info.rounds != 1 or values is None or _b.len(values) > 4096):
        return False
    if _b.any(_b.type(value) is not _b.float for value in values):
        return False
    total = _b.sum(values)
    if not 0.0 <= total < _b.float('inf'):
        return False
    minimum = _b.min(_b.filter(None, values), default=0.0)
    if minimum < 0.0:
        return False
    if minimum == 0.0:
        return True
    maximum = _b.max(values)
    grid = _b.max(_frexp(minimum)[1] - 53, -1074)
    exponent = _frexp(maximum)[1]
    return exponent - grid <= 80 and exponent + 5 <= 1023
'''


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    helper, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name.startswith('_bcopt_compensated_certify')]
    replacement = ast.parse(CERTIFICATE).body[0]
    replacement.name = helper.name
    tree.body[tree.body.index(helper)] = replacement
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if not options.disabled:
            transform(output)
            report['pass_counts']['experiment-native-certificate'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'native-scan binary-grid certificate, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
