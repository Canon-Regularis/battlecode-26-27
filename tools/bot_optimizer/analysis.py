"""Small, deliberately closed-world type/effect analysis.

Facts describe exact runtime types, not Python's general numeric protocols.
Unknowns are not inferred from method names or (by default) annotations.
"""

import ast
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    kind: str = "unknown"
    value: object = None
    item: str = "unknown"
    size: int | None = None


UNKNOWN = Fact()
INT = Fact("int")
BOARD = Fact("board")
FIELD = Fact("field")
VEC = Fact("vec")

# Public API contracts for the bundled 3.0.4 SDK, not the workspace 2.1.6 stubs.
SDK_RETURNS = {
    "cambc.Bitboard": BOARD,
    "cambc.DistanceField": FIELD,
    "cambc.Vec2": VEC,
    "cambc.me": Fact("champion"),
    **{f"cambc.game_map.{name}": BOARD for name in (
        "walls", "holes", "altars", "spawn_region",
    )},
    **{f"cambc.vision.{name}": BOARD for name in (
        "visible_tiles", "champion_tiles", "camp_tiles", "teleport_tiles",
        "awake_camp_tiles",
    )},
}


class Bindings(ast.NodeVisitor):
    """Bindings in one lexical scope, including branch/loop assignments."""

    def __init__(self, body):
        self.counts = Counter()
        self.imports = {}
        self.external = set()
        for statement in body:
            self.visit(statement)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.counts[node.id] += 1

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.counts[name] += 1
            self.imports[name] = alias.name if alias.asname else name

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.counts[name] += 1
            self.imports[name] = f"{node.module}.{alias.name}" if not node.level else ""

    def visit_FunctionDef(self, node):
        self.counts[node.name] += 1
        # Defaults/decorators execute in this scope, the body does not.
        for expression in [*node.decorator_list, *node.args.defaults,
                           *(x for x in node.args.kw_defaults if x is not None),
                           *(arg.annotation for arg in arguments(node) if arg.annotation),
                           *([node.returns] if node.returns else [])]:
            self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.counts[node.name] += 1
        for expression in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(expression)

    def visit_Lambda(self, node):
        for expression in [*node.args.defaults,
                           *(x for x in node.args.kw_defaults if x is not None)]:
            self.visit(expression)

    def visit_comprehension(self, node):
        # Iteration targets live in the comprehension's private scope.
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.counts[node.name] += 1
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.counts[node.name] += 1
        self.generic_visit(node)

    def visit_MatchStar(self, node):
        if node.name:
            self.counts[node.name] += 1

    def visit_MatchMapping(self, node):
        if node.rest:
            self.counts[node.rest] += 1
        self.generic_visit(node)

    def visit_Global(self, node):
        self.external.update(node.names)

    visit_Nonlocal = visit_Global


def arguments(node):
    args = node.args
    return [*args.posonlyargs, *args.args, *args.kwonlyargs,
            *([args.vararg] if args.vararg else []),
            *([args.kwarg] if args.kwarg else [])]


def hazards(tree):
    """Reflection and monkey-patching invalidate closed-world assumptions."""
    reasons = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            reasons.add("direct access to builtins namespace")
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            reasons.add("star import")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "exec", "eval", "globals", "locals", "vars", "dir", "setattr", "delattr",
                "__import__",
            }:
                reasons.add(f"dynamic operation {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr in {
            "__dict__", "__globals__", "__builtins__", "f_globals", "f_locals",
            "modules", "import_module", "settrace", "setprofile", "_getframe", "currentframe",
            "__code__", "__closure__",
        }:
            reasons.add(f"reflective attribute {node.attr}")
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            # Instance attributes are common. Writes via imported module names
            # are checked by the compiler's whole-folder scan instead.
            if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
                reasons.add("builtins mutation")
    return sorted(reasons)


def annotation_fact(node, resolve):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return UNKNOWN
    if isinstance(node, ast.Subscript) and resolve(node.value) in {"tuple", "typing.Tuple"}:
        elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if len(elements) == 2 and isinstance(elements[1], ast.Constant) and elements[1].value is Ellipsis:
            item = annotation_fact(elements[0], resolve)
            return Fact("tuple", item=item.kind)
        items = [annotation_fact(part, resolve).kind for part in elements]
        return Fact("tuple", item=items[0] if items and len(set(items)) == 1 else "unknown", size=len(items))
    name = resolve(node)
    return {"int": INT, "cambc.Bitboard": BOARD, "cambc.DistanceField": FIELD,
            "cambc.Vec2": VEC}.get(name, UNKNOWN)


