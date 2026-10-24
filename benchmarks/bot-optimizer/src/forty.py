"""Guest witnesses for the next compiler iteration."""

import gc
from dataclasses import dataclass

CASES = ('nested_insertions', 'empty_outer', 'custom_route', 'close_cleanup',
         'throw_cleanup', 'exhaust_cleanup', 'iterator_error_cleanup',
         'shared_guard', 'shared_guard_fallback', 'shared_guard_mutation',
         'shared_guard_errors', 'shared_guard_rebinding', 'shared_guard_maximum',
         'shared_guard_maximum_error', 'static_shape_callbacks', 'static_shape_stop')


def insertions(route, items, make=None):
    token = make('token') if make is not None else None
    for item in items:
        for position in range(len(route)+1):
            yield route[:position]+(item,)+route[position:]


def nested_insertions():
    return tuple(insertions((1,3,5,7),(2,4,6)))


def empty_outer():
    return tuple(insertions((1,2),()))


def custom_route():
    events=[]
    class Route(tuple):
        def __getitem__(self,key):
            events.append(('get',repr(key)))
            return super().__getitem__(key)
        def __len__(self):
            events.append('len')
            return super().__len__()
    result=tuple(insertions(Route((1,2)),(3,4)))
    return result,tuple(events)


def lifetime(mode):
    events=[]
    class Value:
        def __init__(self,label):self.label=label
        def __del__(self):events.append(self.label)
    def items():
        yield Value('first')
        events.append('next-item')
        if mode=='iterator-error':
            raise ValueError('iterator')
        yield Value('second')
    gen=insertions((Value('a'),Value('b')),items(),Value)
    saved=row=None
    try:
        next(gen)
        if mode=='close':
            gen.close()
        elif mode=='throw':
            gen.throw(ValueError('injected'))
        else:
            for row in gen:
                pass
            row=None
    except ValueError as error:
        saved=error
    events.append('after')
    del gen,saved,row
    gc.collect()
    return tuple(events)


def close_cleanup():
    return lifetime('close')


def throw_cleanup():
    return lifetime('throw')


def exhaust_cleanup():
    return lifetime('exhaust')


def iterator_error_cleanup():
    return lifetime('iterator-error')


@dataclass(frozen=True)
class GuardRow:
    a: int
    b: int
    c: int


def guard_consume(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return legs,(a,b,c)


GUARD_ROWS=tuple(GuardRow(i,i+1,i+2) for i in range(16))
GUARD_MATRIX=tuple(tuple(i+j for j in range(16)) for i in range(16))


def shared_guard():
    return guard_consume(GUARD_ROWS,(0,1,2,3,4,5,6,7),GUARD_MATRIX)


def shared_guard_fallback():
    events=[]
    class Route(tuple):
        def __getitem__(self,key):
            events.append(repr(key))
            return super().__getitem__(key)
    return guard_consume(GUARD_ROWS,Route((0,1,2)),GUARD_MATRIX),tuple(events)


def shared_guard_mutation():
    events=[]
    rows=[GuardRow(1,2,3),GuardRow(4,5,6)]
    class Number:
        def __radd__(self,other):
            events.append('add')
            GuardRow.__init__(rows[1],4,99,6)
            return other+7
        def __del__(self):
            events.append('release-number')
    class Matrix:
        def __getitem__(self,index):
            events.append(('matrix',index))
            GuardRow.__init__(rows[0],Number(),2,3)
            return [1,1]
    value=guard_consume(rows,(0,1),Matrix())
    del rows[:]
    gc.collect()
    return value,tuple(events)


def shared_guard_errors():
    result=[]
    for route in ((99,),(0,99),(10**100,)):
        try:
            guard_consume(GUARD_ROWS,route,GUARD_MATRIX)
        except Exception as error:
            result.append((type(error).__name__,str(error)))
    return tuple(result)


def guard_rebind(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    route=(1,)
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return legs,(a,b,c)


def shared_guard_rebinding():
    return guard_rebind(GUARD_ROWS,(0,1,2),GUARD_MATRIX)


def guard_maximum(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    maximum=max(rows[i].a+rows[i].b for i in route)
    return maximum


def maximum_effects(fail):
    events=[]
    class Value:
        def __init__(self,label):self.label=label
        def __gt__(self,other):
            events.append(('compare',self.label,other.label))
            if fail:raise ValueError('comparison')
            return False
        def __del__(self):events.append(('release',self.label))
    class Operand:
        def __init__(self,label):self.label=label
        def __add__(self,other):
            events.append(('add',self.label))
            return Value(self.label)
    rows=[GuardRow(Operand('first'),0,0),GuardRow(Operand('second'),0,0)]
    saved=None
    try:
        result=guard_maximum(rows,(0,1),GUARD_MATRIX)
        events.append(('selected',result.label))
        del result
    except ValueError as error:
        saved=error
    events.append('after')
    del saved,rows
    gc.collect()
    return tuple(events)


def shared_guard_maximum():
    return maximum_effects(False)


def shared_guard_maximum_error():
    return maximum_effects(True)


def shape_consume(factory):
    values=[]
    alias=values
    values.append(factory(values))
    return any(value<0 for value in alias)


def shape_effects(fail):
    events=[]
    def factory(values):
        class Value:
            def __lt__(self,other):
                events.append('compare')
                if fail:raise StopIteration('comparison')
                values.append(-1)
                return False
            def __del__(self):events.append('release')
        return Value()
    saved=None
    try:
        value=shape_consume(factory)
    except RuntimeError as error:
        value=type(error).__name__,str(error),str(error.__cause__)
        saved=error
    events.append('after')
    del saved
    gc.collect()
    return value,tuple(events)


def static_shape_callbacks():
    return shape_effects(False)


def static_shape_stop():
    return shape_effects(True)
