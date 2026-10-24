"""Generated any/all helpers with protocol, mutation and lifetime witnesses."""

import gc

CASES = ('empty', 'one', 'four', 'sixteen', 'early', 'all_four',
         'iterator_protocol', 'mutation_true', 'mutation_false',
         'boolean_stop', 'boolean_error', 'predicate_stop', 'predicate_error')


def has_negative(items):
    return any(item < 0 for item in items)


def all_negative(items):
    return all(item < 0 for item in items)


def empty():
    return has_negative([])


def one():
    return has_negative([1])


def four():
    return has_negative([1, 2, 3, 4])


def sixteen():
    return has_negative([1] * 16)


def early():
    return has_negative([-1, 2, 3, 4])


def all_four():
    return all_negative([-1, -2, -3, -4])


def iterator_protocol():
    events = []
    class Items:
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
            return 1
    result = has_negative(Items())
    return result, tuple(events)


def lifetime(mode):
    events, items = [], []
    class Value:
        def __bool__(self):
            events.append('bool')
            if mode == 'bool-stop':
                raise StopIteration('bool')
            if mode == 'bool-error':
                raise ValueError('bool')
            return mode == 'true'
        def __del__(self):
            events.append('value-del')
    class Item:
        def __init__(self, index):
            self.index = index
        def __lt__(self, other):
            events.append(('compare', self.index))
            items.clear()
            if mode == 'compare-stop':
                raise StopIteration('compare')
            if mode == 'compare-error':
                raise ValueError('compare')
            return Value()
        def __del__(self):
            events.append(('item-del', self.index))
    items.extend(Item(i) for i in range(3))
    try:
        events.append(('result', has_negative(items)))
    except BaseException as error:
        events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
    events.append('caught')
    gc.collect()
    events.append('collected')
    return tuple(events)


def mutation_true():
    return lifetime('true')


def mutation_false():
    return lifetime('false')


def boolean_stop():
    return lifetime('bool-stop')


def boolean_error():
    return lifetime('bool-error')


def predicate_stop():
    return lifetime('compare-stop')


def predicate_error():
    return lifetime('compare-error')