def infer(node, facts, resolve, returns=None):
    if isinstance(node, ast.Name):
        return facts.get(node.id, UNKNOWN)
    if isinstance(node, ast.Constant):
        return Fact("int", node.value) if type(node.value) is int else UNKNOWN
    if isinstance(node, (ast.List, ast.Tuple)):
        if any(isinstance(item, ast.Starred) for item in node.elts):
            return Fact("tuple" if isinstance(node, ast.Tuple) else "sequence")
        items = [infer(item, facts, resolve, returns).kind for item in node.elts]
        item = items[0] if items and len(set(items)) == 1 else "unknown"
        return Fact("tuple" if isinstance(node, ast.Tuple) else "sequence", item=item, size=len(items))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        operand = infer(node.operand, facts, resolve, returns)
        if operand.kind == "int":
            if operand.value is not None:
                value = {ast.UAdd: lambda x: x, ast.USub: lambda x: -x,
                         ast.Invert: lambda x: ~x}[type(node.op)](operand.value)
                return Fact("int", value)
            return INT
        if operand.kind == "board" and isinstance(node.op, ast.Invert):
            return BOARD
    if isinstance(node, ast.BinOp):
        left, right = infer(node.left, facts, resolve, returns), infer(node.right, facts, resolve, returns)
        if left.kind == right.kind == "int" and isinstance(node.op, (
            ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.LShift,
            ast.RShift, ast.BitOr, ast.BitAnd, ast.BitXor,
        )):
            return INT
        if left.kind == right.kind == "board" and isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor)):
            return BOARD
    if isinstance(node, ast.Call) and not any(isinstance(a, ast.Starred) for a in node.args):
        name = resolve(node.func)
        if returns and name in returns:
            return returns[name]
        if name in SDK_RETURNS:
            return SDK_RETURNS[name]
        if name == "range" and not node.keywords and 1 <= len(node.args) <= 3:
            args = [infer(a, facts, resolve, returns) for a in node.args]
            size = None
            if all(a.kind == "int" and a.value is not None for a in args):
                try:
                    size = len(range(*(a.value for a in args)))
                except (ValueError, OverflowError):
                    pass
            # Even arguments implementing __index__ produce exact integer items.
            # Invalid arguments raise before any loop body can execute.
            return Fact("range", item="int", size=size)
        if name == "abs" and len(node.args) == 1 and not node.keywords:
            return INT if infer(node.args[0], facts, resolve, returns).kind == "int" else UNKNOWN
        if name == "len" and len(node.args) == 1 and not node.keywords:
            # The builtin normalises __len__/__index__ results to an exact int.
            return INT
        if name == "tuple" and not node.keywords and len(node.args) <= 1:
            if not node.args:
                return Fact("tuple", size=0)
            iterable = infer(node.args[0], facts, resolve, returns)
            if iterable.kind in {"range", "tuple"}:
                return Fact("tuple", item=iterable.item, size=iterable.size)
        if isinstance(node.func, ast.Attribute):
            owner = infer(node.func.value, facts, resolve, returns).kind
            method = node.func.attr
            if owner == "board":
                if method == "positions":
                    return Fact("sequence", item="vec")
                if method in {"copy", "reachable_tiles", "shift_left", "shift_right", "shift_up", "shift_down"}:
                    return BOARD
                if method == "count":
                    return INT
            if owner == "champion" and method == "position":
                return VEC
            if owner == "field" and method == "get":
                return INT
            if owner == "vec" and method in {"chebyshev_distance", "length_squared", "dot"}:
                return INT
    return UNKNOWN


def pure_integer(node, facts, resolve):
    """Expressions safe to fully evaluate before a sum of exact integers."""
    if isinstance(node, ast.Name):
        return facts.get(node.id, UNKNOWN).kind == "int"
    if isinstance(node, ast.Constant):
        return type(node.value) is int
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)) and pure_integer(node.operand, facts, resolve)
    if isinstance(node, ast.BinOp):
        # Exclude division/modulo/shifts/powers: exceptions, float results or
        # unbounded intermediate allocations complicate eager evaluation.
        return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.BitAnd, ast.BitOr, ast.BitXor)) and all(
            pure_integer(part, facts, resolve) for part in (node.left, node.right)
        )
    return (isinstance(node, ast.Call) and resolve(node.func) == "abs"
            and not node.keywords and len(node.args) == 1
            and pure_integer(node.args[0], facts, resolve))


def pure_condition(node, facts, resolve):
    """Only total, callback-free integer predicates; preserve short circuiting."""
    if pure_integer(node, facts, resolve):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return pure_condition(node.operand, facts, resolve)
    if isinstance(node, ast.BoolOp):
        return all(pure_condition(value, facts, resolve) for value in node.values)
    return (isinstance(node, ast.Compare)
            and all(isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in node.ops)
            and all(pure_integer(value, facts, resolve) for value in [node.left, *node.comparators]))
