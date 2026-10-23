"""Manual source alternatives for the30% target; not accepted compiler passes."""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.runtime import executable, run_command


def sources():
    old, new, cases = [], [], []
    for consumer, operation in (('min', '<'), ('max', '>')):
        new.append(f'''def pair_{consumer}(first, second):
    try:
        return second if second {operation} first else first
    except BaseException:
        del first, second
        raise
''')
        for tag, a, b in (('ints', '23', '17'), ('floats', '0.5', '1.0'),
                           ('zero', '-0.0', '0.0'), ('nan_first', "float('nan')", '0.5'),
                           ('nan_second', '0.5', "float('nan')")):
            name = f'pair_{consumer}_{tag}'
            setup = f'A_{name}, B_{name} = {a}, {b}\n'
            # repr makes NaN and signed-zero observations deterministic/equal.
            old.append(setup + f'def {name}():\n    return repr({consumer}(A_{name}, B_{name}))\n')
            new.append(setup + f'def {name}():\n    return repr(pair_{consumer}(A_{name}, B_{name}))\n')
            cases.append(name)
    for width in (2, 3, 4, 8, 12, 20):
        name, cls = f'inline_record_{width}', f'Row{width}'
        fields = [f'f{i}' for i in range(width)]
        definition = ('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass ' + cls + ':\n'
                      + ''.join(f'    {f}: object\n' for f in fields))
        prepare = f'def produce_{width}(seed):\n' + ''.join(f'    {f} = seed + {i}\n' for i, f in enumerate(fields))
        caller = f'def {name}():\n    row = produce_{width}(7)\n    return row.f0 + row.f{width-1}\n'
        baseline = optimize_source(definition + prepare + f'    return {cls}({", ".join(fields)})\n' + caller,
                                   Options(disabled=frozenset({'record-inline-return', 'extremum-loop'}))).source
        inline = (optimize_source(definition).source + f'NEW_{width} = object.__new__\n' + prepare
                  + f'    row = NEW_{width}({cls})\n    d = row.__dict__\n'
                  + ''.join(f'    d[{f!r}] = {f}\n' for f in fields)
                  + '    del d\n    return row\n' + caller)
        old.append(baseline.replace('_bcopt_', f'_probe_{width}_'))
        new.append(inline.replace('_bcopt_', f'_probe_{width}_'))
        cases.append(name)
    for consumer, operation in (('min', '<'), ('max', '>')):
        helper = f'indexed_{consumer}'
        new.append(f'''SENTINEL_{consumer} = object()
def {helper}(rows, route):
    if not (type(route) is tuple or type(route) is list):
        return {consumer}(rows[i][0] + rows[i][1] for i in route)
    best = SENTINEL_{consumer}
    for i in route:
        try:
            try:
                value = rows[i][0] + rows[i][1]
            except StopIteration as error:
                raise RuntimeError('generator raised StopIteration') from error
        except BaseException:
            del best
            raise
        try:
            if best is SENTINEL_{consumer} or value {operation} best:
                best = value
        except BaseException:
            del value, best, i
            raise
        del value
    if best is SENTINEL_{consumer}:
        raise ValueError('{consumer}() iterable argument is empty')
    return best
''')
        for size in (1, 4, 8, 16, 32):
            for numeric in ('int', 'float'):
                name = f'{helper}_{size}_{numeric}'
                setup = f'ROWS_{name} = tuple(({numeric}(i), {numeric}(i+1)) for i in range({size}))\nROUTE_{name} = tuple(range({size}))\n'
                old.append(setup + f'def {name}():\n    rows, route = ROWS_{name}, ROUTE_{name}\n    return {consumer}(rows[i][0] + rows[i][1] for i in route)\n')
                new.append(setup + f'def {name}():\n    rows, route = ROWS_{name}, ROUTE_{name}\n    return {helper}(rows, route)\n')
                cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def next_sources():
    old, new, cases = [], ['from itertools import pairwise\n'], []
    for consumer, operation in (('min', '<'), ('max', '>')):
        old.append(f'def choose_{consumer}(a, b):\n    return {consumer}(a, b)\n')
        new.append(f'def choose_{consumer}(a, b):\n    return b if b {operation} a else a\n')
        for tag, a, b in (('ints', '23', '17'), ('floats', '0.5', '1.0'),
                           ('zero', '-0.0', '0.0'), ('nan_first', "float('nan')", '0.5'),
                           ('nan_second', '0.5', "float('nan')")):
            name = f'inline_{consumer}_{tag}'
            source = (f'A_{name}, B_{name} = {a}, {b}\n'
                      f'def {name}():\n    return repr(choose_{consumer}(A_{name}, B_{name}))\n')
            old.append(source)
            new.append(source)
            cases.append(name)
    old.append('def clamp(x, y):\n    return min(1.0, max(0.0, x / y))\n')
    new.append('''def clamp(x, y):
    operand = x / y
    try:
        lower = operand if operand > 0.0 else 0.0
    finally:
        del operand
    try:
        return lower if lower < 1.0 else 1.0
    finally:
        del lower
''')
    for tag, x, y in (('below', '-1.0', '3.0'), ('within', '1.0', '3.0'),
                       ('above', '7.0', '3.0'), ('nan', "float('nan')", '1.0')):
        name = f'inline_clamp_{tag}'
        source = f'def {name}():\n    return repr(clamp({x}, {y}))\n'
        old.append(source)
        new.append(source)
        cases.append(name)
    for size in (0, 1, 4, 8, 16, 32):
        for strategy in ('native', 'indexed'):
            name = f'pairs_{size}_{strategy}'
            setup = f'ROUTE_{name} = tuple(range({size}))\n'
            common = f'def {name}():\n    route = ROUTE_{name}\n    total = 0\n'
            body = '        total += a + b\n    return total\n'
            old.append(setup + common + '    for a, b in zip(route, route[1:]):\n' + body)
            if strategy == 'native':
                loop = '    for a, b in (pairwise(route) if type(route) is tuple else zip(route, route[1:])):\n'
            else:
                loop = ('    if type(route) is not tuple:\n        return sum(a+b for a,b in zip(route,route[1:]))\n'
                        '    for index in range(len(route)-1):\n        a, b = route[index], route[index+1]\n')
            new.append(setup + common + loop + body)
            cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def kernel_sources():
    old, new, cases = [], ['from itertools import pairwise\nfrom operator import attrgetter\n'], []
    for width in (2, 3, 5, 12):
        for strategy in ('unpack', 'return'):
            name = f'attrs_{width}_{strategy}'
            fields = [f'f{i}' for i in range(width)]
            setup = (f'class Owner_{name}:\n    pass\nROW_{name} = Owner_{name}()\n'
                     + ''.join(f'ROW_{name}.{f} = {i}\n' for i, f in enumerate(fields)))
            old.append(setup)
            new.append(setup + f'GET_{name} = attrgetter({", ".join(repr(f) for f in fields)})\n')
            direct = ', '.join(f'row.{f}' for f in fields)
            native = f'GET_{name}(row)'
            common = f'def {name}():\n    row = ROW_{name}\n'
            if strategy == 'unpack':
                prefix = '    ' + ', '.join(fields) + ' = '
                end = f'\n    return f0 + f{width-1}\n'
            else:
                prefix, end = '    return ', '\n'
            old.append(common + prefix + direct + end)
            new.append(common + prefix + native + end)
            cases.append(name)
    for width in (3, 8, 12, 20):
        for strategy in ('update', 'keywords', 'zip'):
            name = f'fill_{width}_{strategy}'
            cls = 'Row_' + name
            fields = [f'f{i}' for i in range(width)]
            definition = ('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass ' + cls + ':\n'
                          + ''.join(f'    {f}: object\n' for f in fields))
            common = (definition + f'NEW_{name} = object.__new__\nKEYS_{name} = {tuple(fields)!r}\n'
                      f'def {name}():\n' + ''.join(f'    {f} = {i}\n' for i, f in enumerate(fields))
                      + f'    row = NEW_{name}({cls})\n    d = row.__dict__\n')
            end = f'    del d\n    return row.f0 + row.f{width-1}\n'
            old.append(common + ''.join(f'    d[{f!r}] = {f}\n' for f in fields) + end)
            if strategy == 'update':
                fill = '    d.update({' + ', '.join(f'{f!r}: {f}' for f in fields) + '})\n'
            elif strategy == 'keywords':
                fill = '    d.update(' + ', '.join(f'{f}={f}' for f in fields) + ')\n'
            else:
                fill = f'    d.update(zip(KEYS_{name}, ({", ".join(fields)})))\n'
            new.append(common + fill + end)
            cases.append(name)
    old.append('''def extend(target, rows, route):
    target.extend(rows[a][b] for a, b in zip(route, route[1:]))
''')
    for strategy in ('zip', 'pairwise', 'checked_pairwise', 'eager'):
        loop = 'zip(route, route[1:])' if strategy == 'zip' else 'pairwise(route)'
        if strategy == 'eager':
            new.append('''def extend_eager(target, rows, route):
    if type(target) is list and type(route) is tuple:
        target.extend([rows[a][b] for a,b in pairwise(route)])
    else:
        target.extend(rows[a][b] for a,b in zip(route, route[1:]))
''')
        else:
            guard = '''        index = None
        valid = True
        for index in route:
            if type(index) is not int:
                valid = False
                break
        del index
        if not valid:
            return target.extend(rows[a][b] for a,b in zip(route, route[1:]))
''' if strategy == 'checked_pairwise' else ''
            new.append(f'''def extend_{strategy}(target, rows, route):
    try:
        if type(target) is not list or type(route) is not tuple:
            return target.extend(rows[a][b] for a,b in zip(route, route[1:]))
{guard}        for a,b in {loop}:
            try:
                value = rows[a][b]
            except StopIteration as error:
                raise RuntimeError('generator raised StopIteration') from error
            target.append(value)
            del value
    finally:
        del target, route
''')
        for size in (1, 4, 8, 16, 32):
            name = f'extend_{size}_{strategy}'
            setup = f'ROUTE_{name} = tuple(range({size}))\nROWS_{name} = tuple(tuple(range({size})) for _ in range({size}))\n'
            common = f'def {name}():\n    target = [0,1]\n'
            end = '    return tuple(target)\n'
            old.append(setup + common + f'    extend(target, ROWS_{name}, ROUTE_{name})\n' + end)
            new.append(setup + common + f'    extend_{strategy}(target, ROWS_{name}, ROUTE_{name})\n' + end)
            cases.append(name)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def extension_sources():
    old, new, cases = kernel_sources()
    cases = [name for name in cases if name.startswith('extend_') and not name.endswith('eager')]
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + old.split('\n', 1)[1], inventory + new.split('\n', 1)[1], cases


