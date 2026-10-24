"""Research-only numeric-entry inlining; measure before production integration."""

import argparse
import ast
import copy
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.analysis import Bindings, arguments
from tools.bot_optimizer.model import Options
from tools.bot_optimizer.numeric_regions import inline_numeric_helpers
from tools.bot_optimizer.records import used_names
import tools.bot_optimizer.compare as measurement


def transform(folder, *, hoist_inputs=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    numeric, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name.startswith('_bcopt_region_numeric_') and len(node.body) == 1
                and isinstance(node.body[0], ast.Try)]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    retry = numeric.body[0]
    assert not retry.finalbody and not retry.orelse
    assert len(retry.handlers) == 1 and len(retry.handlers[0].body) == 1
    assert isinstance(retry.handlers[0].body[0], ast.Return)
    helper = copy.deepcopy(numeric)
    helper.body = helper.body[0].body
    locals_ = set(Bindings(helper.body).counts) | {arg.arg for arg in arguments(helper)}
    loads = {node.id for node in ast.walk(helper) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    caller_locals = set(Bindings(consumer.body).counts) | {arg.arg for arg in arguments(consumer)}
    assert not (loads-locals_) & caller_locals
    taken, allocated = used_names(tree), set()
    def fresh(stem):
        index = 0
        while f'_bcopt_inline80_{stem}_{index}' in taken:
            index += 1
        name = f'_bcopt_inline80_{stem}_{index}'
        taken.add(name)
        allocated.add(name)
        return name
    changed, hoisted = [], []
    class Inline(ast.NodeTransformer):
        def visit_Assign(self, node):
            if (not isinstance(node.value, ast.IfExp) or not isinstance(node.value.body, ast.Call)
                    or not isinstance(node.value.body.func, ast.Name) or node.value.body.func.id != numeric.name):
                return self.generic_visit(node)
            assert len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            call = copy.deepcopy(node)
            call.value = copy.deepcopy(node.value.body)
            wrapper = ast.parse('def wrapper():\n    pass\n').body[0]
            wrapper.body = [call]
            entry = SimpleNamespace(function=wrapper)
            builder = SimpleNamespace(fresh=fresh, clones={
                'entry': entry, 'helper': SimpleNamespace(name=helper.name, function=helper)})
            assert inline_numeric_helpers(builder, entry, helper_limit=6000, output_limit=12000) == 1
            target = node.targets[0].id
            class Release(ast.NodeTransformer):
                def visit_Assign(self, statement):
                    if (len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)
                            and statement.targets[0].id == target and isinstance(statement.value, ast.Name)
                            and statement.value.id in allocated):
                        return [statement, ast.Delete(targets=[ast.Name(id=statement.value.id, ctx=ast.Del())])]
                    return self.generic_visit(statement)
            body = Release().visit(entry.function).body
            if hoist_inputs:
                root = node.value.body.args[0]
                assert isinstance(root, ast.Name)
                writes = Counter(part.id for statement in body for part in ast.walk(statement)
                                 if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del)))
                def root_read(value):
                    if isinstance(value, ast.Tuple):
                        return all(root_read(item) for item in value.elts)
                    return (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
                            and value.value.id == root.id and isinstance(value.slice, ast.Constant)
                            and type(value.slice.value) is int and value.slice.value >= 0)
                class Hoist(ast.NodeTransformer):
                    def visit_Assign(self, statement):
                        if root_read(statement.value) and all(
                                part.id in allocated and writes[part.id] == 1 for target in statement.targets for part in ast.walk(target)
                                if isinstance(part, ast.Name)):
                            hoisted.append(statement)
                            return None
                        return self.generic_visit(statement)
                temporary = ast.Module(body=body, type_ignores=[])
                body = Hoist().visit(temporary).body
            handler = copy.deepcopy(retry.handlers[0])
            handler.body = [ast.Assign(targets=copy.deepcopy(node.targets), value=handler.body[0].value)]
            protected = ast.Try(body=body, handlers=[handler], orelse=[], finalbody=[])
            fallback = copy.deepcopy(node)
            fallback.value = node.value.orelse
            changed.append(node.lineno)
            return ast.If(test=node.value.test, body=[protected], orelse=[fallback])
    Inline().visit(consumer)
    assert len(changed) == 1
    if hoist_inputs:
        assert hoisted
        # The generated consumer binds its validated snapshot before this point.
        consumer.body[2:2] = hoisted
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hoist-inputs', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'numeric-entry-inline'}):
            transform(output, hoist_inputs=args.hoist_inputs)
            report['pass_counts']['experiment-inline-numeric-entry'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'numeric-entry-inline'})))
    report['experimental_post_compile_transform'] = 'numeric-entry inlining, not production integrated'
    report['hoisted_snapshot_inputs'] = args.hoist_inputs
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
