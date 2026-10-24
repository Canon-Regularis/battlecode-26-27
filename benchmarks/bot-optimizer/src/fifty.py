"""Guest semantic witnesses for snapshot-derived arithmetic and native extrema."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    score: float
    bounded: float


class Engine:
    def __init__(self, matrix: list[list[int]], weights: tuple[float, ...], denominator: tuple[float, ...]):
        self.matrix = matrix
        self.weights = weights
        self.denominator = denominator

    def evaluate(self, route: tuple[int, ...], selector: int):
        total = 0.0
        for i in route:
            pair = self.weights[i] + self.weights[i]
            total += self.matrix[i][i] * pair / self.denominator[i]
        bounded = min(1.0, max(0.0, total))
        return Result(total, bounded)

    def search(self, *, stop, limit: int):
        evaluate = self.evaluate
        results = {}
        for index in range(limit):
            if index > 100 or stop():
                break
            route = (index - 1,)
            value = evaluate(route, 0)
            results[index] = value
        return sorted(results.values(), key=lambda value: value.score)


REMAINING = 1


def stop():
    return REMAINING < 0


def run(matrix, weights, denominator, limit):
    engine = Engine(matrix, weights, denominator)
    return engine.search(stop=stop, limit=limit)


def observe(matrix, weights, denominator, limit):
    try:
        return repr([(row.score.hex(), row.bounded.hex()) for row in run(matrix, weights, denominator, limit)])
    except (IndexError, OverflowError, ZeroDivisionError) as error:
        return type(error).__name__ + ':' + str(error)


def finite_negative_indices():
    return observe([[2, 3], [5, 7]], (0.1, 0.9), (2.0, 2.0), 2)


def nan_and_infinity():
    return observe([[1, 0], [0, 1]], (float('nan'), float('inf')), (2.0, 2.0), 2)


def signed_zero():
    return observe([[1, 0], [0, 1]], (-0.0, 0.0), (-2.0, 2.0), 2)


def mismatched_negative_domains():
    return observe([[2, 3], [5, 7]], (0.1, 0.9, 0.3), (2.0, 2.0), 2)


def skipped_zero_division():
    return observe([[2, 3], [5, 7]], (0.1, 0.9), (0.0, 2.0), 1)


def taken_zero_division():
    return observe([[2, 3], [5, 7]], (0.1, 0.9), (0.0, 2.0), 2)


def original_index_error_order():
    return observe([], (), (), 1)


def huge_integer_conversion():
    return observe([[10**1000]], (0.1,), (2.0,), 1)


def skipped_huge_integer_conversion():
    return observe([[10**1000, 0], [0, 1]], (0.1, 0.9), (2.0, 2.0), 1)


def ragged_matrix():
    return observe([[1], [0, 3]], (0.1, 0.9), (2.0, 2.0), 2)


CASES = ('finite_negative_indices', 'nan_and_infinity', 'signed_zero',
         'mismatched_negative_domains', 'skipped_zero_division', 'taken_zero_division',
         'original_index_error_order', 'huge_integer_conversion',
         'skipped_huge_integer_conversion', 'ragged_matrix')
