"""Fresh construction versus correctness fallbacks; losing cases are retained."""

from dataclasses import dataclass


CASES = ('fresh_record', 'reinitialized_record', 'subclass_record',
         'finalizer_replaces_dictionary', 'dictionary_subclass')


@dataclass(frozen=True)
class Row:
    a: object
    b: object
    c: object
    d: object
    e: object
    f: object


class Derived(Row):
    pass


def fresh_record():
    row = Row(1,2,3,4,5,6)
    result = row.a + row.f
    return result


def reinitialized_record():
    row = Row(1,2,3,4,5,6)
    for i in range(32):
        row.__init__(i,2,3,4,5,6)
    return row.a + row.f


def subclass_record():
    row = Derived(1,2,3,4,5,6)
    result = row.a + row.f
    return result


def finalizer_replaces_dictionary():
    seen = []
    class Swap:
        def __del__(self):
            object.__setattr__(row, '__dict__', {})
            seen.append('swap')
    class Watch:
        def __del__(self):
            seen.append(tuple(sorted(object.__getattribute__(row, '__dict__'))))
    row = Row(Swap(),Watch(),3,4,5,6)
    row.__init__(1,20,30,40,50,60)
    return tuple(seen), row.b, row.c, row.d, row.e, row.f


def dictionary_subclass():
    class Dictionary(dict):
        def __bool__(self):
            raise AssertionError('custom bool must not run')
        def __setitem__(self, key, value):
            raise AssertionError('custom setter must not run')
    row = object.__new__(Row)
    object.__setattr__(row, '__dict__', Dictionary())
    row.__init__(1,2,3,4,5,6)
    return row.a, row.b, row.c, row.d, row.e, row.f