def dispatch_sources():
    old, new, cases = [], [], []
    setup = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
ROWS = tuple(Row(i+1, i+2) for i in range(32))
WEIGHTS = tuple((i+1)/33 for i in range(32))
'''
    old.append(setup)
    new.append(setup)
    for consumer in ('sum', 'max'):
        for expression in ('rows[i].a * weights[i]', 'rows[i].a + rows[i].b'):
            tag = 'product' if '*' in expression else 'addition'
            name = f'consume_{consumer}_{tag}'
            old.append(f'def {name}(rows, weights, route):\n    return {consumer}({expression} for i in route)\n')
            new.append(f'''def {name}(rows, weights, route):
    if type(route) is not tuple:
        return {consumer}({expression} for i in route)
    def value(i):
        try:
            return {expression}
        except StopIteration as error:
            raise RuntimeError('generator raised StopIteration') from error
    return {consumer}(map(value, route))
''')
            for size in (1, 4, 8, 16, 32):
                case = f'map_{consumer}_{tag}_{size}'
                common = f'ROUTE_{case} = tuple(range({size}))\ndef {case}():\n    return {name}(ROWS, WEIGHTS, ROUTE_{case})\n'
                old.append(common)
                new.append(common)
                cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory + '\n'.join(old), inventory + '\n'.join(new), cases


def fusion_sources():
    definition = '''from dataclasses import dataclass
