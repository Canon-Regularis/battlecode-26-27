"""Compact draft-only representation of a shared squad loop."""

from dataclasses import dataclass
import struct


PLAN_HEADER = struct.Struct("<4sBBHB")
ROUTE_HEADER = struct.Struct("<BBH")
MAGIC = b"SQL2"
Route = tuple[tuple[int, int], tuple[tuple[int, int], ...]]


@dataclass(frozen=True)
class Plan:
    altar: tuple[int, int]
    camps: tuple[tuple[int, int], ...]
    roster: tuple[int, ...]
    alternatives: tuple[Route, ...] = ()

    @property
    def routes(self):
        return ((self.altar, self.camps),) + self.alternatives

    def encode(self):
        if not 1 <= len(self.roster) <= 6 or len(set(self.roster)) != len(self.roster):
            raise ValueError("a squad needs one to six unique champion types")
        data = PLAN_HEADER.pack(MAGIC, *self.altar, len(self.camps), len(self.roster))
        data += bytes(self.roster)
        data += bytes(coordinate for camp in self.camps for coordinate in camp)
        data += bytes((len(self.alternatives),))
        for altar, camps in self.alternatives:
            data += ROUTE_HEADER.pack(*altar, len(camps))
            data += bytes(coordinate for camp in camps for coordinate in camp)
        if len(data) > 1024:
            raise ValueError("route exceeds draft memory")
        return data

    @classmethod
    def decode(cls, data):
        if len(data) < PLAN_HEADER.size:
            raise ValueError("missing squad plan")
        magic, x, y, count, size = PLAN_HEADER.unpack_from(data)
        end = PLAN_HEADER.size + size + 2 * count
        if magic not in (b"SQL1", MAGIC) or len(data) < end:
            raise ValueError("invalid squad plan")
        offset = PLAN_HEADER.size
        roster = tuple(data[offset:offset + size])
        points = data[offset + size:end]
        alternatives = []
        offset = end
        if magic == MAGIC:
            if offset >= len(data):
                raise ValueError("missing overlay routes")
            extra = data[offset]
            offset += 1
            for _ in range(extra):
                if offset + ROUTE_HEADER.size > len(data):
                    raise ValueError("truncated overlay route")
                ax, ay, length = ROUTE_HEADER.unpack_from(data, offset)
                offset += ROUTE_HEADER.size
                end = offset + length * 2
                if end > len(data):
                    raise ValueError("truncated overlay camps")
                route = data[offset:end]
                alternatives.append(((ax, ay), tuple(zip(route[::2], route[1::2]))))
                offset = end
        # The engine exposes a fixed-size, zero-padded draft buffer in play.
        if any(data[offset:]):
            raise ValueError("unexpected trailing plan data")
        plan = cls((x, y), tuple(zip(points[::2], points[1::2])), roster, tuple(alternatives))
        plan.encode()  # Validate roster as well as framing.
        return plan
