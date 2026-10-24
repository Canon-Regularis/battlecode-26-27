"""Guest witnesses for generic numeric regions and native-index retry."""

from dataclasses import dataclass
import cambc

CASES = ('region_regular', 'region_empty', 'region_negative', 'region_index_error',
         'region_skipped_index', 'region_compensated', 'region_float_overflow',
         'region_mixed_fallback', 'region_custom_number', 'region_dirty_true')
THRESHOLD = 0
EVENTS = []
TRUE_ROWS = []


@dataclass(frozen=True)
class Cell:
    a: int
    b: int
    c: int
    d: int


@dataclass(frozen=True)
class Result:
    a: int
    b: int
    c: int
    peak: int
    score: float


def never():
    if cambc.fuel_remaining() >= THRESHOLD:
        return False
    return True


def dirty():
    if cambc.fuel_remaining() < THRESHOLD:
        return False
    EVENTS.append('dirty')
    TRUE_ROWS.clear()
    TRUE_ROWS.extend([Cell(101, 2, 3, 4), Cell(17, 19, 23, 29)])
    return True


class Engine:
    def __init__(self, cells: list[Cell], matrix: list[list[int]], weights: tuple[float, ...]):
        self.cells = cells
        self.matrix = matrix
        self.weights = weights

    def evaluate(self, route: tuple[int, ...], selector: int):
        if not route:
            return None
        if any(self.matrix[selector][index] < 0 for index in route):
            return None
        cells = self.cells
        a = sum(cells[index].a for index in route)
        b = sum(cells[index].b for index in route)
        c = sum(cells[index].c for index in route)
        ratio = a / (selector + 1)
        peak = max(cells[index].c + cells[index].d for index in route)
        score = self.weighted(route) + ratio
        return Result(a, b, c, peak, score)

    def weighted(self, route):
        return sum(self.cells[index].c * self.weights[index] for index in route)

    def search(self, *, stop, limit: int):
        evaluate = self.evaluate
        results = {}
        for size in range(1, limit + 1):
            if stop():
                pass
            route = tuple(range(size))
            value = evaluate(route, 0)
            if value is None:
                continue
            results[size] = value
        return sorted(results.values(), key=lambda value: value.score, reverse=True)


def search(cells, matrix, weights, limit):
    engine = Engine(cells, matrix, weights)
    return engine.search(stop=never, limit=limit)


def search_dirty(cells, matrix, weights, limit):
    engine = Engine(cells, matrix, weights)
    return engine.search(stop=dirty, limit=limit)


def normalized(values):
    return tuple((value.a, value.b, value.c, value.peak, value.score.hex()) for value in values)


def rows():
    return [Cell(2, 3, 5, 7), Cell(11, 13, 17, 19), Cell(23, 29, 31, 37)]


def region_regular():
    return normalized(search(rows(), [[1, 2, 3]], (0.1, 0.2, 0.3), 3))


def region_empty():
    return normalized(search([], [[]], (), 0))


def region_negative():
    return normalized(search(rows(), [[1, -1, 3]], (0.1, 0.2, 0.3), 3))


def region_index_error():
    try:
        search(rows(), [[1]], (0.1, 0.2, 0.3), 3)
    except Exception as error:
        return type(error).__name__, str(error)


def region_skipped_index():
    return normalized(search(rows(), [[-1]], (0.1, 0.2, 0.3), 3))


def region_compensated():
    cells = [Cell(0, 0, 10**16, 1), Cell(0, 0, 1, 1), Cell(0, 0, -10**16, 1)]
    return normalized(search(cells, [[1, 2, 3]], (1.0, 1.0, 1.0), 3))


def region_float_overflow():
    cells = [Cell(0, 0, 10**1000, 1), Cell(0, 0, 1, 1)]
    try:
        search(cells, [[1, 2]], (1.0, 0.0), 2)
    except Exception as error:
        return type(error).__name__, str(error)


def region_mixed_fallback():
    try:
        search(rows(), [[1, 2, 3]], (10**1000, 0.0), 3)
    except Exception as error:
        return type(error).__name__, str(error)


def region_custom_number():
    EVENTS.clear()
    class Number:
        def __radd__(self, other):
            EVENTS.append('add')
            return other + 41
    cells = [Cell(Number(), 2, 3, 4)]
    value = normalized(search(cells, [[1]], (0.5,), 1))
    return value, tuple(EVENTS)


def region_dirty_true():
    EVENTS.clear()
    TRUE_ROWS.clear()
    TRUE_ROWS.extend(rows())
    value = normalized(search_dirty(TRUE_ROWS, [[1, 2]], (0.1, 0.2, 0.3), 2))
    return value, tuple(EVENTS)
