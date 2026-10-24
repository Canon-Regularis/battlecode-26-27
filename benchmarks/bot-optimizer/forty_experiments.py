"""Manual guarded candidates against the audited 30% compiler; not acceptance evidence."""

import argparse
import ast
import json
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import optimize_source
from tools.bot_optimizer.model import Options
from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.runtime import executable, run_command


def reduction_frames():
    old, new, cases = [], [], []
    for mode in ('globals', 'locals'):
        cls, kernel = f'Row_{mode}', f'kernel_{mode}'
        source = f'''from dataclasses import dataclass
@dataclass(frozen=True)
class {cls}:
    a: int
    b: int
    c: int
ROWS_{mode}=tuple({cls}(i,i+1,i+2) for i in range(32))
def {kernel}(rows, route):
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return a,b,c
'''
        baseline = optimize_source(source).source
        tree = ast.parse(baseline)
        function, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == kernel]
        body = f'''packed = None
if type(route) is tuple and len(route)<=16 and (type(rows) is list or type(rows) is tuple):
    aa=bb=cc=0
    index=row=x=y=z=None
    try:
        for index in route:
            if type(index) is not int:
                break
            try:
                row=rows[index]
            except IndexError:
                break
            if type(row) is not {cls}:
                break
            try:
                x,y,z=row.a,row.b,row.c
            except AttributeError:
                break
            if not (type(x) is type(y) is type(z) is int):
                break
            aa+=x
            bb+=y
            cc+=z
        else:
            packed=aa,bb,cc
    finally:
        del index,row,x,y,z,aa,bb,cc
if packed is None:
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
else:
    a,b,c=packed
del packed
return a,b,c
'''
        function.body = ast.parse(body).body
        if mode == 'locals':
            names = {'type', 'tuple', 'list', 'int', 'len'}
            class Rename(ast.NodeTransformer):
                def visit_Name(self,node):
                    if node.id in names:
                        node.id = '_inline_' + node.id
                    return node
            function.body = [Rename().visit(n) for n in function.body]
            function.body[:0] = ast.parse('\n'.join(f'_inline_{n}={n}' for n in sorted(names))).body
        candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_', f'_probe_{mode}_'))
        new.append(candidate.replace('_bcopt_', f'_probe_{mode}_'))
        for size in (0,1,4,8,10,16,32):
            case=f'reduction_{mode}_{size}'
            common=f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {kernel}(ROWS_{mode},ROUTE_{case})\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory=f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def product_sums():
    old,new,cases=[],[],[]
    for mode in ('globals','locals'):
        row,risk,kernel=f'Row_product_{mode}',f'Risk_{mode}',f'product_{mode}'
        source=f'''from dataclasses import dataclass
@dataclass(frozen=True)
class {row}:
    service: int
@dataclass(frozen=True)
class {risk}:
    weights: tuple
ROWS_product_{mode}=tuple({row}(i+1) for i in range(32))
RISK_{mode}={risk}(tuple(i/33 for i in range(32)))
def {kernel}(rows,route,risk):
    return sum(rows[index].service * risk.weights[index] for index in route)
'''
        baseline=optimize_source(source).source
        helper=f'guarded_product_{mode}'
        candidate=baseline+f'''\ndef {helper}(rows,route,risk):
    if type(route) is not tuple or len(route)>16 or not (type(rows) is tuple or type(rows) is list) or type(risk) is not {risk}:
        return None
    try:
        weights=risk.weights
    except AttributeError:
        return None
    if type(weights) is not tuple:
        return None
    values=[]
    for index in route:
        if type(index) is not int:
            return None
        try:
            row=rows[index]
        except IndexError:
            return None
        if type(row) is not {row}:
            return None
        try:
            value=row.service
            weight=weights[index]
        except (AttributeError,IndexError):
            return None
        if type(value) is not int or type(weight) is not float:
            return None
        try:
            values.append(value*weight)
        except OverflowError:
            return None
    return sum(values)
def {kernel}(rows,route,risk):
    result={helper}(rows,route,risk)
    if result is not None:
        return result
    return sum(rows[index].service*risk.weights[index] for index in route)
'''
        if mode=='locals':
            tree=ast.parse(candidate)
            function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==helper)
            for name in ('type','tuple','list','len','int','float','sum'):
                function.args.args.append(ast.arg(arg=name))
                function.args.defaults.append(ast.Name(id=name,ctx=ast.Load()))
            candidate=ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_',f'_probe_product_{mode}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_product_{mode}_'))
        for size in (0,1,4,8,10,16,32):
            case=f'product_{mode}_{size}'
            common=f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {kernel}(ROWS_product_{mode},ROUTE_{case},RISK_{mode})\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory=f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old),inventory+'\n'.join(new),cases


