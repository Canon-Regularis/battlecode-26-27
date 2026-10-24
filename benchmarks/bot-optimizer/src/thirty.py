"""Generated allocation-preserving returns and extrema with lifetime witnesses."""

from dataclasses import dataclass
import gc

CASES = ('allocation', 'shared_key_finalizers', 'maximum_four', 'minimum_four',
         'maximum_sixteen', 'nan_first', 'iterator_protocol', 'keep', 'replace',
         'comparison_stop', 'comparison_error', 'boolean_stop', 'boolean_error',
         'expression_stop', 'expression_error',
         'scalar_clamp', 'scalar_keep', 'scalar_replace', 'scalar_bool_error',
          'tuple_pairs', 'list_pairs', 'boolean_traceback_cleanup',
          'extension_values', 'extension_mutation', 'extension_error', 'extension_stop',
          'extension_index_finalizers', 'insertion_empty', 'insertion_four', 'insertion_ten',
          'insertion_close', 'insertion_throw', 'insertion_stop', 'insertion_custom',
          'adjacent_return_cleanup', 'adjacent_exception_cleanup')


@dataclass(frozen=True)
class Row:
    a: object
    b: object
    c: object
    d: object


@dataclass(frozen=True)
class SeedRow:
    a: object
    b: object
    c: object
    d: object


def make(a, b, c, d):
    return Row(a, b, c, d)


def make_seed(a, b, c, d):
    return SeedRow(a, b, c, d)


def allocation():
    row = make(1, 2, 3, 4)
    return row.a + row.d


def shared_key_finalizers():
    seed = object.__new__(SeedRow)
    for name in 'dbac':
        object.__setattr__(seed, name, 0)
    del seed
    events = []
    class Item:
        def __init__(self, label):
            self.label = label
        def __del__(self):
            events.append(self.label)
    row = make_seed(Item('a'), Item('b'), Item('c'), Item('d'))
    del row
    return tuple(events)


def maximum(rows, route):
    return max(rows[i][0] + rows[i][1] for i in route)


def minimum(rows, route):
    return min(rows[i][0] + rows[i][1] for i in route)


ROWS = tuple((i, i + 1) for i in range(16))
FOUR = tuple(range(4))
SIXTEEN = tuple(range(16))


def maximum_four():
    return maximum(ROWS, FOUR)


def minimum_four():
    return minimum(ROWS, FOUR)


def maximum_sixteen():
    return maximum(ROWS, SIXTEEN)


def nan_first():
    return repr(maximum(((float('nan'), 0), (1., 0)), (0, 1)))


def iterator_protocol():
    events = []
    class Route:
        def __init__(self):
            self.index = 0
        def __iter__(self):
            events.append('iter')
            return self
        def __next__(self):
            events.append('next')
            self.index += 1
            if self.index > 2:
                raise StopIteration
            return self.index - 1
    result = maximum(ROWS, Route())
    return result, tuple(events)


def lifetime(mode):
    events = []
    class Truth:
        def __bool__(self):
            events.append('bool')
            if mode == 'bool-stop':
                raise StopIteration('bool')
            if mode == 'bool-error':
                raise ValueError('bool')
            return mode == 'replace'
        def __del__(self):
            events.append('truth-del')
    class Value:
        def __init__(self, index):
            self.index = index
        def __gt__(self, other):
            events.append(('gt', self.index, other.index))
            if mode == 'compare-stop':
                raise StopIteration('comparison')
            if mode == 'compare-error':
                raise ValueError('comparison')
            return Truth()
        def __del__(self):
            events.append(('value-del', self.index))
    class Payload:
        def __init__(self, index):
            self.index = index
        def __add__(self, other):
            events.append(('evaluate', self.index))
            if self.index == 1 and mode == 'expr-stop':
                raise StopIteration('expression')
            if self.index == 1 and mode == 'expr-error':
                raise ValueError('expression')
            return Value(self.index)
    rows, route = [(Payload(i), 0) for i in range(3)], (0, 1, 2)
    try:
        result = maximum(rows, route)
        events.append(('result', result.index))
        del result
    except BaseException as error:
        events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
    events.append('caught')
    gc.collect()
    events.append('collected')
    return tuple(events)


def keep():
    return lifetime('keep')


def replace():
    return lifetime('replace')


def comparison_stop():
    return lifetime('compare-stop')


def comparison_error():
    return lifetime('compare-error')


def boolean_stop():
    return lifetime('bool-stop')


def boolean_error():
    return lifetime('bool-error')


def expression_stop():
    return lifetime('expr-stop')


def expression_error():
    return lifetime('expr-error')


def clamp(x, y):
    return min(1.0, max(0.0, x / y))


def scalar_clamp():
    return tuple(repr(clamp(x, 1.0)) for x in (-1., -0., .5, 2., float('nan')))


def choose(make):
    return min(1.0, max(0.0, make()))


def scalar_lifetime(mode):
    events = []
    class Truth:
        def __init__(self, which):
            self.which = which
        def __bool__(self):
            events.append(('bool', self.which))
            if mode == 'error':
                raise ValueError('bool')
            return self.which == 'inner' or mode == 'replace'
        def __del__(self):
            events.append(('truth-del', self.which))
    class Value:
        def __gt__(self, other):
            events.append('gt')
            return Truth('inner')
        def __lt__(self, other):
            events.append('lt')
            return Truth('outer')
        def __del__(self):
            events.append('value-del')
    saved = None
    try:
        result = choose(Value)
        events.append(('result', isinstance(result, Value)))
        del result
    except ValueError as error:
        saved = error
    events.append('after')
    del saved
    return tuple(events)