from math import ceil
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
    d: int
ROWS = tuple(Row(i+1,i+2,i+3,i+4) for i in range(32))
'''
    old, new, cases = [], [optimize_source(definition).source], []
    for gap in (False, True):
        tag = 'gap' if gap else 'adjacent'
        name = f'consume_{tag}'
        prefix = '''    a = sum(rows[i].a for i in route)
    b = sum(rows[i].b for i in route)
    c = sum(rows[i].c for i in route)
'''
        between = '    tribute = ceil(a/10)\n    travel = sum(legs)\n    active = travel + c + tribute\n' if gap else '    active = 0\n'
        maximum = '    floor = max(rows[i].d + rows[i].c for i in route)\n'
        end = '    return a,b,c,active,floor\n'
        old.append(f'def {name}(rows,route,legs):\n' + prefix + between + maximum + end)
        guard = '''    if not (type(legs) is list or type(legs) is tuple):
        return None
    for value in legs:
        if type(value) is not int:
            return None
''' if gap else ''
        new.append(f'''def fused_{tag}(rows,route,legs):
    if type(route) is not tuple or not route or len(route)>32 or not (type(rows) is list or type(rows) is tuple):
        return None
{guard}    size = len(rows)
    a=b=c=0
    best=None
    for i in route:
        if type(i) is not int or not -size <= i < size:
            return None
        row = rows[i]
        if type(row) is not Row:
            return None
        try:
            x,y,z,w = row.a,row.b,row.c,row.d
        except AttributeError:
            return None
        if not (type(x) is type(y) is type(z) is type(w) is int):
            return None
        a+=x
        b+=y
        c+=z
        value=w+z
        if best is None or value>best:
            best=value
    return a,b,c,best