def fused_native():
    spec=importlib.util.spec_from_file_location('thirty_candidates',Path(__file__).with_name('thirty_experiments.py'))
    previous=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    old,new,cases=previous.fusion_sources()
    tree=ast.parse(new)
    for function in tree.body:
        if not isinstance(function,ast.FunctionDef) or function.name not in {'fused_gap','fused_adjacent'}:
            continue
        text=ast.unparse(function)
        text=text.replace('len(route) > 32','len(route) > 16')
        text=text.replace('    size = len(rows)\n','')
        text=text.replace(' or not -size <= i < size:',':')
        text=text.replace('        row = rows[i]\n',
            '        try:\n            row = rows[i]\n        except IndexError:\n            return None\n')
        function.body=ast.parse(text).body[0].body
        for name in ('type','list','tuple','int','len'):
            function.args.args.append(ast.arg(arg=name))
            function.args.defaults.append(ast.Name(id=name,ctx=ast.Load()))
    return old,ast.unparse(ast.fix_missing_locations(tree))+'\n',cases


def record_tags(fused=False):
    """Exploratory only: field-cache validity under reinitialization is not proved."""
    old,new,cases=fused_native()
    tree=ast.parse(new if fused else old)
    row=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Row')
    row.body.append(ast.parse('_probe_numeric_fields = False').body[0])
    initializer=next((n for n in row.body if isinstance(n,ast.FunctionDef) and n.name=='__init__'),None)
    if initializer is None:
        initializer=ast.parse('''def __init__(self,a,b,c,d):
    object.__setattr__(self,'a',a)
    object.__setattr__(self,'b',b)
    object.__setattr__(self,'c',c)
    object.__setattr__(self,'d',d)
''').body[0]
        row.body.append(initializer)
    initializer.body.extend(ast.parse('''if type(self) is __class__:
    object.__setattr__(self, '_probe_numeric_fields', type(self.a) is type(self.b) is type(self.c) is type(self.d) is int)
''').body)
    # Optimized warm fixtures construct through private factories, bypassing
    # __init__. Stamp those paths too; otherwise this measures only fallback.
    for function in tree.body:
        if not isinstance(function,ast.FunctionDef) or not function.name.startswith('_bcopt_make_record_'):
            continue
        result=function.body[-1]
        if not isinstance(result,ast.Return) or not isinstance(result.value,ast.Name):
            continue
        name=result.value.id
        function.body[-1:-1]=ast.parse(f"{name}.__dict__['_probe_numeric_fields'] = type(a) is type(b) is type(c) is type(d) is int").body
    replaced=0
    for function in tree.body:
        if not isinstance(function,ast.FunctionDef) or not (function.name.startswith('_bcopt_reduce_three_')
                or function.name in {'fused_gap','fused_adjacent'}):
            continue
        for node in ast.walk(function):
            if not isinstance(node,ast.If):continue
            names={n.id for n in ast.walk(node.test) if isinstance(n,ast.Name)}
            if {'x','y','z'} <= names:
                node.test=ast.parse('not row._probe_numeric_fields',mode='eval').body
                replaced+=1
    assert replaced
    new=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    extra=[]
    for gap in ('adjacent','gap'):
        for size in (1,8,16):
            case=f'cold_tag_{gap}_{size}'
            extra.append(f'''def {case}():
    rows=tuple(Row(i+1,i+2,i+3,i+4) for i in range({size}))
    return consume_{gap}(rows,tuple(range({size})),(1,)*({size}+1))
''')
            cases.append(case)
    # Both sources already have their original literal inventory. Replace it so
    # the guest runner sees the same enlarged set without executing fixtures.
    sources=[]
    for text in (old,new):
        module=ast.parse(text+'\n'.join(extra))
        inventory=next(n for n in module.body if isinstance(n,ast.Assign)
                       and any(isinstance(t,ast.Name) and t.id=='CASES' for t in n.targets))
        inventory.value=ast.parse(repr(tuple(cases)),mode='eval').body
        sources.append(ast.unparse(ast.fix_missing_locations(module))+'\n')
    return *sources,cases


