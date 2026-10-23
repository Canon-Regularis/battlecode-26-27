"""Fuel-motivated rewrites with explicit, conservative applicability checks."""

import ast
import copy

from .analysis import (
    Bindings, Fact, INT, UNKNOWN, annotation_fact, arguments, infer, pure_integer, pure_condition,
)
from .model import Change, Options


def method(receiver, name, *args):
    return ast.Call(func=ast.Attribute(value=receiver, attr=name, ctx=ast.Load()),
                    args=list(args), keywords=[])


def no_args(node, name):
    return (isinstance(node, ast.Call) and not node.args and not node.keywords
            and isinstance(node.func, ast.Attribute) and node.func.attr == name)


class Rewriter(ast.NodeTransformer):
    def __init__(self, options: Options, *, program=None, module="__bot__"):
        self.options = options
        self.program, self.module = program, module
        self.function_lines = []
        self.changes = []
        self.scopes = []
        self.facts = {}
        self.bindings = None
        self.helper_imports = {}
        self.helper_keys = {}
        self.state_masks = {}
        self.record_factories = {}
        self.used_names = set()

    def fresh_name(self, stem):
        index = 0
        while f"_bcopt_{stem}_{index}" in self.used_names:
            index += 1
        name = f"_bcopt_{stem}_{index}"
        self.used_names.add(name)
        return name

    def resolve(self, node):
        if isinstance(node, ast.Name):
            if node.id.startswith("__") and not node.id.endswith("__"):
                return None
            for scope in reversed(self.scopes):
                if node.id in scope:
                    value = scope[node.id]
                    return self.program.canonical(value) if self.program else value
            return node.id  # Unshadowed builtin (only whitelisted names used).
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and not node.attr.endswith("__"):
                return None
            owner = self.resolve(node.value)
            value = f"{owner}.{node.attr}" if owner else None
            return self.program.canonical(value) if self.program else value
        return None

    def fact(self, node):
        if self.program and "constant-facts" not in self.options.disabled:
            owner = self
            before = self.function_lines[-1] if self.function_lines else getattr(node, 'lineno', 0)

            class Constants(ast.NodeTransformer):
                def visit_Name(self, expression):
                    constant = owner.program.constants.get(owner.resolve(expression))
                    if constant and owner.program.available(owner.module, expression, before):
                        return ast.copy_location(ast.Constant(constant.value), expression)
                    return expression

                def visit_Attribute(self, expression):
                    replacement = self.visit_Name(expression)
                    return replacement if replacement is not expression else self.generic_visit(expression)

            # Only the analysis tree is substituted. Ordinary global reads stay
            # in generated code unless a specific pass proves their elimination.
            node = Constants().visit(copy.deepcopy(node))
        returns = (self.program.return_facts if self.program and
                   "return-shape" not in self.options.disabled else None)
        return infer(node, self.facts, self.resolve, returns)

    def change(self, name, old, new):
        if name in self.options.disabled:
            return old
        new = ast.copy_location(new, old)
        self.changes.append(Change(name, old.lineno, ast.unparse(old), ast.unparse(new)))
        return new

    def visit_Module(self, node):
        self.used_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        self.used_names.update(arg.arg for n in ast.walk(node)
                               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                               for arg in arguments(n))
        self.used_names.update(alias.asname or alias.name for n in ast.walk(node)
                               if isinstance(n, (ast.Import, ast.ImportFrom)) for alias in n.names)
        self.used_names.update(n.name for n in ast.walk(node)
                               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        self.used_names.update(n.name for n in ast.walk(node)
                               if isinstance(n, ast.ExceptHandler) and n.name)
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.used_names.update(Bindings(child.body).counts)
        self.bindings = Bindings(node.body)
        self.used_names.update(self.bindings.counts)
        if self.program:
            # Imported record fields can become helper parameters later. Reserve
            # all of them before choosing any shared factory/global alias.
            for record in self.program.records.values():
                self.used_names.update(record.fields)
        self.bindings.external.update(name for n in ast.walk(node) if isinstance(n, ast.Global)
                                      for name in n.names)
        scope = dict.fromkeys(self.bindings.counts)
        if self.program:
            scope.update({name: value for name, value in self.program.modules[self.module].symbols.items()
                          if name in scope})
        self.scopes.append(scope)
        node.body = [self.visit(statement) for statement in node.body]
        self.scopes.pop()
        # _operator is built into the pinned interpreter; a bot's operator.py
        # must not shadow the native helpers we introduce.
        helpers = [ast.ImportFrom(module="_operator", names=[ast.alias(name=kind, asname=alias)], level=0)
                   for kind, alias in self.helper_imports.items()]
        helpers.extend(ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=ast.Call(
            func=ast.Name(id=self.helper_imports[kind], ctx=ast.Load()),
            args=[ast.Constant(value=part) for part in value], keywords=[],
        )) for (kind, value), name in self.helper_keys.items())
        if self.record_factories:
            helpers.append(ast.ImportFrom(module="builtins", names=[ast.alias(
                name="object", asname=self.factory_object)], level=0))
            allocator = f"{self.factory_object}.__new__"
            if "record-allocator-cache" not in self.options.disabled:
                cached = self.fresh_name("new")
                helpers.extend(ast.parse(f"{cached} = {allocator}").body)
                allocator = cached
            for fields, (factory, cls, row, dictionary) in self.record_factories.items():
                source = (f"def {factory}({cls}, {', '.join(fields)}):\n"
                          f"    {row} = {allocator}({cls})\n"
                          f"    {dictionary} = {row}.__dict__\n")
                source += ''.join(f"    {dictionary}[{field!r}] = {field}\n" for field in fields)
                source += f"    return {row}\n"
                helpers.extend(ast.parse(source).body)
        if hasattr(self, "state_helper"):
            helpers.append(ast.ImportFrom(module="cambc", names=[ast.alias(
                name="ChampionState", asname=self.state_helper)], level=0))
            for flags, alias in self.state_masks.items():
                parts = [ast.Attribute(value=ast.Name(id=self.state_helper, ctx=ast.Load()),
                                       attr=flag, ctx=ast.Load()) for flag in flags]
                value = parts[0]
                for part in parts[1:]:
                    value = ast.BinOp(left=value, op=ast.BitOr(), right=part)
                helpers.append(ast.Assign(targets=[ast.Name(id=alias, ctx=ast.Store())], value=ast.Call(
                    func=ast.Name(id=self.state_helper, ctx=ast.Load()), args=[value], keywords=[])))
        index = 0
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            index = 1
        while index < len(node.body) and isinstance(node.body[index], ast.ImportFrom) and node.body[index].module == "__future__":
            index += 1
        node.body[index:index] = helpers
        return node

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.facts.pop(name, None)
            if self.bindings.counts[name] == 1 and name not in self.bindings.external:
                self.scopes[-1][name] = alias.name if alias.asname else name
        return node

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.facts.pop(name, None)
            if self.bindings.counts[name] == 1 and name not in self.bindings.external and not node.level:
                self.scopes[-1][name] = f"{node.module}.{alias.name}"
            elif (self.program and len(self.scopes) == 1 and node.level
                  and self.bindings.counts[name] == 1 and name not in self.bindings.external):
                self.scopes[-1][name] = self.program.modules[self.module].symbols.get(name)
        return node

    def visit_FunctionDef(self, node):
        self.forget_writes([node])
        if node.type_params:
            # PEP 695 introduces an additional annotation/type-parameter scope.
            return node
        saved_facts, saved_bindings = self.facts, self.bindings
        self.bindings = Bindings(node.body)
        scope = dict.fromkeys(self.bindings.counts.keys() | self.bindings.external)
        scope.update(dict.fromkeys(arg.arg for arg in arguments(node)))
        self.scopes.append(scope)
        self.function_lines.append(node.lineno)
        self.facts = {}
        # A nested closure can mutate its parent's locals through nonlocal.
        escaped = {name for child in ast.walk(node) if isinstance(child, ast.Nonlocal)
                   for name in child.names}
        self.bindings.external.update(escaped)
        if self.options.trust_annotations:
            for arg in arguments(node):
                if arg.annotation and arg.arg not in self.bindings.external:
                    self.facts[arg.arg] = annotation_fact(arg.annotation, self.resolve)
        node.body = [self.visit(statement) for statement in node.body]
        self.scopes.pop()
        self.function_lines.pop()
        self.facts, self.bindings = saved_facts, saved_bindings
        return node

    def visit_AsyncFunctionDef(self, node):
        # Await/scheduling boundaries require a different lifetime analysis.
        self.forget_writes([node])
        return node

    def visit_ClassDef(self, node):
        self.forget_writes([node])
        if node.type_params:
            return node
        # Methods skip their class namespace when resolving free variables.
        # Leave class-level expressions/defaults alone, but optimise method bodies
        # using only the surrounding module/function lexical scopes.
        for index, statement in enumerate(node.body):
            if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
                node.body[index] = self.visit(statement)
        return node

    def visit_Lambda(self, node):
        self.forget_writes([ast.Expr(value=node)])
        return node

    def assign(self, target, value):
        if isinstance(target, ast.Name):
            if target.id not in self.bindings.external:
                self.facts[target.id] = value
        elif isinstance(target, (ast.List, ast.Tuple)):
            for item in target.elts:
                self.assign(item, UNKNOWN)

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        value = self.fact(node.value)
        for target in node.targets:
            self.visit(target)
            self.assign(target, value)
        return node

    def visit_AnnAssign(self, node):
        if node.value is not None:
            node.value = self.visit(node.value)
            self.visit(node.target)
            self.assign(node.target, self.fact(node.value))
        else:
            self.visit(node.target)
        self.forget_writes([ast.Expr(value=node.annotation)])
        return node

    def visit_AugAssign(self, node):
        node.target = self.visit(node.target)
        node.value = self.visit(node.value)
        value = infer(ast.BinOp(left=node.target, op=node.op, right=node.value), self.facts, self.resolve)
        self.assign(node.target, value)
        return node

    def forget_writes(self, statements):
        bindings = Bindings(statements)
        for name in bindings.counts.keys() | bindings.external:
            self.facts.pop(name, None)

    def visit_Delete(self, node):
        for target in node.targets:
            self.visit(target)
            self.assign(target, UNKNOWN)
        return node

    def visit_If(self, node):
        node.test = self.visit(node.test)
        before = self.facts.copy()
        node.body = [self.visit(s) for s in node.body]
        first = self.facts
        self.facts = before.copy()
        node.orelse = [self.visit(s) for s in node.orelse]
        self.facts = {k: v for k, v in first.items() if self.facts.get(k) == v}
        return node

    def visit_BoolOp(self, node):
        flags = {
            "can_move": "CAN_MOVE", "can_attack": "CAN_ATTACK", "can_cast": "CAN_CAST",
            "is_recalling": "RECALLING", "is_submitting_gems": "SUBMITTING_GEMS",
            "is_teleporting": "TELEPORTING", "has_completed_turn": "COMPLETED_TURN",
        }
        calls = []

        def eligible(expression):
            if isinstance(expression, ast.BoolOp):
                return all(eligible(value) for value in expression.values)
            if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
                return eligible(expression.operand)
            if isinstance(expression, ast.Constant):
                return type(expression.value) in {bool, int, type(None)}
            if (isinstance(expression, ast.Call) and not expression.args and not expression.keywords
                    and isinstance(expression.func, ast.Attribute) and isinstance(expression.func.value, ast.Name)
                    and self.fact(expression.func.value).kind == "champion"
                    and expression.func.attr in {*flags, "is_alive"}):
                calls.append(expression)
                return True
            return False

        if ("sdk-state-expression" in self.options.disabled
                or (self.program and "cambc" in self.program.modules) or not eligible(node)
                or len({call.func.value.id for call in calls}) != 1
                or sum(call.func.attr in flags for call in calls) < 2):
            return self.generic_visit(node)
        local = self.fresh_name("state")
        # A private import alias avoids shadowed cambc/ChampionState names. It is
        # generated only after profitability (at least one dominated reuse).
        flag_owner = getattr(self, "state_helper", None) or self.fresh_name("ChampionState")
        reuse = 0

        def snapshot(receiver, defined):
            nonlocal reuse
            state = ast.Name(id=local, ctx=ast.Load())
            if not defined:
                state = ast.NamedExpr(target=ast.Name(id=local, ctx=ast.Store()),
                                      value=method(copy.deepcopy(receiver), "state"))
            else:
                reuse += 1
            return state

        def predicate(value):
            positive = True
            if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
                positive, value = False, value.operand
            if isinstance(value, ast.Call) and value.func.attr in flags:
                return positive, value
            return None

        def rewrite(expression, defined):
            nonlocal reuse
            if isinstance(expression, ast.BoolOp):
                result = copy.deepcopy(expression)
                result.values = []
                first_defined = defined
                index = 0
                while index < len(expression.values):
                    start = index
                    value = expression.values[index]
                    first = predicate(value)
                    group = [first] if first else []
                    if first and "sdk-state-mask" not in self.options.disabled:
                        for following in expression.values[index + 1:]:
                            item = predicate(following)
                            if item is None or item[0] != first[0]:
                                break
                            group.append(item)
                    if len(group) >= 2:
                        token = tuple(flags[item[1].func.attr] for item in group)
                        if token not in self.state_masks:
                            self.state_masks[token] = self.fresh_name("state_flags")
                        mask = ast.Name(id=self.state_masks[token], ctx=ast.Load())
                        state = snapshot(first[1].func.value, defined)
                        # Positive AND / negative OR need all flags; positive
                        # OR / negative AND need any flag. Leaves are bools and
                        # read-only SDK predicates, never arbitrary callbacks.
                        any_flags = isinstance(expression.op, ast.Or) == first[0]
                        value = (method(state, "intersects", mask) if any_flags else
                                 ast.Compare(left=mask, ops=[ast.In()], comparators=[state]))
                        if not first[0]:
                            value = ast.UnaryOp(op=ast.Not(), operand=value)
                        original = ast.copy_location(ast.BoolOp(op=copy.deepcopy(expression.op),
                            values=copy.deepcopy(expression.values[index:index + len(group)])), expression)
                        value = self.change("sdk-state-mask", original, ast.fix_missing_locations(value))
                        reuse += len(group) - 1
                        defined = True
                        index += len(group)
                    else:
                        value, defined = rewrite(value, defined)
                        index += 1
                    result.values.append(value)
                    if start == 0:
                        first_defined = defined
                # Later operands may be skipped. Only definitions guaranteed by
                # the first operand dominate a use outside this boolean node.
                return (result.values[0] if len(result.values) == 1 else result), first_defined
            if isinstance(expression, ast.UnaryOp):
                operand, defined = rewrite(expression.operand, defined)
                return ast.UnaryOp(op=ast.Not(), operand=operand), defined
            if isinstance(expression, ast.Call) and expression.func.attr in flags:
                state = snapshot(expression.func.value, defined)
                flag = ast.Attribute(value=ast.Name(id=flag_owner, ctx=ast.Load()),
                                     attr=flags[expression.func.attr], ctx=ast.Load())
                return ast.Compare(left=flag, ops=[ast.In()], comparators=[state]), True
            return copy.deepcopy(expression), defined

        result, _ = rewrite(node, False)
        if not reuse:
            return self.generic_visit(node)
        # Use a separate helper inventory: operator constructors are unrelated.
        self.state_helper = flag_owner
        return self.change("sdk-state-expression", node, ast.fix_missing_locations(result))

    def visit_For(self, node):
        node.iter = self.visit(node.iter)
        iterable = self.fact(node.iter)
        stable = self.loop_integer_facts(node)
        self.forget_writes([node])
        self.facts.update(stable)
        # Mutating the induction variable inside the body invalidates its type
        # on subsequent expressions/iterations, unless a new assignment proves it.
        writes = Bindings(node.body).counts
        if isinstance(node.target, ast.Name) and node.target.id not in writes and iterable.kind in {"range", "tuple"}:
            self.assign(node.target, Fact(iterable.item))
        node.body = [self.visit(s) for s in node.body]
        self.forget_writes([node])
        self.facts.update(stable)
        node.orelse = [self.visit(s) for s in node.orelse]
        self.forget_writes([node])
        self.facts.update(stable)
        return node

    def loop_integer_facts(self, node):
        """Retain already-bound ints only if every loop write preserves exact int."""
        if "loop-integer-facts" in self.options.disabled:
            return {}
        parts = list(ast.walk(node))
        if any(isinstance(part, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                                 ast.NamedExpr, ast.Global, ast.Nonlocal)) for part in parts):
            return {}
        written = Bindings([node]).counts
        stable = {name: INT for name, fact in self.facts.items()
                  if fact.kind == 'int' and name in written and name not in self.bindings.external}
        untouched = {name: fact for name, fact in self.facts.items() if name not in written}
        while stable:
            removed = set()
            for name in stable:
                stores = {id(part) for part in parts if isinstance(part, ast.Name)
                          and part.id == name and isinstance(part.ctx, (ast.Store, ast.Del))}
                allowed = set()
                for part in parts:
                    if isinstance(part, (ast.Assign, ast.AnnAssign)):
                        targets = part.targets if isinstance(part, ast.Assign) else [part.target]
                        if pure_integer(part.value, {**untouched, **stable}, self.resolve):
                            allowed.update(id(t) for t in targets if isinstance(t, ast.Name) and t.id == name)
                    elif (isinstance(part, ast.AugAssign) and isinstance(part.target, ast.Name)
                          and part.target.id == name and isinstance(part.op, (ast.Add, ast.Sub, ast.Mult,
                                                                             ast.BitOr, ast.BitAnd, ast.BitXor))
                          and pure_integer(part.value, {**untouched, **stable}, self.resolve)):
                        allowed.add(id(part.target))
                if stores != allowed or len(stores) != written[name]:
                    removed.add(name)
            if not removed:
                break
            stable = {name: fact for name, fact in stable.items() if name not in removed}
        return stable

    def visit_While(self, node):
        stable = self.loop_integer_facts(node)
        self.forget_writes([node])
        self.facts.update(stable)
        node.test = self.visit(node.test)
        node.body = [self.visit(s) for s in node.body]
        self.forget_writes([node])
        self.facts.update(stable)
        node.orelse = [self.visit(s) for s in node.orelse]
        self.forget_writes([node])
        self.facts.update(stable)
        return node

    def visit_Try(self, node):
        # Exception edges can expose intermediate assignments. Optimise each
        # straight-line region with no incoming facts; never merge across edges.
        for name in ("body", "handlers", "orelse", "finalbody"):
            self.facts = {}
            values = getattr(node, name)
            rewritten = []
            for statement in values:
                if name == "handlers":
                    self.facts = {}
                rewritten.append(self.visit(statement))
            setattr(node, name, rewritten)
        self.facts = {}
        return node

    visit_TryStar = visit_Try

    def visit_With(self, node):
        # __enter__/__exit__ may have arbitrary effects.
        self.facts = {}
        for item in node.items:
            item.context_expr = self.visit(item.context_expr)
        node.body = [self.visit(s) for s in node.body]
        self.facts = {}
        return node

    def visit_Match(self, node):
        self.facts = {}
        node.subject = self.visit(node.subject)
        for case in node.cases:
            self.facts = {}
            if case.guard:
                case.guard = self.visit(case.guard)
            case.body = [self.visit(s) for s in case.body]
        self.facts = {}
        return node

    def visit_NamedExpr(self, node):
        node.value = self.visit(node.value)
        self.assign(node.target, UNKNOWN)
        return node

    def visit_comprehension_expression(self, node):
        # Only the first iterable executes in the enclosing scope.
        node.generators[0].iter = self.visit(node.generators[0].iter)
        first_iterable = self.fact(node.generators[0].iter)
        saved = self.facts.copy()
        bound = {n.id for gen in node.generators for n in ast.walk(gen.target)
                 if isinstance(n, ast.Name)}
        self.scopes.append(dict.fromkeys(bound))
        # A generator body can run after captured locals have been rebound.
        if isinstance(node, ast.GeneratorExp):
            self.facts = {}
        else:
            self.facts = {k: v for k, v in self.facts.items() if k not in bound}
        for index, gen in enumerate(node.generators):
            if index:
                gen.iter = self.visit(gen.iter)
            value = first_iterable if index == 0 else self.fact(gen.iter)
            self.assign(gen.target, Fact(value.item) if value.kind in {"range", "tuple"} else UNKNOWN)
            gen.ifs = [self.visit(condition) for condition in gen.ifs]
        if isinstance(node, ast.DictComp):
            node.key, node.value = self.visit(node.key), self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self.scopes.pop()
        self.facts = saved
        for child in ast.walk(node):
            if isinstance(child, ast.NamedExpr):
                self.assign(child.target, UNKNOWN)
        return node

    visit_GeneratorExp = visit_comprehension_expression
    visit_SetComp = visit_comprehension_expression
    visit_DictComp = visit_comprehension_expression

    def visit_ListComp(self, node):
        node = self.visit_comprehension_expression(node)
        pair = self.mask_pair(node)
        if pair and isinstance(node.elt, ast.Name) and node.elt.id == pair[2]:
            intersection = ast.BinOp(left=pair[0], op=ast.BitAnd(), right=pair[1])
            return self.change("mask-filter", node, method(intersection, "positions"))
        return node

    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if (isinstance(node.op, ast.Mod) and self.fact(node.left).kind == 'int'
                and isinstance(node.right, (ast.Constant, ast.Name, ast.Attribute))):
            divisor = self.fact(node.right)
            value = divisor.value
            if (divisor.kind == 'int' and type(value) is int and 2 <= value <= 1 << 30
                    and value & (value - 1) == 0):
                return self.change('integer-mod-mask', node, ast.BinOp(
                    left=node.left, op=ast.BitAnd(), right=ast.Constant(value - 1)))
        if (isinstance(node.op, ast.Pow) and isinstance(node.left, ast.Name)
                and isinstance(node.right, ast.Constant) and type(node.right.value) is int
                and node.right.value == 2 and self.fact(node.left).kind == "int"):
            return self.change("integer-square", node, ast.BinOp(
                left=node.left, op=ast.Mult(), right=copy.deepcopy(node.left),
            ))
        return node

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        if (len(node.ops) != 1 or not isinstance(node.ops[0], (ast.In, ast.NotIn))
                or self.fact(node.left).kind != "int"):
            return node
        table = node.comparators[0]
        if (not isinstance(table, (ast.List, ast.Tuple))
                or not 4 <= len(table.elts) <= self.options.max_materialize):
            return node
        try:
            values = [ast.literal_eval(value) for value in table.elts]
        except (ValueError, TypeError, SyntaxError):
            return node
        if any(type(value) is not int for value in values):
            return node
        # CPython folds a constant set used by CONTAINS_OP to a frozenset. No
        # runtime set allocation/hoisting and no hash callbacks on exact ints.
        result = copy.deepcopy(node)
        result.comparators = [ast.Set(elts=[ast.Constant(value=value) for value in values])]
        return self.change("integer-membership", node, result)

    def mask_pair(self, node):
        if len(node.generators) != 1:
            return None
        gen = node.generators[0]
        if (gen.is_async or not isinstance(gen.target, ast.Name) or len(gen.ifs) != 1
                or not no_args(gen.iter, "positions")):
            return None
        left = gen.iter.func.value
        condition = gen.ifs[0]
        if not (isinstance(condition, ast.Call) and isinstance(condition.func, ast.Attribute)
                and condition.func.attr == "is_set" and not condition.keywords
                and len(condition.args) == 1 and isinstance(condition.args[0], ast.Name)
                and condition.args[0].id == gen.target.id):
            return None
        right = condition.func.value
        if not (isinstance(left, ast.Name) and isinstance(right, ast.Name)
                and gen.target.id not in {left.id, right.id}
                and self.fact(left).kind == self.fact(right).kind == "board"):
            return None
        return left, right, gen.target.id

    def visit_Call(self, node):
        node = self.generic_visit(node)
        node = self.positional_call(node)
        inline = self.inline_helper(node)
        if inline is not node:
            return self.visit(inline)
        constructed = self.record_call(node)
        if constructed is not node:
            return constructed
        name = self.resolve(node.func)
        mapped = self.native_map_consumer(node, name)
        if mapped is not node:
            return mapped
        identity = self.identity_reduction(node, name)
        if identity is not node:
            return identity
        if not node.keywords and len(node.args) == 1:
            argument = node.args[0]
            if name in {"len", "bool"} and no_args(argument, "positions"):
                board = argument.func.value
                if self.fact(board).kind == "board":
                    if name == "len":
                        return self.change("mask-count", node, method(board, "count"))
                    return self.change("mask-empty", node, ast.UnaryOp(
                        op=ast.Not(), operand=method(board, "is_empty"),
                    ))
            if name == "sum" and isinstance(argument, ast.GeneratorExp):
                pair = self.mask_pair(argument)
                if pair and isinstance(argument.elt, ast.Constant) and type(argument.elt.value) is int and argument.elt.value == 1:
                    intersection = ast.BinOp(left=pair[0], op=ast.BitAnd(), right=pair[1])
                    return self.change("mask-intersection-count", node, method(intersection, "count"))
                return self.integer_sum(node, argument)
        if name in {"min", "max", "sorted"}:
            bounded = self.bounded_extremum(node, name)
            if bounded is not node:
                return bounded
            replacement = self.operator_key(node)
            if replacement is not node:
                return replacement
            return self.native_key(node)
        # list.sort has the same key contract; require exact provenance from a
        # list literal or SDK positions() (not an arbitrary user sort method).
        if (isinstance(node.func, ast.Attribute) and node.func.attr == "sort"
                and self.fact(node.func.value).kind == "sequence" and not node.args):
            return self.operator_key(node)
        return node

    def positional_call(self, node):
        if not self.program or not node.keywords or "call-positional" in self.options.disabled:
            return node
        if any(kw.arg and kw.arg.startswith("__") and not kw.arg.endswith("__") for kw in node.keywords):
            return node
        signature = self.program.signatures.get(self.resolve(node.func))
        if signature is None or signature.bind(node) is None:
            return node
        count = 0
        for keyword in node.keywords:
            position = len(node.args) + count
            if (position >= len(signature.positional) or position < signature.posonly
                    or keyword.arg != signature.positional[position]):
                break
            count += 1
        if not count:
            return node
        result = copy.deepcopy(node)
        result.args.extend(keyword.value for keyword in result.keywords[:count])
        result.keywords = result.keywords[count:]
        return self.change("call-positional", node, result)

    def record_call(self, node):
        if not self.program:
            return node
        record = self.program.records.get(self.resolve(node.func))
        if record is None or not record.frozen or not record.simple:
            return node
        width = len(record.fields)
        if (2 <= width <= 3 and (width < self.options.min_bulk_fields
                                or "record-bulk-init" in self.options.disabled)):
            pass_name = "small-record-call"
        elif 4 <= width <= 20 and "record-allocator-cache" not in self.options.disabled:
            # Larger uncached factories lost to the guarded initializer. A
            # prebound allocator reverses that result in the measured range.
            pass_name = "record-call"
        else:
            return node
        if pass_name in self.options.disabled:
            return node
        before = self.function_lines[-1] if self.function_lines else node.lineno
        if not self.program.available(self.module, node.func, before):
            return node
        bound = record.signature.bind(node)
        if bound is None or set(bound) != set(record.fields):
            return node
        # Only direct calls to an exact, hook-free source record qualify. The
        # newly allocated object cannot have an existing dictionary alias or old
        # fields/finalizers. Public construction and subclass initialization stay
        # untouched. The original class lookup is still evaluated before args.
        self.used_names.update(record.fields)
        if not self.record_factories:
            self.factory_object = self.fresh_name("object")
        if record.fields not in self.record_factories:
            self.record_factories[record.fields] = tuple(self.fresh_name(stem) for stem in
                                                        ("make_record", "class", "record", "dict"))
        factory = self.record_factories[record.fields][0]
        result = copy.deepcopy(node)
        result.func = ast.Name(id=factory, ctx=ast.Load())
        result.args.insert(0, copy.deepcopy(node.func))
        return self.change(pass_name, node, result)

    def inline_helper(self, node):
        if not self.program or "inline-integer-helper" in self.options.disabled:
            return node
        if any(kw.arg and kw.arg.startswith("__") and not kw.arg.endswith("__") for kw in node.keywords):
            return node
        function = self.program.functions.get(self.resolve(node.func))
        if function is None or function.expression is None:
            return node
        before = self.function_lines[-1] if self.function_lines else node.lineno
        if not self.program.available(self.module, node.func, before):
            return node
        bound = function.signature.bind(node)
        if bound is None or set(bound) != set(function.signature.positional) | set(function.signature.kwonly):
            return node
        if any(not isinstance(value, (ast.Name, ast.Constant)) or self.fact(value).kind != "int"
               for value in bound.values()):
            return node

        class Substitute(ast.NodeTransformer):
            def visit_Name(self, name):
                return ast.copy_location(copy.deepcopy(bound[name.id]), name)

        expression = Substitute().visit(copy.deepcopy(function.expression))
        return self.change("inline-integer-helper", node, expression)

    def identity_reduction(self, node, name):
        if (name not in {"sum", "min", "max", "any", "all"} or len(node.args) != 1
                or any(kw.arg != "default" or not isinstance(kw.value, ast.Constant) for kw in node.keywords)
                or (node.keywords and name not in {"min", "max"})):
            return node
        gen = node.args[0]
        if not isinstance(gen, ast.GeneratorExp) or len(gen.generators) != 1:
            return node
        loop = gen.generators[0]
        if (loop.is_async or loop.ifs or not isinstance(loop.target, ast.Name)
                or not isinstance(gen.elt, ast.Name) or gen.elt.id != loop.target.id):
            return node
        result = copy.deepcopy(node)
        result.args = [copy.deepcopy(loop.iter)]
        # sum/min/max/any/all do not consult length hints, unlike list/tuple/set/
        # sorted. Keep those consumers out of this general streaming rewrite.
        return self.change("identity-reduction", node, result)

    def bounded_extremum(self, node, name):
        if (name not in {"min", "max"} or len(node.args) != 1
                or any(kw.arg != "default" or not isinstance(kw.value, ast.Constant) for kw in node.keywords)):
            return node
        gen = node.args[0]
        if not isinstance(gen, ast.GeneratorExp) or len(gen.generators) != 1:
            return node
        return self.materialize_reduction(node, gen, "bounded-reduction")

    def materialize_reduction(self, call, gen, pass_name):
        loop = gen.generators[0]
        if loop.is_async or not isinstance(loop.target, ast.Name):
            return call
        iterable = self.fact(loop.iter)
        if iterable.kind not in {"range", "tuple"} or iterable.item != "int":
            return call
        facts = {**self.facts, loop.target.id: INT}
        if (not pure_integer(gen.elt, facts, self.resolve)
                or not all(pure_condition(test, facts, self.resolve) for test in loop.ifs)):
            return call
        result = copy.deepcopy(call)
        result.args = [ast.ListComp(elt=copy.deepcopy(gen.elt), generators=copy.deepcopy(gen.generators))]
        if iterable.size is not None:
            if iterable.size > self.options.max_materialize:
                return call
        elif (iterable.kind == "tuple" and isinstance(loop.iter, ast.Name)
              and self.options.max_materialize > 0 and self.resolve(ast.Name(id="len")) == "len"):
            result = ast.IfExp(test=ast.Compare(
                left=ast.Call(func=ast.Name(id="len", ctx=ast.Load()),
                              args=[copy.deepcopy(loop.iter)], keywords=[]),
                ops=[ast.LtE()], comparators=[ast.Constant(self.options.max_materialize)],
            ), body=result, orelse=copy.deepcopy(call))
        else:
            return call
        return self.change(pass_name, call, result)

    def operator_key(self, node):
        key = next((kw for kw in node.keywords if kw.arg == "key"), None)
        if key is None or not isinstance(key.value, ast.Lambda):
            return node
        callback = key.value
        args = callback.args
        if (len(args.args) != 1 or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
                or args.defaults or any(kw.arg is None for kw in node.keywords)):
            return node
        name = args.args[0].arg
        def extract(body):
            if (isinstance(body, ast.Subscript) and isinstance(body.value, ast.Name) and body.value.id == name
                    and isinstance(body.slice, ast.Constant) and type(body.slice.value) in {int, str}):
                return "itemgetter", body.slice.value, "native-itemgetter"
            path = []
            while isinstance(body, ast.Attribute):
                # A string passed to attrgetter does not undergo class-name
                # mangling the way an attribute expression in a lambda does.
                if body.attr.startswith("__") and not body.attr.endswith("__"):
                    return None
                path.append(body.attr)
                body = body.value
            if not path or not isinstance(body, ast.Name) or body.id != name:
                return None
            return "attrgetter", ".".join(reversed(path)), "native-attrgetter"

        body = callback.body
        # Multi-getters return a tuple and retain left-to-right access order.
        # A one-element tuple must stay a tuple, not become a scalar getter.
        parts = body.elts if isinstance(body, ast.Tuple) and len(body.elts) >= 2 else [body]
        extracted = [extract(part) for part in parts]
        if any(part is None for part in extracted) or len({part[0] for part in extracted}) != 1:
            return node
        kind, _, pass_name = extracted[0]
        value = tuple(part[1] for part in extracted)
        if pass_name in self.options.disabled:
            return node
        if kind not in self.helper_imports:
            self.helper_imports[kind] = self.fresh_name(kind)
        token = (kind, value)
        if token not in self.helper_keys:
            self.helper_keys[token] = self.fresh_name("key")
        replacement = copy.deepcopy(node)
        next(kw for kw in replacement.keywords if kw.arg == "key").value = ast.Name(
            id=self.helper_keys[token], ctx=ast.Load(),
        )
        return self.change(pass_name, node, replacement)

    def integer_sum(self, call, gen):
        if len(gen.generators) != 1:
            return call
        loop = gen.generators[0]
        if loop.is_async or not isinstance(loop.target, ast.Name):
            return call
        iterable = self.fact(loop.iter)
        # Exact range has stable immutable integer elements. Lists can be mutated
        # by aliases, so their contents are not trusted here.
        if iterable.kind not in {"range", "tuple"} or iterable.item != "int":
            return call
        return self.materialize_reduction(call, gen, "bounded-sum" if iterable.kind == "range" else "bounded-reduction")

    def native_map_consumer(self, call, name):
        if (name not in {"sum", "min", "max", "any", "all", "list", "tuple"}
                or len(call.args) != 1 or "native-map" in self.options.disabled
                or self.resolve(ast.Name(id="map")) != "map"
                or any(kw.arg != "default" or not isinstance(kw.value, ast.Constant) for kw in call.keywords)
                or (call.keywords and name not in {"min", "max"})):
            return call
        gen = call.args[0]
        if not isinstance(gen, ast.GeneratorExp) or len(gen.generators) != 1:
            return call
        loop, expression = gen.generators[0], gen.elt
        if (loop.is_async or loop.ifs or not isinstance(loop.target, ast.Name) or loop.target.id == "abs"
                or not isinstance(expression, ast.Call) or self.resolve(expression.func) != "abs"
                or expression.keywords or len(expression.args) != 1
                or not isinstance(expression.args[0], ast.Name) or expression.args[0].id != loop.target.id):
            return call
        iterable = self.fact(loop.iter)
        # Exact integers cannot run callbacks or raise StopIteration in abs.
        # General objects could: map would then silently stop where a generator
        # raises RuntimeError (PEP 479). Never infer this from the callback alone.
        if iterable.kind not in {"range", "tuple"} or iterable.item != "int":
            return call
        result = copy.deepcopy(call)
        result.args = [ast.Call(func=ast.Name(id="map", ctx=ast.Load()),
                               args=[copy.deepcopy(expression.func), copy.deepcopy(loop.iter)], keywords=[])]
        return self.change("native-map", call, result)

    def native_key(self, node):
        if len(node.args) != 1 or any(kw.arg not in {"key", "default", "reverse"} for kw in node.keywords):
            return node
        # Iterating a freshly materialised SDK position list cannot run Python
        # callbacks that rebind the lambda's captured field.
        iterable = node.args[0]
        if not no_args(iterable, "positions") or self.fact(iterable.func.value).kind != "board":
            return node
        key = next((kw for kw in node.keywords if kw.arg == "key"), None)
        if key is None or not isinstance(key.value, ast.Lambda):
            return node
        callback = key.value
        args = callback.args
        if (len(args.args) != 1 or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
                or args.defaults or not isinstance(callback.body, ast.Call)):
            return node
        body = callback.body
        if (body.keywords or len(body.args) != 1 or not isinstance(body.args[0], ast.Name)
                or body.args[0].id != args.args[0].arg or not isinstance(body.func, ast.Attribute)
                or not isinstance(body.func.value, ast.Name)
                or body.func.value.id == args.args[0].arg):
            return node
        receiver = self.fact(body.func.value).kind
        if (receiver, body.func.attr) not in {("field", "get"), ("vec", "chebyshev_distance")}:
            return node
        # Restrict other keyword values to inert constants. Otherwise moving
        # method lookup earlier could change exception/side-effect ordering.
        if any(kw is not key and not isinstance(kw.value, ast.Constant) for kw in node.keywords):
            return node
        replacement = copy.deepcopy(node)
        next(kw for kw in replacement.keywords if kw.arg == "key").value = copy.deepcopy(body.func)
        return self.change("native-key", node, replacement)