''')
        new.append(f'def {name}(rows,route,legs):\n    totals = fused_{tag}(rows,route,legs)\n    if totals is None:\n'
                   + ''.join('    '+line+'\n' for line in prefix.splitlines())
                   + '    else:\n        a,b,c,floor = totals\n' + between
                   + '    if totals is None:\n' + '    '+maximum + end)
        for size in (1, 4, 8, 16, 32):
            case = f'fused_{tag}_{size}'
            common = f'ROUTE_{case} = tuple(range({size}))\nLEGS_{case} = (1,)*({size}+1)\ndef {case}():\n    return {name}(ROWS,ROUTE_{case},LEGS_{case})\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return (optimize_source(inventory + definition + '\n'.join(old)).source,
            optimize_source(inventory + '\n'.join(new)).source, cases)


def extension_fusion_sources():
    old, new, cases = [], [], []
    old.append('''def consume(rows,route):
    target = [1,2]
    target.extend(rows[a][b] for a,b in zip(route,route[1:]))
    if any(value < 0 for value in target):
        return None
    return tuple(target)
''')
    new.append('''from itertools import pairwise
def extend_checked(target,rows,route):
    if type(target) is not list or type(route) is not tuple or not (type(rows) is list or type(rows) is tuple):
        return None
    result = False
    for value in target:
        if type(value) is not int:
            return None
        if value < 0:
            result = True
    size = len(rows)
    for index in route:
        if type(index) is not int or not -size <= index < size:
            return None
    values = []
    for a,b in pairwise(route):
        row = rows[a]
        if not (type(row) is list or type(row) is tuple) or not -len(row) <= b < len(row):
            return None
        value = row[b]
        if type(value) is not int:
            return None
        values.append(value)
        if value < 0:
            result = True
    target.extend(values)
    return result

def consume(rows,route):
    target = [1,2]
    result = extend_checked(target,rows,route)
    if result is None:
        target.extend(rows[a][b] for a,b in zip(route,route[1:]))
    if result if result is not None else any(value < 0 for value in target):
        return None
    return tuple(target)