def record_dicts():
    old,new,cases=[],[],[]
    for mode in ('profile','rows'):
        if mode=='profile':
            source='''from dataclasses import dataclass
@dataclass(frozen=True)
class Profile:
    camps: tuple
    altars: tuple
PROFILE=Profile(tuple(i/33 for i in range(32)),(0.5,))
def kernel_profile(route,profile):
    exposure=0.0
    for index in route:
        combined=profile.camps[index]+profile.altars[0]
        exposure+=combined*profile.camps[index]
    return exposure
'''
            baseline=optimize_source(source).source
            tree=ast.parse(baseline)
            function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='kernel_profile')
            original=function.body
            import copy
            class Fields(ast.NodeTransformer):
                def visit_Attribute(self,node):
                    if isinstance(node.value,ast.Name) and node.value.id=='profile':
                        return ast.Subscript(value=ast.Name(id='fields',ctx=ast.Load()),slice=ast.Constant(node.attr),ctx=ast.Load())
                    return self.generic_visit(node)
            fast=[Fields().visit(copy.deepcopy(n)) for n in original]
            function.body=ast.parse('''if type(profile) is Profile:
    fields=profile.__dict__
    if type(fields) is dict and 'camps' in fields and 'altars' in fields:
        try:
            pass
        finally:
            del fields
    del fields
''').body
            function.body[0].body[1].body[0].body=fast
            function.body.extend(original)
            candidate=ast.unparse(ast.fix_missing_locations(tree))+'\n'
        else:
            source='''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
ROWS=tuple(Row(i,i+1,i+2) for i in range(32))
def kernel_rows(rows,route):
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return a,b,c
'''
            baseline=optimize_source(source).source
            tree=ast.parse(baseline)
            for function in tree.body:
                if not isinstance(function,ast.FunctionDef) or not function.name.startswith('_bcopt_reduce_three_'):
                    continue
                text=ast.unparse(function)
                text=text.replace('        try:\n            x, y, z = (row.a, row.b, row.c)',
                    '        fields = row.__dict__\n        if type(fields) is not dict:\n            return None\n'
                    "        try:\n            x, y, z = fields['a'], fields['b'], fields['c']")
                text=text.replace('except _bcopt_reduce_AttributeError_0:', 'except KeyError:')
                function.body=ast.parse(text).body[0].body
            candidate=ast.unparse(ast.fix_missing_locations(tree))+'\n'
        old.append(baseline.replace('_bcopt_',f'_probe_dict_{mode}_'))
        new.append(candidate.replace('_bcopt_',f'_probe_dict_{mode}_'))
        for size in (0,1,4,8,10,16,32):
            case=f'dict_{mode}_{size}'
            call=f'kernel_profile(ROUTE_{case},PROFILE)' if mode=='profile' else f'kernel_rows(ROWS,ROUTE_{case})'
            common=f'ROUTE_{case}=tuple(range({size}))\ndef {case}():\n    return {call}\n'
            old.append(common)
            new.append(common)
            cases.append(case)
    inventory=f'CASES = {tuple(cases)!r}\n'
    return inventory+'\n'.join(old),inventory+'\n'.join(new),cases


def batch_regions():
    """Validation-inclusive callback-free region probe; no compiler integration."""
    source='''from dataclasses import dataclass
from math import ceil
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
    d: int
ROWS=tuple(Row(i+1,i+2,i+3,i+4) for i in range(24))
def consume(rows,route,legs):
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+c+tribute
    floor=max(rows[i].d+rows[i].c for i in route)
    return a,b,c,active,floor
def batch(rows,routes,legs):
    return tuple(consume(rows,route,legs) for route in routes)
'''
    old=optimize_source(source).source
    new=old+'''
def valid_region(rows,routes,legs,type=type,int=int,tuple=tuple,list=list,len=len):
    if not (type(rows) is tuple or type(rows) is list) or type(routes) is not tuple:
        return False
    if not (type(legs) is tuple or type(legs) is list):
        return False
    for value in legs:
        if type(value) is not int:
            return False
    for row in rows:
        if type(row) is not Row:
            return False
        try:
            a,b,c,d=row.a,row.b,row.c,row.d
        except AttributeError:
            return False
        if not type(a) is type(b) is type(c) is type(d) is int:
            return False
    size=len(rows)
    for route in routes:
        if type(route) is not tuple or not route:
            return False
        for index in route:
            if type(index) is not int or not -size <= index < size:
                return False
    return True
def consume_valid(rows,route,legs):
    a=b=c=0
    floor=None
    for index in route:
        row=rows[index]
        a+=row.a
        b+=row.b
        c+=row.c
        value=row.d+row.c
        if floor is None or value>floor:
            floor=value
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+c+tribute
    return a,b,c,active,floor
def batch(rows,routes,legs):
    if valid_region(rows,routes,legs):
        return tuple(consume_valid(rows,route,legs) for route in routes)
    return tuple(consume(rows,route,legs) for route in routes)
'''
    cases=[]
    for size in (4,8,16):
        for count in (1,4,8):
            name=f'region_{size}_{count}'
            common=f'''ROUTES_{name}=tuple(tuple((i+j)%24 for i in range({size})) for j in range({count}))
LEGS_{name}=(1,)*({size}+1)
def {name}():
    return batch(ROWS,ROUTES_{name},LEGS_{name})
'''
            old+=common
            new+=common
            cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def progressive_products():
    """Probe delayed native float sum with a one-shot non-float continuation."""
    old,new,cases=product_sums()
    tree=ast.parse(new)
    for mode in ('globals','locals'):
        name=f'product_{mode}'
        # Replace the last (candidate) definition; preserve the original helper
        # only as dead exploratory code, so baseline fixture names stay stable.
        function=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
        function.body=ast.parse(f'''if type(route) is not tuple or len(route)>16:
    return sum(rows[index].service*risk.weights[index] for index in route)
for index in route:
    if type(index) is not int:
        return sum(rows[index].service*risk.weights[index] for index in route)
values=[]
for position,index in enumerate(route):
    try:
        value=rows[index].service*risk.weights[index]
    except StopIteration as error:
        raise RuntimeError('generator raised StopIteration') from error
    if type(value) is not float:
        head=[value]
        del value
        return sum(chain(values,tail_{mode}(head,rows,route[position+1:],risk)))
    values.append(value)
return sum(values)
''').body
        if mode=='locals':
            for builtin in ('type','tuple','len','int','float','sum','enumerate'):
                function.args.args.append(ast.arg(arg=builtin))
                function.args.defaults.append(ast.Name(id=builtin,ctx=ast.Load()))
        tree.body.extend(ast.parse(f'''def tail_{mode}(head,rows,route,risk):
    yield head.pop()
    for index in route:
        yield rows[index].service*risk.weights[index]
''').body)
    tree.body.insert(0,ast.ImportFrom(module='itertools',names=[ast.alias(name='chain')],level=0))
    return old,ast.unparse(ast.fix_missing_locations(tree))+'\n',cases


