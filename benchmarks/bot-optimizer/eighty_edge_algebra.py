"""Research-only insertion edge totals over certified nonnegative integer tables.

Cache the base tour's exact integer total lazily at the original evaluation point.
Each insertion replaces one edge (or one endpoint) instead of materializing and
scanning the full edge list. Original code handles uncertified tables and indices.
Names here describe the economy research output, not a production proof.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.model import Options


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    prefix = '_bcopt_algebra80_'
    assert not any(name.startswith(prefix) for name in used_names(tree))
    # Snapshot tables are immutable exact integer tuples; certification is scoped
    # to the same snapshot as the prepared numeric version.
    setup = ast.parse('''
import builtins as _bcopt_algebra80_b
_bcopt_algebra80_n = _bcopt_algebra80_b.len(_bcopt_entry_local_34)
_bcopt_algebra80_cert = (
    _bcopt_algebra80_b.len(_bcopt_entry_local_47) >= _bcopt_algebra80_n
    and _bcopt_algebra80_b.all(_bcopt_algebra80_b.len(row) >= _bcopt_algebra80_n and
        _bcopt_algebra80_b.all(value >= 0 for value in row) for row in _bcopt_entry_local_34)
    and _bcopt_algebra80_b.all(_bcopt_algebra80_b.len(row) >= _bcopt_algebra80_n and
        _bcopt_algebra80_b.all(value >= 0 for value in row) for row in _bcopt_entry_local_30)
    and _bcopt_algebra80_b.all(value >= 0 for value in _bcopt_entry_local_47))
''').body
    outer = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.For))
    consumer.body[outer:outer] = setup
    producer, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == '_bcopt_fused_camp_index']
    class Initialize(ast.NodeTransformer):
        def visit_For(self, node):
            if node is producer:
                return [*ast.parse('''
_bcopt_algebra80_base_total = None
_bcopt_algebra80_valid = None
''').body, node]
            return self.generic_visit(node)
    Initialize().visit(consumer)
    version, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name) and node.test.id == '_bcopt_entry_prepared_ready_0']
    protected, = version.body
    assert isinstance(protected, ast.Try)
    guard = protected.body[-1]
    assert isinstance(guard, ast.If) and isinstance(guard.test, ast.BoolOp)
    old_edges = copy.deepcopy(protected.body[:-1])
    assert len(old_edges) == 3
    body = ast.parse('''
if _bcopt_algebra80_valid is None:
    _bcopt_algebra80_valid = (_bcopt_algebra80_cert and _bcopt_fused_size > 1
        and 0 <= altar_index < _bcopt_algebra80_b.len(_bcopt_entry_local_30)
        and _bcopt_algebra80_b.all(-_bcopt_algebra80_n <= item < _bcopt_algebra80_n for item in _bcopt_fused_route))
_bcopt_algebra80_fast = _bcopt_algebra80_valid and -_bcopt_algebra80_n <= _bcopt_fused_camp_index < _bcopt_algebra80_n
if _bcopt_algebra80_fast:
    _bcopt_entry_local_35, _bcopt_entry_local_39 = route[0], route[-1]
    if _bcopt_algebra80_base_total is None:
        _bcopt_algebra80_base_total = _bcopt_entry_local_30[altar_index][_bcopt_fused_route[0]] + _bcopt_entry_local_30[altar_index][_bcopt_fused_route[-1]]
        for _bcopt_algebra80_a, _bcopt_algebra80_z in _bcopt_algebra80_b.zip(_bcopt_fused_route, _bcopt_fused_route[1:]):
            _bcopt_algebra80_base_total += _bcopt_entry_local_34[_bcopt_algebra80_a][_bcopt_algebra80_z]
    _bcopt_algebra80_first = _bcopt_entry_local_30[altar_index][_bcopt_entry_local_35]
    if _bcopt_edge_position == 0:
        _bcopt_algebra80_total = (_bcopt_algebra80_base_total - _bcopt_entry_local_30[altar_index][_bcopt_fused_route[0]]
            + _bcopt_algebra80_first + _bcopt_entry_local_34[_bcopt_fused_camp_index][_bcopt_fused_route[0]])
    elif _bcopt_edge_position == _bcopt_fused_size - 1:
        _bcopt_algebra80_total = (_bcopt_algebra80_base_total - _bcopt_entry_local_30[altar_index][_bcopt_fused_route[-1]]
            + _bcopt_entry_local_30[altar_index][_bcopt_fused_camp_index] + _bcopt_entry_local_34[_bcopt_fused_route[-1]][_bcopt_fused_camp_index])
    else:
        _bcopt_algebra80_a, _bcopt_algebra80_z = _bcopt_fused_route[_bcopt_edge_position-1], _bcopt_fused_route[_bcopt_edge_position]
        _bcopt_algebra80_total = (_bcopt_algebra80_base_total - _bcopt_entry_local_34[_bcopt_algebra80_a][_bcopt_algebra80_z]
            + _bcopt_entry_local_34[_bcopt_algebra80_a][_bcopt_fused_camp_index] + _bcopt_entry_local_34[_bcopt_fused_camp_index][_bcopt_algebra80_z])
else:
    pass
''').body
    body[-1].orelse = old_edges
    guard.test = ast.BoolOp(op=ast.And(), values=[ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=prefix+'fast', ctx=ast.Load())), guard.test])
    replaced = []
    class Reads(ast.NodeTransformer):
        def visit_Call(self, node):
            if (isinstance(node.func, ast.Name) and node.func.id == 'sum' and len(node.args) == 1
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == '_bcopt_entry_local_40'):
                replaced.append('total')
                return ast.IfExp(test=ast.Name(id=prefix+'fast', ctx=ast.Load()),
                    body=ast.Name(id=prefix+'total', ctx=ast.Load()), orelse=node)
            return self.generic_visit(node)
        def visit_Subscript(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == '_bcopt_entry_local_40':
                assert isinstance(node.slice, ast.Constant) and node.slice.value == 0
                replaced.append('first')
                return ast.IfExp(test=ast.Name(id=prefix+'fast', ctx=ast.Load()),
                    body=ast.Name(id=prefix+'first', ctx=ast.Load()), orelse=node)
            return self.generic_visit(node)
    for statement in guard.orelse:
        Reads().visit(statement)
    assert replaced == ['total', 'first'], replaced
    protected.body = [*body, guard]
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-edge-algebra'}):
            transform(output)
            report['pass_counts']['experiment-edge-algebra'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-edge-algebra'})))
    report['experimental_post_compile_transform'] = 'nonnegative integer insertion edge algebra, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