''')
    for size in (1, 4, 8, 16, 32):
        for negative in (False,True):
            case = f'extension_fused_{size}_{"negative" if negative else "positive"}'
            common = (f'ROUTE_{case} = tuple(range({size}))\n'
                      f'ROWS_{case} = tuple(tuple({-1 if negative else 1}*i for i in range({size})) for _ in range({size}))\n'
                      f'def {case}():\n    return consume(ROWS_{case},ROUTE_{case})\n')
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return optimize_source(inventory+'\n'.join(old)).source, optimize_source(inventory+'\n'.join(new)).source, cases


def cache_sources():
    old, new, cases = [], [], []
    for mode in ('type', 'defaults', 'locals'):
        for kind in ('sums', 'extremum', 'short', 'extend'):
            tag = f'{mode}_{kind}'
            cls, kernel = f'Row_{tag}', f'kernel_{tag}'
            setup = (f'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass {cls}:\n'
                     '    a: int\n    b: int\n    c: int\n'
                     f'ROWS_{tag} = tuple({cls}(i,i+1,i+2) for i in range(16))\n'
                     f'MATRIX_{tag} = tuple(tuple(range(16)) for _ in range(16))\n')
            body = {
                'sums': '    a=sum(rows[i].a for i in route)\n    b=sum(rows[i].b for i in route)\n    c=sum(rows[i].c for i in route)\n    return a,b,c\n',
                'extremum': '    return max(rows[i].a+rows[i].b for i in route)\n',
                'short': '    return any(i<0 for i in route)\n',
                'extend': '    target=[]\n    target.extend(rows[a][b] for a,b in zip(route,route[1:]))\n    return tuple(target)\n',
            }[kind]
            text = setup + f'def {kernel}(rows,route):\n' + body
            for size in (1, 4, 8, 10):
                case = f'cached_{tag}_{size}'
                rows = f'MATRIX_{tag}' if kind == 'extend' else f'ROWS_{tag}'
                text += f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {kernel}({rows},ROUTE_{case})\n'
                cases.append(case)
            baseline = optimize_source(text, Options(disabled=frozenset({'helper-builtin-cache', 'helper-loop-shape', 'native-index-guard', 'wide-helper-limit'}))).source
            tree = ast.parse(baseline)
            imports = {a.asname or a.name: a.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'builtins' for a in n.names}
            for function in tree.body:
                if not isinstance(function, ast.FunctionDef) or not function.name.startswith('_bcopt_'):
                    continue
                loaded = {n.id for statement in function.body for n in ast.walk(statement) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                names = sorted(name for name in loaded & imports.keys()
                               if imports[name] in ({'type'} if mode == 'type' else {'type','int','list','tuple','len'}))
                if mode != 'locals':
                    function.args.args.extend(ast.arg(arg=n) for n in names)
                    function.args.defaults.extend(ast.Name(id=n,ctx=ast.Load()) for n in names)
                else:
                    mapping = {n: n+'_local' for n in names}
                    class Rename(ast.NodeTransformer):
                        def visit_Name(self,node):
                            node.id = mapping.get(node.id,node.id)
                            return node
                    function.body = [Rename().visit(n) for n in function.body]
                    function.body[:0] = ast.parse('\n'.join(f'{mapping[n]} = {n}' for n in names)).body
            candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
            old.append(baseline.replace('_bcopt_', f'_probe_{tag}_'))
            new.append(candidate.replace('_bcopt_', f'_probe_{tag}_'))
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def loop_sources():
    old, new, cases = [], [], []
    for mode in ('bounds', 'checks', 'stores', 'combined', 'flag'):
        cls, kernel = f'Row_{mode}', f'kernel_{mode}'
        source = (f'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass {cls}:\n'
                  '    a: int\n    b: int\n    c: int\n'
                  f'ROWS_{mode} = tuple({cls}(i,i+1,i+2) for i in range(16))\n'
                  f'def {kernel}(rows,route):\n')
        if mode == 'flag':
            source += '    return max(rows[i].a+rows[i].b for i in route)\n'
        else:
            source += '    a=sum(rows[i].a for i in route)\n    b=sum(rows[i].b for i in route)\n    c=sum(rows[i].c for i in route)\n    return a,b,c\n'
        for size in (1, 4, 8, 10):
            name = f'loop_{mode}_{size}'
            source += f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return {kernel}(ROWS_{mode},ROUTE_{name})\n'
            cases.append(name)
        baseline = optimize_source(source, Options(disabled=frozenset({'helper-builtin-cache', 'helper-loop-shape', 'native-index-guard', 'wide-helper-limit'}))).source
        tree = ast.parse(baseline)
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            if function.name.startswith('_bcopt_reduce_three_'):
                text = ast.unparse(function)
                if mode in ('bounds','combined'):
                    text = text.replace('    a = b = c = 0', '    lower = -size\n    a = b = c = 0')
                    text = text.replace('not -size <= index < size', 'index < lower or index >= size')
                function.body = ast.parse(text).body[0].body
                if mode in ('checks','combined'):
                    class Checks(ast.NodeTransformer):
                        def visit_Compare(self,node):
                            if len(node.ops)==3 and all(isinstance(op,ast.Is) for op in node.ops):
                                return ast.BoolOp(op=ast.And(),values=[ast.Compare(left=value,ops=[ast.Is()],comparators=[node.comparators[-1]])
                                    for value in [node.left,*node.comparators[:-1]]])
                            return self.generic_visit(node)
                    function.body = [Checks().visit(n) for n in function.body]
                if mode in ('stores','combined'):
                    for loop in ast.walk(function):
                        if not isinstance(loop,ast.For):continue
                        for index in range(len(loop.body)-2):
                            statements = loop.body[index:index+3]
                            if all(isinstance(n,ast.AugAssign) and isinstance(n.op,ast.Add) for n in statements):
                                replacement = ast.parse('a, b, c = a + x, b + y, c + z').body
                                loop.body[index:index+3] = replacement
                                break
            if mode=='flag' and function.name.startswith('_bcopt_ext_max_'):
                sentinel = next(n.value.id for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='best' for t in n.targets))
                text = ast.unparse(function)
                text = text.replace(f'    best = {sentinel}', '    best = None\n    have_best = False')
                text = text.replace(f'            if best is {sentinel} or value > best:\n                best = value',
                                    '            if have_best:\n                if value > best:\n                    best = value\n            else:\n                best = value\n                have_best = True')
                text = text.replace(f'if best is {sentinel}:', 'if not have_best:')
                function.body = ast.parse(text).body[0].body
        candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_',f'_probe_{mode}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_{mode}_'))
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def indexing_sources():
    old, new, cases = [], [], []
    for mode in ('bounds-exception', 'bounds-exception-long', 'sums-long', 'extend-long'):
        tag = mode.replace('-', '_')
        cls, kernel = f'Row_{tag}', f'kernel_{tag}'
        source = (f'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass {cls}:\n'
                  '    a: int\n    b: int\n    c: int\n'
                  f'ROWS_{tag} = tuple({cls}(i,i+1,i+2) for i in range(32))\n'
                  f'MATRIX_{tag} = tuple(tuple(range(32)) for _ in range(32))\n'
                  f'def {kernel}(rows,route):\n')
        if mode == 'extend-long':
            source += '    target=[]\n    target.extend(rows[a][b] for a,b in zip(route,route[1:]))\n    return tuple(target)\n'
        else:
            source += '    a=sum(rows[i].a for i in route)\n    b=sum(rows[i].b for i in route)\n    c=sum(rows[i].c for i in route)\n    return a,b,c\n'
        for size in (1, 4, 8, 9, 10, 16, 32):
            name = f'indexing_{tag}_{size}'
            rows = f'MATRIX_{tag}' if mode == 'extend-long' else f'ROWS_{tag}'
            source += f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return {kernel}({rows},ROUTE_{name})\n'
            cases.append(name)
        baseline = optimize_source(source, Options(disabled=frozenset({'native-index-guard', 'wide-helper-limit'}))).source
        tree = ast.parse(baseline)
        for function in tree.body:
            if not isinstance(function,ast.FunctionDef) or not function.name.startswith(('_bcopt_reduce_three_', '_bcopt_extend_pairs_')):
                continue
            if mode.endswith('long'):
                for n in ast.walk(function):
                    if isinstance(n,ast.Compare) and len(n.ops)==1 and isinstance(n.ops[0],ast.Gt) and isinstance(n.comparators[0],ast.Constant) and n.comparators[0].value==8:
                        n.comparators[0].value=32
            if mode.startswith('bounds-exception'):
                function.body = [n for n in function.body if not (isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id in {'size','lower'} for t in n.targets))]
                for loop in ast.walk(function):
                    if not isinstance(loop,ast.For):continue
                    check = loop.body[0]
                    if isinstance(check,ast.If) and isinstance(check.test,ast.BoolOp):
                        check.test = check.test.values[0]
                    for index,n in enumerate(loop.body):
                        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='row' for t in n.targets):
                            loop.body[index] = ast.Try(body=[n],handlers=[ast.ExceptHandler(type=ast.Name(id='IndexError',ctx=ast.Load()),name=None,body=[ast.Return(value=ast.Constant(None))])],orelse=[],finalbody=[])
                            break
        candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_',f'_probe_{tag}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_{tag}_'))
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def insertion_sources():
    old, new, cases = [], [], []
    for mode in ('starred', 'scratch_delete', 'scratch_pop', 'scratch_move'):
        name = f'insert_{mode}'
        original = f'''def {name}(route,item):
    for position in range(len(route)+1):
        yield route[:position]+(item,)+route[position:]