def helper_regions(*, disable_guard_branches=False):
    """Compare shared boolean proofs with branch-specialized continuations."""
    source='''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
ROWS=tuple(Row(i,i+1,i+2) for i in range(16))
MATRIX=tuple(tuple(i+j for j in range(16)) for i in range(16))
def consume(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return legs,(a,b,c)
'''
    disabled={'immutable-helper-regions'}
    if disable_guard_branches:
        disabled.add('helper-guard-branches')
    old=optimize_source(source,Options(disabled=frozenset(disabled))).source
    tree=ast.parse(old)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    import copy
    branch=next(n for n in function.body if isinstance(n,ast.If)
                and isinstance(n.test,ast.UnaryOp) and isinstance(n.test.operand,ast.NamedExpr))
    flag=branch.test.operand.target.id
    class Specialize(ast.NodeTransformer):
        def __init__(self,truth):self.truth=truth
        def visit_IfExp(self,node):
            if isinstance(node.test,ast.Name) and node.test.id==flag:
                return node.body if self.truth else node.orelse
            return self.generic_visit(node)
    index=function.body.index(branch)
    tail=function.body[index+1:]
    branch.test.operand=branch.test.operand.value
    branch.body.extend(Specialize(False).visit(copy.deepcopy(n)) for n in tail)
    branch.orelse=[Specialize(True).visit(copy.deepcopy(n)) for n in tail]
    function.body=function.body[:index+1]
    new=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    cases=[]
    for size in (0,1,4,8,10,16):
        name=f'helper_region_{size}'
        common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return consume(ROWS,ROUTE_{name},MATRIX)\n'
        old+=common
        new+=common
        cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def helper_fusion():
    """Retest cross-gap fusion using the new cross-helper immutable proof."""
    source='''from dataclasses import dataclass
from math import ceil
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
    d: int
ROWS=tuple(Row(i,i+1,i+2,i+3) for i in range(32))
MATRIX=tuple(tuple(i+j for j in range(32)) for i in range(32))
def consume(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+c+tribute
    floor=max(rows[i].d+rows[i].c for i in route)
    return legs,(a,b,c,active,floor)
'''
    old=optimize_source(source,Options(disabled=frozenset({'immutable-helper-regions'}))).source
    tree=ast.parse(old)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    flag=function.body[1].test.operand.target.id
    begin=next(i for i,n in enumerate(function.body) if isinstance(n,ast.Assign)
               and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='tribute')
    maximum=next(i for i,n in enumerate(function.body) if isinstance(n,ast.Assign)
                 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='floor')
    decision=ast.parse('''if packed is None:
    pass
else:
    a,b,c,floor=packed
''').body[0]
    decision.body=function.body[2:begin]
    fallback=ast.If(test=ast.parse('packed is None',mode='eval').body,
                    body=[function.body[maximum]],orelse=[])
    function.body=[*function.body[:2],*ast.parse(f'packed=fused(rows,route,legs) if {flag} else None').body,
                   decision,*function.body[begin:maximum],fallback,*function.body[maximum+1:]]
    tree.body.extend(ast.parse('''def fused(rows,route,legs,type=type,int=int,list=list,tuple=tuple):
    if not (type(rows) is list or type(rows) is tuple) or not route:
        return None
    for value in legs:
        if type(value) is not int:
            return None
    a=b=c=0
    floor=None
    for index in route:
        try:
            row=rows[index]
        except IndexError:
            return None
        if type(row) is not Row:
            return None
        try:
            x,y,z,w=row.a,row.b,row.c,row.d
        except AttributeError:
            return None
        if not type(x) is type(y) is type(z) is type(w) is int:
            return None
        a+=x
        b+=y
        c+=z
        value=w+z
        if floor is None or value>floor:
            floor=value
    return a,b,c,floor
''').body)
    new=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    cases=[]
    for size in (1,4,8,10,16,32):
        name=f'helper_fusion_{size}'
        common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return consume(ROWS,ROUTE_{name},MATRIX)\n'
        old+=common
        new+=common
        cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def risk_regions():
    """Full guard/setup cost for a callback-free weighted-route region."""
    source='''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    service: int
@dataclass(frozen=True)
class Profile:
    weights: tuple
    altar: float
ROWS=tuple(Row(i+1) for i in range(32))
MATRIX=tuple(tuple(i+j+1 for j in range(32)) for i in range(32))
PROFILE=Profile(tuple(i/33 for i in range(32)),0.4)
def consume(rows,route,matrix,profile,legs,tribute,active,period):
    altar=profile.altar
    first,last=route[0],route[-1]
    exposure=legs[0]*(altar+profile.weights[first])/2
    exposure+=legs[1]*(profile.weights[last]+altar)/2
    for origin,destination in zip(route,route[1:]):
        combined=profile.weights[origin]+profile.weights[destination]
        exposure+=matrix[origin][destination]*combined/2
    exposure+=sum(rows[index].service*profile.weights[index] for index in route)
    exposure+=(tribute+period-active)*altar
    return min(1.0,max(0.0,exposure/period))
'''
    old=optimize_source(source).source
    tree=ast.parse(old)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    original=function.body
    function.body=ast.parse('''result=guarded_region(rows,route,matrix,profile,legs,tribute,active,period)
if result is not None:
    return result
''').body+original
    tree.body.extend(ast.parse('''def guarded_region(rows,route,matrix,profile,legs,tribute,active,period,
                   type=type,int=int,float=float,list=list,tuple=tuple,len=len):
    if type(route) is not tuple or not route or len(route)>16:
        return None
    if not (type(rows) is list or type(rows) is tuple) or not (type(matrix) is list or type(matrix) is tuple):
        return None
    if type(profile) is not Profile or not (type(legs) is list or type(legs) is tuple):
        return None
    if not type(tribute) is type(active) is type(period) is int:
        return None
    try:
        weights,altar=profile.weights,profile.altar
        first_leg,last_leg=legs[0],legs[1]
    except (AttributeError,IndexError):
        return None
    if type(weights) is not tuple or type(altar) is not float or not type(first_leg) is type(last_leg) is int:
        return None
    selected=[]
    services=[]
    edges=[]
    previous=None
    for index in route:
        if type(index) is not int:
            return None
        try:
            row=rows[index]
            weight=weights[index]
        except IndexError:
            return None
        if type(row) is not Row or type(weight) is not float:
            return None
        try:
            service=row.service
        except AttributeError:
            return None
        if type(service) is not int:
            return None
        selected.append(weight)
        services.append(service)
        if previous is not None:
            try:
                distances=matrix[previous]
            except IndexError:
                return None
            if not (type(distances) is tuple or type(distances) is list):
                return None
            try:
                distance=distances[index]
            except IndexError:
                return None
            if type(distance) is not int:
                return None
            edges.append(distance)
        previous=index
    exposure=first_leg*(altar+selected[0])/2
    exposure+=last_leg*(selected[-1]+altar)/2
    previous=selected[0]
    for distance,weight in zip(edges,selected[1:]):
        combined=previous+weight
        exposure+=distance*combined/2
        previous=weight
    exposure+=sum([service*weight for service,weight in zip(services,selected)])
    exposure+=(tribute+period-active)*altar
    value=exposure/period
    inner=value if value>0.0 else 0.0
    return inner if inner<1.0 else 1.0
''').body)
    new=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    cases=[]
    for size in (1,4,8,10,16,32):
        name=f'risk_region_{size}'
        common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return consume(ROWS,ROUTE_{name},MATRIX,PROFILE,(3,4),2,90,100)\n'
        old+=common
        new+=common
        cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def guard_branches():
    """Revisit pure type-guard branches now that helpers cache builtin aliases."""
    old,_,cases=helper_regions(disable_guard_branches=True)
    tree=ast.parse(old)
    import copy
    class Branches(ast.NodeTransformer):
        def visit_Compare(self,node):
            if (len(node.ops)==3 and all(isinstance(op,ast.Is) for op in node.ops)
                    and all(isinstance(value,ast.Call) for value in [node.left,*node.comparators[:-1]])
                    and isinstance(node.comparators[-1],ast.Name)
                    and node.comparators[-1].id.startswith('_bcopt_reduce_int_')):
                return ast.BoolOp(op=ast.And(),values=[ast.Compare(left=value,ops=[ast.Is()],
                    comparators=[copy.deepcopy(node.comparators[-1])])
                    for value in [node.left,*node.comparators[:-1]]])
            return self.generic_visit(node)
    tree=Branches().visit(tree)
    return old,ast.unparse(ast.fix_missing_locations(tree))+'\n',cases


