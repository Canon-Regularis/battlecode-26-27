"""Small records and implementation-derived return types; no annotation trust."""

from dataclasses import dataclass
import cambc

CASES = ('record_pair', 'record_triple', 'record_effects', 'wrapped_sum',
         'wrapped_native_map', 'wrapped_mask_count', 'wrapped_mask_empty',
         'nested_integer_counter', 'signed_integer_modulo')

PERIOD = 8


@dataclass(frozen=True)
class Pair:
    a: object
    b: object


@dataclass(frozen=True)
class Triple:
    a: object
    b: object
    c: object


def record_pair():
    row = Pair(3, 4)
    result = row.a + row.b
    return result


def record_triple():
    row = Triple(3, 4, 5)
    result = row.a + row.b + row.c
    return result


def record_effects():
    seen = []
    def value(n):
        seen.append(n)
        return n
    row = Triple(c=value(3), b=value(2), a=value(1))
    return row.a, row.b, row.c, tuple(seen)


def numbers():
    return (-8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3)


def wrapped_sum():
    return sum(x*x for x in numbers() if x > 0)


def wrapped_native_map():
    return tuple(abs(x) for x in numbers())


def mask():
    board = cambc.Bitboard()
    board.draw_chebyshev(cambc.Vec2(8, 8), 5)
    return board


def wrapped_mask_count():
    return len(mask().positions())


def wrapped_mask_empty():
    return bool(mask().positions())


def nested_integer_counter():
    count = hits = 0
    for x in range(16):
        for y in range(16):
            count += 1
            if count % PERIOD == 0:
                hits += 1
    return count, hits


def signed_integer_modulo():
    return tuple(value % PERIOD for value in range(-128, 128))
