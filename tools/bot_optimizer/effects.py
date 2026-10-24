"""Conservative, path-sensitive callback effects for guarded numeric regions.

This is an analysis, not permission to skip a callback. Consumers must preserve
the call and its truth test, guard callable identity and dependency bindings, and
discard region facts on every other effectful path. No annotations establish an
effect contract. Native contracts target the pinned cambc 3.0.4 guest only.
"""

import ast
from dataclasses import dataclass

from .analysis import Bindings, arguments
from .program import body_without_docstring


# Guest wrapper and actual Wasm w_fuel_remaining were audited: the successful
# call reads sdk_fuel_remaining and converts its result to an exact Python int.
# The negative-ABI-error path raises; it never continues candidate evaluation.
SDK_READONLY_RETURNS = {'cambc.fuel_remaining': 'int'}
NUMERIC = {'int', 'float', 'bool', 'number'}
SCALAR = NUMERIC | {'none'}


@dataclass(frozen=True)
class FalseContinuation:
    function: str
    constants: tuple[str, ...]
    sdk_calls: tuple[str, ...]
    false_paths: int
    true_paths: int


class CallbackEffects:
    """Prove all False exits read-only; dirty True exits may terminate a region.

    Only zero-argument functions with exact boolean exits qualify. Unknown calls,
    custom truth/comparison, parameter promises, loops and dynamic bindings never
    certify continuation. Bounded path enumeration keeps compile cost predictable.
    """
    def __init__(self, program):
        self.program = program
        self.cache = {}

    def false_continuation(self, qualified):
        if qualified not in self.cache:
            self.cache[qualified] = self._analyze(qualified)
        return self.cache[qualified]

    def _analyze(self, qualified):
        function = self.program.functions.get(qualified)
        if (function is None or self.program.dynamic_modules or self.program._cyclic_imports()
                or arguments(function.node)):
            return None
        node, module = function.node, function.module
        if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.Lambda, ast.ClassDef,
                              ast.Yield, ast.YieldFrom, ast.Await, ast.NamedExpr))
               or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node
               for n in ast.walk(node)):
            return None
        local = set(Bindings(node.body).counts)
        constants, sdk_calls = set(), set()
        returns = []
        visited = 0

        def resolve(expression):
            root = expression
            while isinstance(root, ast.Attribute):
                root = root.value
            if not isinstance(root, ast.Name) or root.id in local:
                return None
            return self.program.resolve(module, expression)

        def expression(value, facts):
            """Exact result category and absence of user-visible mutation."""
            if isinstance(value, ast.Constant):
                kind = {int: 'int', float: 'float', bool: 'bool', type(None): 'none'}.get(type(value.value))
                return kind, True
            if isinstance(value, ast.Name) and value.id in local:
                return facts.get(value.id), value.id in facts
            if isinstance(value, (ast.Name, ast.Attribute)):
                name = resolve(value)
                if name in self.program.constants and self.program.available(module, value, node.lineno):
                    constants.add(name)
                    return 'int', True
                return None, False
            if isinstance(value, ast.Call):
                name = resolve(value.func)
                root = value.func
                while isinstance(root, ast.Attribute):
                    root = root.value
                imported = self.program.modules[module].imports.get(root.id) if isinstance(root, ast.Name) else None
                if (name in SDK_READONLY_RETURNS and 'cambc' not in self.program.modules
                        and imported and imported[1] < node.lineno and not value.args and not value.keywords):
                    sdk_calls.add(name)
                    return SDK_READONLY_RETURNS[name], True
                return None, False
            if isinstance(value, ast.UnaryOp):
                kind, pure = expression(value.operand, facts)
                if isinstance(value.op, ast.Not) and kind in SCALAR:
                    return 'bool', pure
                if isinstance(value.op, (ast.UAdd, ast.USub)) and kind in NUMERIC:
                    return ('int' if kind == 'bool' else kind), pure
                if isinstance(value.op, ast.Invert) and kind in {'int', 'bool'}:
                    return 'int', pure
            if isinstance(value, ast.BinOp):
                left, lp = expression(value.left, facts)
                right, rp = expression(value.right, facts)
                if left in NUMERIC and right in NUMERIC:
                    if isinstance(value.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)):
                        kind = 'int' if {left, right} <= {'int', 'bool'} else 'number'
                        return kind, lp and rp
                    if isinstance(value.op, ast.Div):
                        return 'float', lp and rp
                    if isinstance(value.op, (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)) and {left, right} <= {'int', 'bool'}:
                        return 'int', lp and rp
            if isinstance(value, ast.Compare):
                parts = [expression(part, facts) for part in [value.left, *value.comparators]]
                if all(pure for _, pure in parts):
                    if all(isinstance(op, (ast.Is, ast.IsNot)) for op in value.ops):
                        return 'bool', True
                    if (all(kind in NUMERIC for kind, _ in parts)
                            and all(isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in value.ops)):
                        return 'bool', True
            if isinstance(value, ast.BoolOp):
                parts = [expression(part, facts) for part in value.values]
                if all(kind == 'bool' and pure for kind, pure in parts):
                    return 'bool', True
            return None, False

        def block(statements, facts, dirty):
            nonlocal visited
            visited += len(statements) + 1
            if visited > 512:
                raise ValueError('effect path budget')
            if not statements:
                returns.append((None, dirty))  # Implicit None is a falsey continuation.
                return
            statement, *tail = statements
            if isinstance(statement, ast.Return):
                kind, pure = expression(statement.value, facts)
                if isinstance(statement.value, ast.Constant) and type(statement.value.value) is bool:
                    returns.append((statement.value.value, dirty or not pure))
                elif kind == 'bool':
                    returns.extend([(False, dirty or not pure), (True, dirty or not pure)])
                else:
                    returns.append((None, True))
                return
            if isinstance(statement, ast.Raise):
                return  # No ordinary continuation, including construction errors.
            if isinstance(statement, ast.If):
                kind, pure = expression(statement.test, facts)
                changed = dirty or not pure or kind not in SCALAR
                block([*statement.body, *tail], dict(facts), changed)
                block([*statement.orelse, *tail], dict(facts), changed)
                return
            if isinstance(statement, ast.Assign) and all(isinstance(target, ast.Name) for target in statement.targets):
                kind, pure = expression(statement.value, facts)
                facts = dict(facts)
                for target in statement.targets:
                    if kind in SCALAR and pure:
                        facts[target.id] = kind
                    else:
                        facts.pop(target.id, None)
                block(tail, facts, dirty or not pure or kind not in SCALAR)
                return
            if isinstance(statement, ast.Expr):
                _, pure = expression(statement.value, facts)
                block(tail, facts, dirty or not pure)
                return
            if isinstance(statement, ast.Pass):
                block(tail, facts, dirty)
                return
            raise ValueError('unsupported callback control flow')

        try:
            block(body_without_docstring(node.body), {}, False)
        except ValueError:
            return None
        if (not any(result is False for result, _ in returns)
                or any(result is None or result is False and dirty for result, dirty in returns)):
            return None
        return FalseContinuation(qualified, tuple(sorted(constants)), tuple(sorted(sdk_calls)),
                                 sum(result is False for result, _ in returns),
                                 sum(result is True for result, _ in returns))