def helper_bindings():
    """Compare per-call default binding with closure cells and packed defaults."""
    old, new, cases = [], [], []
    for mode in ('closure', 'packed'):
        baseline, _, inventory = helper_regions()
        tree = ast.parse(baseline)
        body = []
        for node in tree.body:
            if not (isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_')
                    and node.args.defaults):
                body.append(node)
                continue
            required = len(node.args.args) - len(node.args.defaults)
            args, defaults = node.args.args[required:], node.args.defaults
            node.args.args = node.args.args[:required]
            node.args.defaults = []
            if mode == 'closure':
                factory = ast.FunctionDef(name=node.name+'_bindings',
                    args=ast.arguments(posonlyargs=[], args=args, kwonlyargs=[], kw_defaults=[], defaults=defaults),
                    body=[node, ast.Return(value=ast.Name(id=node.name, ctx=ast.Load()))],
                    decorator_list=[])
                body.extend([factory, *ast.parse(f'{node.name}={factory.name}()\ndel {factory.name}').body])
            else:
                node.args.args.append(ast.arg(arg='_packed_builtins'))
                node.args.defaults.append(ast.Tuple(elts=defaults, ctx=ast.Load()))
                node.body.insert(0, ast.Assign(targets=[ast.Tuple(
                    elts=[ast.Name(id=arg.arg, ctx=ast.Store()) for arg in args],ctx=ast.Store())],
                    value=ast.Name(id='_packed_builtins',ctx=ast.Load())))
                body.append(node)
        tree.body = body
        candidate = ast.unparse(ast.fix_missing_locations(tree))+'\n'
        # Separate module-like namespaces so factories and fixtures do not collide.
        names = {n.id for n in ast.walk(ast.parse(baseline)) if isinstance(n, ast.Name)}
        names.update(n.name for n in ast.walk(ast.parse(baseline)) if isinstance(n,(ast.FunctionDef,ast.ClassDef)))
        def rename(text):
            def renamed(name):
                if name in names and (name.startswith('_bcopt_') or name in {'Row','ROWS','MATRIX','consume','CASES'} or name.startswith(('helper_region_', 'ROUTE_'))):
                    return name+'_'+mode
                return name
            class Rename(ast.NodeTransformer):
                def visit_Name(self,node):
                    node.id=renamed(node.id)
                    return node
                def visit_arg(self,node):
                    node.arg=renamed(node.arg)
                    return node
                def visit_alias(self,node):
                    if node.asname:node.asname=renamed(node.asname)
                    return node
                def visit_FunctionDef(self,node):
                    node=self.generic_visit(node)
                    node.name=renamed(node.name)
                    return node
                def visit_ClassDef(self,node):
                    node=self.generic_visit(node)
                    node.name=renamed(node.name)
                    return node
            # Include new factory names in the reference-renaming inventory.
            names.update(n.name for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef))
            return ast.unparse(ast.fix_missing_locations(Rename().visit(ast.parse(text))))+'\n'
        old.append(rename(baseline))
        new.append(rename(candidate))
        cases.extend(name+'_'+mode for name in inventory)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+'\n'.join(old), inventory+'\n'.join(new), cases