'''
        old.append(original)
        prefix = f'''def {name}(route,item):
    if type(route) is not tuple:
        for position in range(len(route)+1):
            yield route[:position]+(item,)+route[position:]
        return
'''
        if mode=='starred':
            body = '''    for position in range(len(route)+1):
        yield (*route[:position],item,*route[position:])
'''
        elif mode=='scratch_move':
            body = '''    work = [item,*route]
    try:
        for position in range(len(route)+1):
            yield tuple(work)
            if position < len(route):
                work[position] = work[position+1]
                work[position+1] = item
    finally:
        del work
'''
        else:
            cleanup = 'del work[position]' if mode=='scratch_delete' else 'work.pop(position)'
            body = f'''    work = list(route)
    try:
        for position in range(len(route)+1):
            work.insert(position,item)
            yield tuple(work)
            {cleanup}
    finally:
        del work
'''
        new.append(prefix+body)
        for size in (0, 1, 4, 8, 10, 16):
            case = f'insertion_{mode}_{size}'
            common = f'ROUTE_{case} = tuple(range({size}))\ndef {case}():\n    return tuple({name}(ROUTE_{case},99))\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def refinement_sources():
    old, new, cases = [], [], []
    for mode in ('adj_slice', 'adj_iter', 'adj_index', 'insert_outer', 'max_first'):
        name = f'refine_{mode}'
        if mode.startswith('adj_'):
            prefix = f'from itertools import pairwise\ndef {name}(route):\n    result = 0.0\n'
            original = prefix + '''    for a,b in pairwise(route) if type(route) is tuple else zip(route,route[1:]):
        result += a * (a+b) / 2
    return result
