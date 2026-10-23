"""Setup-inclusive generated-code kernels and a combined decision workload."""

from dataclasses import dataclass


CASES = (
    'filtered_empty', 'filtered_small', 'filtered_large', 'filtered_tuple',
    'compound_item_key', 'compound_attribute_key', 'tuple_map_empty',
    'tuple_map_large', 'list_map_small', 'membership_small', 'membership_large',
    'combined_decision',
)


@dataclass(frozen=True)
class Candidate:
    handle: int
    damage: int
    distance: int
    priority: int
    reserve: int
    weight: int


def weight(damage, distance):
    return damage*3-distance


def filtered_empty():
    return sum(x*x for x in range(0) if x & 1)


def filtered_small():
    return sum(x*x for x in range(8) if x > 2 if x & 1)


def filtered_large():
    return sum(x*x for x in range(4096) if x & 1)


def filtered_tuple():
    values = (-8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3)
    return max(x*x for x in values if x < 0 or x > 1)


def compound_item_key():
    rows = [(i % 7, -i, i) for i in range(128)]
    return sorted(rows, key=lambda r: (r[0], r[1]))


def compound_attribute_key():
    rows = [Candidate(i, i % 7, 3, -i, 0, 1) for i in range(32)]
    return [row.handle for row in sorted(rows, key=lambda r: (r.damage, r.priority))]


def tuple_map_empty():
    return tuple(abs(x) for x in range(0))


def tuple_map_large():
    return tuple(abs(x) for x in range(-128, 0))


def list_map_small():
    return list(abs(x) for x in range(-8, 0))


def membership_small():
    total = 0
    for x in range(128):
        total += x in (1, 4, 7, 9)
    return total


def membership_large():
    total = 0
    for x in range(128):
        total += x not in (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
                          32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62)
    return total


def combined_decision():
    rows = []
    for i in range(64):
        if i not in (3, 7, 15, 19, 22, 37, 51, 58):
            score = weight(i, 3)
            rows.append(Candidate(handle=i, damage=i, distance=3, priority=score, reserve=4, weight=1))
    chosen = sorted(rows, key=lambda r: (r.priority, r.handle), reverse=True)[:8]
    coverage = sum(x*x for x in range(32) if x > 2 if x & 1)
    offsets = tuple(abs(x) for x in range(-8, 0))
    return tuple(row.handle for row in chosen), coverage, offsets