def mapped_products():
    """Probe lazy native map callbacks while retaining native compensated sum."""
    source='''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    service: int
ROWS=tuple(Row(i+1) for i in range(32))
WEIGHTS=tuple(i/33 for i in range(32))
def consume(rows,route,weights):
    return sum(rows[index].service*weights[index] for index in route)
'''
    old=optimize_source(source).source
    tree=ast.parse(old)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    original=function.body
    function.body=ast.parse('''if type(route) is tuple:
    def term(index):
        try:
            return rows[index].service*weights[index]
        except StopIteration as error:
            raise RuntimeError('generator raised StopIteration') from error
    try:
        return sum(map(term,route))
    finally:
        del term
''').body+original
    new=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    cases=[]
    for size in (0,1,4,8,10,16,32):
        name=f'mapped_product_{size}'
        common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return consume(ROWS,ROUTE_{name},WEIGHTS)\n'
        old+=common
        new+=common
        cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def scoring_regions():
    """Share validation/field loads across integer totals and weighted risk."""
    source='''from dataclasses import dataclass
from math import ceil
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    service: int
    respawn: int
@dataclass(frozen=True)
class Profile:
    weights: tuple
    altar: float
ROWS=tuple(Row(i+1,i+2,i+3,i+4) for i in range(32))
MATRIX=tuple(tuple(i+j+1 for j in range(32)) for i in range(32))
PROFILE=Profile(tuple(i/33 for i in range(32)),0.4)
def consume(rows,route,matrix,profile):
    legs=[3,4]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    if any(distance<0 for distance in legs):
        return None
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    service=sum(rows[i].service for i in route)
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+service+tribute
    floor=max(rows[i].respawn+rows[i].service for i in route)
    period=max(active,floor)
    first=active-legs[0]+2
    base=(a+0.02*b)/(period+0.15*first)
    altar=profile.altar
    exposure=legs[0]*(altar+profile.weights[route[0]])/2
    exposure+=legs[1]*(profile.weights[route[-1]]+altar)/2
    for origin,destination in zip(route,route[1:]):
        combined=profile.weights[origin]+profile.weights[destination]
        exposure+=matrix[origin][destination]*combined/2
    exposure+=sum(rows[i].service*profile.weights[i] for i in route)
    exposure+=(tribute+period-active)*altar
    risk=min(1.0,max(0.0,exposure/period))
    return a,b,service,period,risk,base*(1-0.8*risk)
'''
    old=optimize_source(source).source
    tree=ast.parse(source)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    function.body[3:3]=ast.parse('''packed=scoring_region(rows,route,matrix,profile,legs)
if packed is not None:
    return packed
''').body
    tree.body.extend(ast.parse('''def scoring_region(rows,route,matrix,profile,legs,
                   type=type,int=int,float=float,list=list,tuple=tuple,len=len):
    if type(route) is not tuple or not route or len(route)>16:
        return None
    if not (type(rows) is list or type(rows) is tuple) or not (type(matrix) is list or type(matrix) is tuple):
        return None
    if type(profile) is not Profile:
        return None
    try:
        weights,altar=profile.weights,profile.altar
    except AttributeError:
        return None
    if type(weights) is not tuple or type(altar) is not float:
        return None
    for leg in legs:
        if type(leg) is not int:
            return None
    selected=[]
    services=[]
    respawns=[]
    edges=[]
    previous=None
    a=b=service=0
    for index in route:
        if type(index) is not int:
            return None
        try:
            row=rows[index]
            weight=weights[index]
        except IndexError:
            return None
        if type(row) is not Row or type(weight) is not float:
            return None
        try:
            x,y,z,w=row.a,row.b,row.service,row.respawn
        except AttributeError:
            return None
        if not (type(x) is int and type(y) is int and type(z) is int and type(w) is int):
            return None
        a+=x
        b+=y
        service+=z
        selected.append(weight)
        services.append(z)
        respawns.append(w)
        if previous is not None:
            try:
                distances=matrix[previous]
            except IndexError:
                return None
            if not (type(distances) is tuple or type(distances) is list):
                return None
            try:
                distance=distances[index]
            except IndexError:
                return None
            if type(distance) is not int:
                return None
            edges.append(distance)
        previous=index
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+service+tribute
    floor=max([w+z for w,z in zip(respawns,services)])
    period=active if active>=floor else floor
    first=active-legs[0]+2
    base=(a+0.02*b)/(period+0.15*first)
    exposure=legs[0]*(altar+selected[0])/2
    exposure+=legs[1]*(selected[-1]+altar)/2
    previous=selected[0]
    for distance,weight in zip(edges,selected[1:]):
        combined=previous+weight
        exposure+=distance*combined/2
        previous=weight
    exposure+=sum([z*weight for z,weight in zip(services,selected)])
    exposure+=(tribute+period-active)*altar
    value=exposure/period
    inner=value if value>0.0 else 0.0
    risk=inner if inner<1.0 else 1.0
    return a,b,service,period,risk,base*(1-0.8*risk)
''').body)
    new=optimize_source(ast.unparse(ast.fix_missing_locations(tree))).source
    cases=[]
    for size in (1,4,8,10,16,32):
        name=f'scoring_region_{size}'
        common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return consume(ROWS,ROUTE_{name},MATRIX,PROFILE)\n'
        old+=common
        new+=common
        cases.append(name)
    inventory=f'CASES={tuple(cases)!r}\n'
    return inventory+old,inventory+new,cases


