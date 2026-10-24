"""Guest witnesses for private insertion-key producer/consumer specialization."""

from dataclasses import dataclass
from math import ceil


def variants(base, count):
    for value in range(-1, count):
        for position in range(len(base) + 1):
            yield base[:position] + (value,) + base[position:]


@dataclass(frozen=True)
class Item:
    amount: int
    duration: int


@dataclass(frozen=True)
class Result:
    amount: int
    duration: int
    peak: int
    score: float


class Engine:
    def __init__(self, items: list[Item], weights: tuple[float, ...], divisors: tuple[float, ...], matrix: list[list[int]]):
        self.items = items
        self.weights = weights
        self.divisors = divisors
        self.matrix = matrix

    def evaluate(self, route: tuple[int, ...], selector: int):
        if not route:
            return None
        matrix = self.matrix
        first, last = route[0], route[-1]
        edges = [matrix[selector][first], matrix[selector][last]]
        edges.extend(matrix[a][b] for a, b in zip(route, route[1:]))
        if any(value < 0 for value in edges):
            return None
        items = self.items
        amount = sum(items[i].amount for i in route)
        duration = sum(items[i].duration for i in route)
        rounded = ceil(amount / 10)
        peak = max(items[i].amount + items[i].duration for i in route)
        reward = amount + 0.1 * duration
        score = reward + rounded
        for origin, destination in zip(route, route[1:]):
            score += matrix[origin][destination] * self.weights[destination]
        score += sum(self.weights[i] / self.divisors[i] for i in route)
        score += sum(edges)
        return Result(amount, duration, peak, score)

    def search(self, *, stop, limit: int):
        evaluate = self.evaluate
        results = {}
        selection = 0
        for base in [tuple([0, 0]), tuple([0])]:
            for route in variants(base, limit):
                if stop():
                    break
                result = evaluate(route, selection)
                if result is None:
                    continue
                key = frozenset(route)
                previous = results.get(key)
                if previous is None or result.score > previous.score:
                    results[key] = result
        return sorted(results.values(), key=lambda value: value.score, reverse=True)


REMAINING = 1


def stop():
    return REMAINING < 0


def run(items, weights, divisors, limit, matrix):
    owner = Engine(items, weights, divisors, matrix)
    return owner.search(stop=stop, limit=limit)


def observe(weights, divisors, limit, matrix=None):
    try:
        rows = run([Item(2, 3), Item(5, 7)], weights, divisors, limit,
                   matrix if matrix is not None else [[2, 3], [5, 7]])
        return repr([(row.amount, row.duration, row.peak, row.score.hex()) for row in rows])
    except (IndexError, OverflowError, ZeroDivisionError) as error:
        return type(error).__name__ + ':' + str(error)


def duplicate_negative_indices():
    return observe((0.1, 0.9), (2.0, 2.0), 2)


def compensated_and_infinite():
    return observe((1e16, -1e16), (1.0, 1.0), 2) + observe((float('inf'), float('-inf')), (1.0, 1.0), 2)


def signed_zero():
    return observe((-0.0, 0.0), (-2.0, 2.0), 2, [[0, 0], [0, 0]])


def partial_preparation_skips_error():
    return observe((0.1, 0.3, 0.9), (2.0, 0.0, 2.0), 1)


def taken_error():
    return observe((0.1, 0.9), (2.0, 0.0), 2)


def index_error_retry():
    return observe((0.1, 0.9), (2.0, 2.0), 3)


def stopped():
    return True


def stopped_before_evaluation():
    owner = Engine([], (), (), [])
    return repr(owner.search(stop=stopped, limit=2))


def ragged_edges():
    return observe((0.1, 0.9), (2.0, 2.0), 2, [[2], [5, 7]])


def negative_edges():
    return observe((0.1, 0.9), (2.0, 2.0), 2, [[2, -3], [5, 7]])


def large_edges():
    return observe((0.1, 0.9), (2.0, 2.0), 2, [[10**100, 3], [5, 7]])


CASES = ('duplicate_negative_indices', 'compensated_and_infinite', 'signed_zero',
         'partial_preparation_skips_error', 'taken_error', 'index_error_retry',
         'stopped_before_evaluation', 'ragged_edges', 'negative_edges', 'large_edges')
