"""Generated deferred-return paths, retained/rejected costs and lifecycle probes."""

from dataclasses import dataclass

CASES = ('reject_all', 'retain_quarter', 'retain_all', 'fallback_override',
         'finalizer_reject', 'finalizer_mutation')


@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
    d: int


@dataclass(frozen=True)
class Kept:
    index: object
    value: object


class Engine:
    def __init__(self, output):
        self.output = output

    def make(self, values):
        if values is None:
            return None
        a, b, c, d = values
        return Row(a, b, c, d)

    def choose(self, data, threshold):
        produce = self.make
        kept = self.output
        for index, values in enumerate(data):
            row = produce(values)
            if row is None:
                continue
            if row.a > threshold:
                kept[index] = Kept(index, row)
        return kept


def workload(threshold):
    engine = Engine({})
    rows = engine.choose(((i % 8, i, i + 1, i + 2) for i in range(128)), threshold)
    return tuple((key, value.value.a) for key, value in rows.items())


def reject_all():
    return workload(10)


def retain_quarter():
    return workload(5)


def retain_all():
    return workload(-1)


def fallback_override():
    class Child(Engine):
        def make(self, values):
            return Row(20, 2, 3, 4)
    result = Child({}).choose([(1, 2, 3, 4)], 5)
    return result[0].value.a


def lifetime(retain, mutate):
    events = []
    class Item:
        def __init__(self, label):
            self.label = label
        def __gt__(self, other):
            events.append(('compare', self.label))
            return retain
        def __del__(self):
            events.append(('del', self.label))
    class Output(dict):
        def __setitem__(self, key, value):
            events.append(('store', key))
            if mutate:
                object.__setattr__(value.value, 'b', Item(str(key) + 'replacement'))
            super().__setitem__(key, value)
    def data():
        for i in range(3):
            yield tuple(Item(str(i) + field) for field in 'abcd')
    output = Output()
    engine = Engine(output)
    engine.choose(data(), 0)
    del engine
    output.clear()
    return tuple(events)


def finalizer_reject():
    return lifetime(False, False)


def finalizer_mutation():
    return lifetime(True, True)
