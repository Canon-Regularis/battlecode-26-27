"""Generated short-reduction guards, long-input and protocol fallbacks."""

from dataclasses import dataclass

CASES = ('empty', 'one', 'four', 'eight', 'thirty_two', 'floats', 'bigints', 'protocols')


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
