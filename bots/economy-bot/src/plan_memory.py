"""Named route plans and their compact draft-memory representation.

The SQL2 byte format is unchanged. SQL1 buffers and engine zero-padding remain
readable; do not replace this with a heavyweight serializer inside the bot.
"""

from dataclasses import dataclass
import struct

from settings import DRAFT_MEMORY_LIMIT


PLAN_HEADER = struct.Struct("<4sBBHB")
ROUTE_HEADER = struct.Struct("<BBH")
MAGIC = b"SQL2"


@dataclass(frozen=True)
class RoutePlan:
    """Coordinates, unlike the camp/altar indices used during search."""

    altar: tuple[int, int]
    camps: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class DraftPlan:
    primary: RoutePlan
    roster: tuple[int, ...]
    alternatives: tuple[RoutePlan, ...] = ()

    @property
    def routes(self):
        return (self.primary,) + self.alternatives

    def encode(self):
        if not 1 <= len(self.roster) <= 6 or len(set(self.roster)) != len(self.roster):
            raise ValueError("a squad needs one to six unique champion types")
        data = PLAN_HEADER.pack(MAGIC, *self.primary.altar, len(self.primary.camps), len(self.roster))
        data += bytes(self.roster)
        data += bytes(coordinate for camp in self.primary.camps for coordinate in camp)
        data += bytes((len(self.alternatives),))
        for route in self.alternatives:
            data += ROUTE_HEADER.pack(*route.altar, len(route.camps))
            data += bytes(coordinate for camp in route.camps for coordinate in camp)
        if len(data) > DRAFT_MEMORY_LIMIT:
            raise ValueError("route exceeds draft memory")
        return data

    @classmethod
    def decode(cls, data):
        if len(data) < PLAN_HEADER.size:
            raise ValueError("missing squad plan")
        magic, altar_x, altar_y, camp_count, roster_size = PLAN_HEADER.unpack_from(data)
        end = PLAN_HEADER.size + roster_size + 2 * camp_count
        if magic not in (b"SQL1", MAGIC) or len(data) < end:
            raise ValueError("invalid squad plan")
        offset = PLAN_HEADER.size
        roster = tuple(data[offset:offset + roster_size])
        points = data[offset + roster_size:end]
        alternatives = []
        offset = end
        if magic == MAGIC:
            if offset >= len(data):
                raise ValueError("missing overlay routes")
            alternative_count = data[offset]
            offset += 1
            for _ in range(alternative_count):
                if offset + ROUTE_HEADER.size > len(data):
                    raise ValueError("truncated overlay route")
                route_x, route_y, route_length = ROUTE_HEADER.unpack_from(data, offset)
                offset += ROUTE_HEADER.size
                end = offset + route_length * 2
                if end > len(data):
                    raise ValueError("truncated overlay camps")
                coordinates = data[offset:end]
                route = RoutePlan((route_x, route_y), tuple(zip(coordinates[::2], coordinates[1::2])))
                alternatives.append(route)
                offset = end
        # The engine exposes a fixed-size, zero-padded draft buffer in play.
        if any(data[offset:]):
            raise ValueError("unexpected trailing plan data")
        primary = RoutePlan((altar_x, altar_y), tuple(zip(points[::2], points[1::2])))
        plan = cls(primary, roster, tuple(alternatives))
        plan.encode()  # Validate roster as well as framing.
        return plan