'''
            body = {
                'adj_slice': '''        if len(route)>1:
            previous = route[0]
            try:
                for b in route[1:]:
                    a = previous
                    previous = b
                    result += a * (a+b) / 2
            finally:
                del previous
''',
                'adj_iter': '''        iterator = iter(route)
        previous = next(iterator, None)
        try:
            for b in iterator:
                a = previous
                previous = b
                result += a * (a+b) / 2
        finally:
            del previous, iterator
''',
                'adj_index': '''        try:
            for index in range(1,len(route)):
                a = route[index-1]
                b = route[index]
                result += a * (a+b) / 2
        finally:
            pass
''',
            }[mode]
            candidate = prefix + '    if type(route) is tuple:\n' + body + '''    else:
        for a,b in zip(route,route[1:]):
            result += a * (a+b) / 2
    return result
'''
        elif mode == 'insert_outer':
            original = f'''def {name}(route):
    exact = type(route) is tuple
    for item in range(20):
        if item in route:
            continue
        if exact:
            work = list(route)
            try:
                for position in range(len(route)+1):
                    work.insert(position,item)
                    yield tuple(work)
                    del work[position]
            finally:
                del work
        else:
            for position in range(len(route)+1):
                yield route[:position]+(item,)+route[position:]
'''
            candidate = f'''def {name}(route):
    exact = type(route) is tuple
    work = list(route) if exact else None
    try:
        for item in range(20):
            if item in route:
                continue
            if exact:
                for position in range(len(route)+1):
                    work.insert(position,item)
                    yield tuple(work)
                    del work[position]
            else:
                for position in range(len(route)+1):
                    yield route[:position]+(item,)+route[position:]
    finally:
        del work
'''
        else:
            source = f'''def {name}(route):
    return max(route[i]+route[i] for i in range(len(route)))
'''
            # Bind the route/index tuple explicitly so the ordinary direct-loop
            # pass recognizes the same shape as the planner's maximum.
            source = f'''def {name}(route):
    indices = tuple(range(len(route)))
    return max(route[i]+route[i] for i in indices)
'''
            original = optimize_source(source).source
            tree = ast.parse(original)
            for function in tree.body:
                if not isinstance(function, ast.FunctionDef) or not function.name.startswith('_bcopt_ext_max_'):
                    continue
                text = ast.unparse(function)
                text = text.replace('    best = None\n    have_best = False\n    for item in items:',
                    '    best = None\n    have_best = False\n    iterator = iter(items)\n    for item in iterator:')
                # Keep the full original expression/error cleanup in both loops.
                function.body = ast.parse(text).body[0].body
                loop = next(n for n in function.body if isinstance(n, ast.For))
                import copy
                remaining = copy.deepcopy(loop)
                selection = remaining.body[1].body[0]
                remaining.body[1].body = selection.body
                loop.body.append(ast.Break())
                end = function.body.index(loop)+1
                function.body.insert(end, remaining)
            candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(original.replace('_bcopt_',f'_probe_{mode}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_{mode}_'))
        for size in (1,4,8,10,16):
            case = f'{mode}_{size}'
            expression = f'tuple({name}(ROUTE_{case}))' if mode == 'insert_outer' else f'{name}(ROUTE_{case})'
            common = f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {expression}\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def vector_reduction_sources():
    old, new, cases = [], [], []
    for mode in ('identity', 'type_ids'):
        tag = f'vector_{mode}'
        cls, kernel = f'Row_{tag}', f'kernel_{tag}'
        source = f'''from dataclasses import dataclass
