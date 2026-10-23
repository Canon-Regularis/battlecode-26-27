"""Generated short-reduction guards, long-input and protocol fallbacks."""

from dataclasses import dataclass

CASES = ('empty', 'one', 'four', 'eight', 'sixteen', 'thirty_two', 'floats', 'bigints', 'protocols',
         'negative_indices', 'index_errors')


@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int


ROWS = tuple(Row(i, i + 1, i + 2) for i in range(32))
FLOATS = (Row(1e30, -1e30, 0.1), Row(1, 1, 0.2), Row(-1e30, 1e30, 0.3))
BIGINTS = tuple(Row(2**100 + i, -(2**120) + i, i) for i in range(4))


def totals(rows, route):
    a = sum(rows[i].a for i in route)
    b = sum(rows[i].b for i in route)
    c = sum(rows[i].c for i in route)
    return a, b, c


def empty():
    return totals(ROWS, ())


def one():
    return totals(ROWS, (0,))


def four():
    return totals(ROWS, (0, 1, 2, 3))


def eight():
    return totals(ROWS, tuple(range(8)))


def thirty_two():
    return totals(ROWS, tuple(range(32)))


def sixteen():
    return totals(ROWS, tuple(range(16)))


def negative_indices():
    return totals(ROWS, (-1,-2,-32))


def index_errors():
    results = []
    for route in ((32,), (-33,), (10**100,), (-(10**100),), (0,1,99)):
        try:
            totals(ROWS, route)
        except IndexError as error:
            results.append((type(error).__name__, str(error)))
    return tuple(results)


def floats():
    return tuple(value.hex() for value in totals(FLOATS, (0, 1, 2)))


def bigints():
    return totals(BIGINTS, (0, 1, 2, 3))


def protocols():
    events = []
    class Child(Row):
        def __getattribute__(self, name):
            events.append(name)
            return super().__getattribute__(name)
    result = totals([Child(1, 2, 3), Child(4, 5, 6)], (0, 1))
    return result, tuple(events)