def scalar_keep():
    return scalar_lifetime('keep')


def scalar_replace():
    return scalar_lifetime('replace')


def scalar_bool_error():
    return scalar_lifetime('error')


def pairs(route):
    result = []
    for a, b in zip(route, route[1:]):
        result.append(a + b)
        if type(route) is list and len(route) > 2:
            route.pop()
    return tuple(result)


def tuple_pairs():
    return pairs((1, 2, 3, 4))


def list_pairs():
    return pairs([1, 2, 3, 4])


def adjacent_exit(route, callback, make):
    token = make()
    for a,b in zip(route,route[1:]):
        callback(a,b)
        return None


def adjacent_lifetime(fails):
    events=[]
    class Value:
        def __init__(self,label):
            self.label=label
        def __del__(self):
            events.append(self.label)
    def callback(a,b):
        events.append((a.label,b.label))
        if fails:
            raise ValueError('callback')
    saved=None
    try:
        adjacent_exit((Value('a'),Value('b'),Value('c')),callback,lambda:Value('token'))
    except ValueError as error:
        saved=error
    events.append('after')
    del saved
    gc.collect()
    return tuple(events)


def adjacent_return_cleanup():
    return adjacent_lifetime(False)


def adjacent_exception_cleanup():
    return adjacent_lifetime(True)


def saved_boolean(items, events):
    try:
        any(item < 0 for item in items)
    except ValueError as error:
        saved = error
    items = None
    events.append('after')
    return saved


def boolean_traceback_cleanup():
    events = []
    class Truth:
        def __bool__(self):
            raise ValueError('bool')
    class Item:
        def __lt__(self, other):
            return Truth()
        def __del__(self):
            events.append('item-del')
    error = saved_boolean([Item()], events)
    del error
    return tuple(events)


def extend_values(target, rows, route):
    target.extend(rows[a][b] for a,b in zip(route,route[1:]))


def extension_values():
    target = []
    extend_values(target, ((1,2,3,4),)*4, (0,1,2,3))
    return tuple(target)


def extension_lifetime(mode):
    events, target = [], []
    class Value:
        def __init__(self, label):
            self.label = label
        def __del__(self):
            events.append(('del', self.label))
    class Row:
        def __init__(self, label):
            self.label = label
        def __getitem__(self, index):
            events.append(('get', self.label, index, len(target)))
            if self.label == 1:
                if mode == 'stop':
                    raise StopIteration('index')
                if mode == 'error':
                    raise ValueError('index')
                target.clear()
            return Value(self.label)
    saved = None
    try:
        extend_values(target, [Row(i) for i in range(4)], (0,1,2,3))
    except BaseException as error:
        saved = error
        events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
    events.append(('length', len(target)))
    target.clear()
    events.append('cleared')
    del saved
    gc.collect()
    return tuple(events)


def extension_mutation():
    return extension_lifetime('mutate')


def extension_error():
    return extension_lifetime('error')


def extension_stop():
    return extension_lifetime('stop')


def extend_owned(rows, route):
    target = []
    target.extend(rows[a][b] for a,b in zip(route,route[1:]))
    return target


def extension_index_finalizers():
    events = []
    class Index:
        def __init__(self, number):
            self.number = number
        def __del__(self):
            events.append(('index-del', self.number))
    class Rows:
        def __getitem__(self, index):
            if index.number == 1:
                raise ValueError('index')
            return self
        def __del__(self):
            events.append('rows-del')
    saved = None
    try:
        extend_owned(Rows(), tuple(Index(i) for i in range(4)))
    except ValueError as error:
        saved = error
    events.append('caught')
    del saved
    gc.collect()
    return tuple(events)


def insertions(route, item):
    for position in range(len(route)+1):
        yield route[:position]+(item,)+route[position:]


def insertion_empty():
    return tuple(insertions((), 99))


def insertion_four():
    return tuple(insertions((0,1,2,3), 99))


def insertion_ten():
    return tuple(insertions(tuple(range(10)), 99))


def insertion_lifetime(mode):
    events = []
    class Value:
        def __init__(self, label):
            self.label = label
        def __del__(self):
            events.append(self.label)
    gen = insertions((Value('a'), Value('b')), Value('item'))
    row = next(gen)
    del row
    saved = None
    if mode == 'close':
        gen.close()
    else:
        try:
            gen.throw(ValueError('injected') if mode == 'throw' else StopIteration('injected'))
        except (ValueError, RuntimeError) as error:
            saved = error
            events.append(('caught', type(error).__name__, type(error.__cause__).__name__))
    events.append('after')
    del gen, saved
    gc.collect()
    return tuple(events)


def insertion_close():
    return insertion_lifetime('close')


def insertion_throw():
    return insertion_lifetime('throw')


def insertion_stop():
    return insertion_lifetime('stop')


def insertion_custom():
    events = []
    class Route(tuple):
        def __len__(self):
            events.append('len')
            return super().__len__()
        def __getitem__(self, key):
            events.append(('get', repr(key)))
            return super().__getitem__(key)
    result = tuple(insertions(Route((1,2)), 3))
    return result, tuple(events)
