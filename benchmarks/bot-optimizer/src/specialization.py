"""Generic compiler workloads: no game-specific classes or algorithms."""

from dataclasses import dataclass


CASES = (
    "identity_sum", "bounded_tuple", "native_map_tuple", "integer_helper",
    "keyword_calls", "frozen_record4", "frozen_record8", "frozen_record12",
    "temporary_record", "subclass_fallback",
)


@dataclass(frozen=True)
class Record4:
    a: int
    b: int
    c: int
    d: int


@dataclass(frozen=True)
class Record8:
    a: int
    b: int
    c: int
    d: int
    e: int
    f: int
    g: int
    h: int


@dataclass(frozen=True)
class Record12:
    a: int
    b: int
    c: int
    d: int
    e: int
    f: int
    g: int
    h: int
    i: int
    j: int
    k: int
    l: int


@dataclass(frozen=True)
class Point:
    x: int
    y: int


class Derived(Record12):
    pass


def _square(value):
    return value*value


def _pack(a, b, c, d):
    return a, b, c, d


def identity_sum():
    return sum(x for x in range(128))


def bounded_tuple():
    values = (-8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7)
    return sum(x*x for x in values)


def native_map_tuple():
    values = tuple(range(-64, 64))
    return sum(abs(x) for x in values)


def integer_helper():
    result = 0
    for x in range(128):
        result += _square(x)
    return result


def keyword_calls():
    result = 0
    for x in range(32):
        result += _pack(a=x, b=x+1, c=x+2, d=x+3)[0]
    return result


def frozen_record4():
    obj = Record4(1, 2, 3, 4)
    result = obj.a + obj.d
    return result


def frozen_record8():
    obj = Record8(1, 2, 3, 4, 5, 6, 7, 8)
    result = obj.a + obj.h
    return result


def frozen_record12():
    obj = Record12(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    result = obj.a + obj.l
    return result


def temporary_record():
    base = len(range(7))
    obj = Point(x=base-4, y=base-3)
    return obj.x*obj.x + obj.y*obj.y


def subclass_fallback():
    obj = Derived(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    result = obj.a + obj.l
    return result
