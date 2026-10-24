"""Native numeric operations under private emitter-owned type contracts.

Run after ordinary passes, so precise facts survive numeric helper inlining and
do not interfere with record-return allocation lowering. No source spelling or
annotation grants a contract to this pass.
"""

import ast
import copy

from .model import Change
from .records import used_names


class NumericOperations(ast.NodeTransformer):
    def __init__(self, options):
        self.options = options
        self.changes = []
        self.taken = set()
        self.aliases = {}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_numeric_{stem}_{index}' in self.taken:
            index += 1
        name = f'_bcopt_numeric_{stem}_{index}'
        self.taken.add(name)
        return name

    def native(self, name):
        if name not in self.aliases:
            self.aliases[name] = self.fresh(name)
        return ast.Name(id=self.aliases[name], ctx=ast.Load())

    def apply(self, tree):
        if 'numeric-region-operations' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and getattr(node, '_bcopt_numeric_clone', False):
                node.body = [self.visit(statement) for statement in node.body]
        if self.aliases:
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body.insert(index, ast.ImportFrom(module='builtins', level=0,
                names=[ast.alias(name=name, asname=alias) for name, alias in self.aliases.items()]))
        return ast.fix_missing_locations(tree)

    def replaced(self, node, replacement):
        self.changes.append(Change('numeric-region-operations', node.lineno,
                                   ast.unparse(node), ast.unparse(replacement)))
        for name, value in vars(node).items():
            if name.startswith('_bcopt_numeric_'):
                setattr(replacement, name, value)
        return ast.copy_location(replacement, node)

    def visit_Call(self, node):
        self.generic_visit(node)
        operation = getattr(node, '_bcopt_numeric_native', None)
        if node.keywords:
            return node
        if operation in {'min', 'max'} and len(node.args) == 2:
            left, right = node.args
            if not isinstance(left, (ast.Name, ast.Constant)):
                return node
            if getattr(node, '_bcopt_numeric_kind', None) not in {'int', 'float', 'bool', 'number'}:
                return node
            # The first argument is an already-bound primitive or inert literal.
            # Comparing second against first preserves native ties, NaNs and -0.
            temporary = self.fresh('extremum')
            comparison = ast.Compare(left=ast.NamedExpr(target=ast.Name(id=temporary, ctx=ast.Store()), value=right),
                                     ops=[ast.Lt() if operation == 'min' else ast.Gt()], comparators=[left])
            result = ast.IfExp(test=comparison, body=ast.Name(id=temporary, ctx=ast.Load()), orelse=copy.deepcopy(left))
            return self.replaced(node, result)
        if operation not in {'any', 'all'} or len(node.args) != 1:
            return node
        comp = node.args[0]
        if not isinstance(comp, ast.ListComp) or len(comp.generators) != 1:
            return node
        generator, comparison = comp.generators[0], comp.elt
        if (generator.is_async or generator.ifs or not isinstance(generator.target, ast.Name)
                or not isinstance(generator.iter, ast.Name)
                or getattr(generator.iter, '_bcopt_numeric_kind', None) not in {'list', 'tuple', 'fixed-tuple'}
                or not isinstance(comparison, ast.Compare) or len(comparison.ops) != 1
                or not isinstance(comparison.left, ast.Name) or comparison.left.id != generator.target.id
                or getattr(comparison.left, '_bcopt_numeric_kind', None) != 'int'
                or not isinstance(comparison.comparators[0], ast.Constant)
                or type(comparison.comparators[0].value) is not int
                or not isinstance(comparison.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE))):
            return node
        less = isinstance(comparison.ops[0], (ast.Lt, ast.LtE))
        reduction = 'min' if less == (operation == 'any') else 'max'
        compare = ast.Compare(left=ast.Call(func=self.native(reduction), args=[copy.deepcopy(generator.iter)], keywords=[]),
                              ops=comparison.ops, comparators=comparison.comparators)
        result = ast.IfExp(test=copy.deepcopy(generator.iter), body=compare, orelse=ast.Constant(operation == 'all'))
        return self.replaced(node, result)