@dataclass(frozen=True)
class {cls}:
    a: int
    b: int
    c: int
ROWS_{tag}=tuple({cls}(i,i+1,i+2) for i in range(32))
def {kernel}(rows,route):
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return a,b,c
'''
        baseline = optimize_source(source).source
        tree = ast.parse(baseline)
        additions = ast.parse(f'''from operator import itemgetter as pick_{tag}, attrgetter as fields_{tag}, is_ as same_{tag}
from itertools import repeat as repeat_{tag}
fields_{tag} = fields_{tag}('a','b','c')
''').body
        def check(values, kind, size):
            if mode == 'identity':
                return f'all(map(same_{tag}, map(type, {values}), repeat_{tag}({kind})))'
            return f'tuple(map(id, map(type, {values}))) == (id({kind}),) * ({size})'
        for index,function in enumerate(tree.body):
            if not isinstance(function,ast.FunctionDef) or not function.name.startswith('_bcopt_reduce_three_'):
                continue
            replacement = f'''def {function.name}(rows,route,record,type=type,tuple=tuple,list=list,int=int,len=len,map=map,all=all,sum=sum,id=id,zip=zip):
    if type(route) is not tuple or not (type(rows) is list or type(rows) is tuple):
        return None
    size=len(route)
    if size>16:
        return None
    if size==0:
        return 0,0,0
    if not ({check('route','int','size')}):
        return None
    try:
        selected = pick_{tag}(*route)(rows) if size>1 else (rows[route[0]],)
    except IndexError:
        return None
    if not ({check('selected','record','size')}):
        return None
    try:
        a,b,c=zip(*map(fields_{tag},selected))
    except AttributeError:
        return None
    if not ({check('a+b+c','int','3*size')}):
        return None
    return sum(a),sum(b),sum(c)
'''
            tree.body[index] = ast.parse(replacement).body[0]
        tree.body[:0] = additions
        candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_',f'_probe_{tag}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_{tag}_'))
        for size in (0,1,4,8,10,16,32):
            case = f'{tag}_{size}'
            common = f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {kernel}(ROWS_{tag},ROUTE_{case})\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory = f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--focus', choices=('first', 'next', 'kernel', 'dispatch', 'extensions', 'fusion', 'extension-fusion', 'caches', 'loops', 'indexing', 'insertions', 'refinements', 'vector-reductions'), default='first')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    old, new, cases = {'first': sources, 'next': next_sources, 'kernel': kernel_sources,
                       'dispatch': dispatch_sources, 'extensions': extension_sources,
                       'fusion': fusion_sources, 'extension-fusion': extension_fusion_sources,
                       'caches': cache_sources, 'loops': loop_sources,
                        'indexing': indexing_sources, 'insertions': insertion_sources,
                        'refinements': refinement_sources, 'vector-reductions': vector_reduction_sources}[args.focus]()
    src = args.output.resolve() / 'bot/src'
    src.mkdir(parents=True)
    (src / 'original.py').write_text(old)
    (src / 'optimized.py').write_text(new)
    (src / 'main.py').write_text((Path(__file__).parent / 'src/main.py').read_text())
    report = {'status': 'running', 'manual_candidates': True, 'datasets': []}
    for game_map in ('collision', 'corners'):
        dest = args.output.resolve() / game_map
        run_command([executable(), 'run', str(src.parent), str(src.parent), '--release', '--rounds', '1',
                     '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
        replay, = dest.glob('*.repl26a')
        dataset = summarize(replay, cases)
        dataset['map'] = game_map
        report['datasets'].append(dataset)
        for name, rows in dataset['pairs'].items():
            print(game_map, name, rows[0]['ratio'], flush=True)
        (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