def snapshot_regions(counts=(1,8,64)):
    """Amortize a full primitive graph proof across a callback-free batch."""
    old,_,_=scoring_regions()
    # Retain the current compiler's baseline and append fresh batch fixtures.
    new=old+'''\n\ndef snapshot(rows,matrix,profile,type=type,int=int,float=float,list=list,tuple=tuple,len=len):
    if not (type(rows) is list or type(rows) is tuple) or not (type(matrix) is list or type(matrix) is tuple):
        return None
    if type(profile) is not Profile:
        return None
    try:
        weights,altar=profile.weights,profile.altar
    except AttributeError:
        return None
    if type(weights) is not tuple or type(altar) is not float or len(weights)!=len(rows) or len(matrix)!=len(rows):
        return None
    aa=[]
    bb=[]
    services=[]
    respawns=[]
    for row in rows:
        if type(row) is not Row:
            return None
        try:
            a,b,s,r=row.a,row.b,row.service,row.respawn
        except AttributeError:
            return None
        if not (type(a) is int and type(b) is int and type(s) is int and type(r) is int):
            return None
        aa.append(a)
        bb.append(b)
        services.append(s)
        respawns.append(r)
    for weight in weights:
        if type(weight) is not float:
            return None
    for distances in matrix:
        if not (type(distances) is list or type(distances) is tuple) or len(distances)!=len(rows):
            return None
        for distance in distances:
            if type(distance) is not int:
                return None
    return aa,bb,services,respawns,weights,altar

def fast_consume(route,matrix,data):
    aa,bb,services,respawns,weights,altar=data
    legs=[3,4]
    legs.extend([matrix[a][b] for a,b in zip(route,route[1:])])
    if any(distance<0 for distance in legs):
        return None
    a=sum([aa[i] for i in route])
    b=sum([bb[i] for i in route])
    service=sum([services[i] for i in route])
    tribute=ceil(a/10)
    travel=sum(legs)
    active=travel+service+tribute
    floor=max([respawns[i]+services[i] for i in route])
    period=active if active>=floor else floor
    first=active-legs[0]+2
    base=(a+0.02*b)/(period+0.15*first)
    exposure=legs[0]*(altar+weights[route[0]])/2
    exposure+=legs[1]*(weights[route[-1]]+altar)/2
    for origin,destination in zip(route,route[1:]):
        combined=weights[origin]+weights[destination]
        exposure+=matrix[origin][destination]*combined/2
    exposure+=sum([services[i]*weights[i] for i in route])
    exposure+=(tribute+period-active)*altar
    value=exposure/period
    inner=value if value>0.0 else 0.0
    risk=inner if inner<1.0 else 1.0
    return a,b,service,period,risk,base*(1-0.8*risk)

def batch(rows,route,matrix,profile,count):
    data=snapshot(rows,matrix,profile)
    if data is None or type(route) is not tuple or not all(type(index) is int and -len(rows)<=index<len(rows) for index in route):
        return [consume(rows,route,matrix,profile) for _ in range(count)]
    return [fast_consume(route,matrix,data) for _ in range(count)]
'''
    old+='''\n\ndef batch(rows,route,matrix,profile,count):
    return [consume(rows,route,matrix,profile) for _ in range(count)]
'''
    cases=[]
    for count in counts:
        for size in (4,8):
            name=f'snapshot_region_{count}_{size}'
            common=f'ROUTE_{name}=tuple(range({size}))\ndef {name}():\n    return batch(ROWS,ROUTE_{name},MATRIX,PROFILE,{count})\n'
            old+=common
            new+=common
            cases.append(name)
    # Last assignment replaces the scoring fixture inventory retained above.
    inventory=f'CASES={tuple(cases)!r}\n'
    return old+inventory,new+inventory,cases


