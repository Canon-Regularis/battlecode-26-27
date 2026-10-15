"""Exact eight-byte team protocol and validated draft roster cache."""

import cambc
from strategy_config import MAX_GROUP_CODE, STATUS_UNKNOWN


MAGIC = b"GD1"


def pack_roster(roster):
    data = MAGIC + bytes((len(roster), *roster))
    return data + bytes((sum(data) & 255,))


def unpack_roster(data):
    data = bytes(data)
    if len(data) < 6 or data[:3] != MAGIC:
        return ()
    count = data[3]
    if count < 3 or count > 6 or len(data) < count + 5:
        return ()
    result = tuple(data[4:4 + count])
    if any(kind > 11 for kind in result):
        return ()
    if data[4 + count] != (sum(data[:4 + count]) & 255):
        return ()
    return result


def slot_for(roster, champion_type):
    try:
        return roster.index(int(champion_type))
    except ValueError:
        return None


def encode_objective(group_id):
    if group_id is None:
        return STATUS_UNKNOWN
    if 0 <= group_id <= MAX_GROUP_CODE:
        return group_id
    return 232


class TeamSignals:
    def __init__(self, slot):
        self.slot = slot if slot is not None and 0 <= slot < 6 else None
        self.enabled = self.slot is not None and cambc.shared_memory.size() == 8

    def statuses(self):
        if not self.enabled:
            return ()
        return tuple(cambc.shared_memory[index] for index in range(6))

    def publish(self, value):
        if self.enabled and 0 <= value <= 255:
            cambc.shared_memory[self.slot] = value

    def alert(self, round_number):
        if not self.enabled:
            return None
        head = cambc.shared_memory[6]
        target = cambc.shared_memory[7]
        if head != cambc.shared_memory[6]:
            return None
        kind = head >> 5
        if not kind:
            return None
        age = (round_number - (head & 31)) & 31
        if age > (1 if kind in (4, 7) else 2):
            return None
        return kind, target

    def clear_stale(self, round_number):
        if not self.enabled:
            return
        head = cambc.shared_memory[6]
        kind = head >> 5
        age = (round_number - (head & 31)) & 31
        if kind and age > (1 if kind in (4, 7) else 2):
            cambc.shared_memory[6] = round_number & 31

    def publish_alert(self, kind, target, round_number):
        if not self.enabled or not 1 <= kind <= 7 or not 0 <= target <= 255:
            return
        current = self.alert(round_number)
        priority = {7: 7, 4: 6, 3: 5, 2: 4, 1: 3, 6: 2, 5: 1}
        if current is not None and priority[current[0]] > priority[kind]:
            return
        cambc.shared_memory[7] = target
        cambc.shared_memory[6] = (kind << 5) | (round_number & 31)

