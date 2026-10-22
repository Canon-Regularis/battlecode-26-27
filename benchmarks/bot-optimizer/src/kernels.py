"""Original kernels: the benchmark driver compiles these, not hand-written alternatives.

Setup is deliberately included. No annotations are needed to trigger the passes.
"""

import cambc


CASES = (
    "integer_square", "native_map", "bounded_sum", "mask_count", "mask_empty",
    "mask_filter", "mask_intersection_count", "native_key", "item_key", "attribute_key",
)


def integer_square():
    result = 0
    for x in range(128):
        result += x**2
    return result


def native_map():
    return sum(abs(x) for x in range(-64, 64))


def bounded_sum():
    return sum(x*x for x in range(128))


def mask_count():
    board = cambc.Bitboard()
    board.draw_chebyshev(cambc.Vec2(10, 10), 8)
    return len(board.positions())


def mask_empty():
    board = cambc.Bitboard()
    board.draw_chebyshev(cambc.Vec2(10, 10), 8)
    return bool(board.positions())


def mask_filter():
    a = cambc.Bitboard()
    b = cambc.Bitboard()
    a.draw_chebyshev(cambc.Vec2(10, 10), 8)
    b.draw_chebyshev(cambc.Vec2(14, 14), 6)
    return [p for p in a.positions() if b.is_set(p)]


def mask_intersection_count():
    a = cambc.Bitboard()
    b = cambc.Bitboard()
    a.draw_chebyshev(cambc.Vec2(10, 10), 8)
    b.draw_chebyshev(cambc.Vec2(14, 14), 6)
    return sum(1 for p in a.positions() if b.is_set(p))


def native_key():
    board = cambc.Bitboard()
    board.draw_chebyshev(cambc.Vec2(10, 10), 8)
    field = cambc.DistanceField()
    return min(board.positions(), key=lambda p: field.get(p))


def item_key():
    records = [(x, (x*31) % 97) for x in range(128)]
    return min(records, key=lambda row: row[1])


def attribute_key():
    records = list(range(128, 0, -1))
    return min(records, key=lambda row: row.real)
