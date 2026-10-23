"""Bind stable builtins in compiler-owned helpers without changing user APIs."""

import ast

from .model import Change


def cache_helper_builtins(body, aliases, selected, options, changes, line):
    if 'helper-builtin-cache' in options.disabled:
        return body
    for function in body:
        if not isinstance(function, ast.FunctionDef):
            continue
        loaded = {n.id for statement in function.body for n in ast.walk(statement)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        names = sorted(aliases[name] for name in selected if aliases[name] in loaded)
        if not names:
            continue
        # These are freshly generated private helpers, not source functions.
        # Their aliases were imported immediately before the helper definitions.
        before = ast.unparse(function)
        function.args.args.extend(ast.arg(arg=name) for name in names)
        function.args.defaults.extend(ast.Name(id=name, ctx=ast.Load()) for name in names)
        changes.append(Change('helper-builtin-cache', line, before, ast.unparse(function)))
    return body