def snapshot_fused(counts=(1,8,64)):
    """Keep one traversal of prevalidated numeric row tuples in the batch."""
    old,new,cases=snapshot_regions(counts)
    replacements={
        'return aa,bb,services,respawns,weights,altar':
            'return aa,bb,services,respawns,weights,altar,tuple(zip(aa,bb,services,respawns))',
        'aa,bb,services,respawns,weights,altar=data':
            'aa,bb,services,respawns,weights,altar,packed=data',
        '    a=sum([aa[i] for i in route])\n    b=sum([bb[i] for i in route])\n    service=sum([services[i] for i in route])':
            '''    a=b=service=0
    floor=None
    for index in route:
        x,y,z,w=packed[index]
        a+=x
        b+=y
        service+=z
        value=w+z
        if floor is None or value>floor:
            floor=value''',
        '    floor=max([respawns[i]+services[i] for i in route])':
            '    if floor is None:\n        floor=max(())',
    }
    for before,after in replacements.items():
        assert new.count(before)==1,before
        new=new.replace(before,after)
    return old,new,cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--focus',choices=('reduction-frames','product-sums','fused-native','record-tags','fused-tags','record-dicts','batch-regions','progressive-products','helper-regions','helper-fusion','risk-regions','guard-branches','helper-bindings','mapped-products','scoring-regions','snapshot-regions','snapshot-fused','snapshot-long'),default='reduction-frames')
    parser.add_argument('--measure-repeats',type=int,default=20)
    parser.add_argument('--warmups',type=int,default=20)
    parser.add_argument('--fuel',type=int,default=1_000_000_000)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    if args.measure_repeats<1 or args.warmups<0:
        parser.error('measure repeats must be positive and warmups nonnegative')
    old,new,cases={'reduction-frames':reduction_frames,'product-sums':product_sums,'fused-native':fused_native,
                   'record-tags':record_tags,'fused-tags':lambda:record_tags(True),'record-dicts':record_dicts,
                   'batch-regions':batch_regions,'progressive-products':progressive_products,
                   'helper-regions':helper_regions,'helper-fusion':helper_fusion,'risk-regions':risk_regions,
                   'guard-branches':guard_branches,'helper-bindings':helper_bindings,
                   'mapped-products':mapped_products,'scoring-regions':scoring_regions,
                   'snapshot-regions':snapshot_regions,'snapshot-fused':snapshot_fused,
                   'snapshot-long':lambda:snapshot_fused((128,512))}[args.focus]()
    src=args.output.resolve()/'bot/src'
    src.mkdir(parents=True)
    (src/'original.py').write_text(old)
    (src/'optimized.py').write_text(new)
    runner=Path(__file__).with_name('src').joinpath('main.py').read_text()
    runner=runner.replace('def measure(function, repeats=20):',f'def measure(function, repeats={args.measure_repeats}):')
    runner=runner.replace('for _ in range(20):',f'for _ in range({args.warmups}):')
    (src/'main.py').write_text(runner)
    report={'status':'running','manual_candidates':True,'datasets':[],
            'measure_repeats':args.measure_repeats,'warmups':args.warmups,'fuel':args.fuel}
    for game_map in ('collision','corners'):
        dest=args.output.resolve()/game_map
        run_command([executable(),'run',str(src.parent),str(src.parent),'--release','--rounds','1',
                     '--fuel',str(args.fuel),'--map',game_map,'--out-dir',str(dest)],timeout=300)
        replay,=dest.glob('*.repl26a')
        dataset=summarize(replay,cases)
        dataset['map']=game_map
        report['datasets'].append(dataset)
        for name,rows in dataset['pairs'].items():
            print(game_map,name,rows[0]['ratio'],flush=True)
        (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    report['status']='complete'
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
