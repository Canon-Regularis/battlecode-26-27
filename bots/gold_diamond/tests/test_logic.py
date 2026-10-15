"""Deterministic tests for draft choices and the eight-byte signal protocol."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))


class FakeSharedMemory:
    def __init__(self):
        self.data = [0] * 8

    def size(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value


fake_cambc = types.ModuleType("cambc")
fake_cambc.shared_memory = FakeSharedMemory()
sys.modules["cambc"] = fake_cambc
comm = importlib.import_module("comm")
draft = importlib.import_module("draft")


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        fake_cambc.shared_memory = FakeSharedMemory()

    def test_roster_round_trip(self):
        roster = (11, 3, 4, 10)
        self.assertEqual(comm.unpack_roster(comm.pack_roster(roster)), roster)

    def test_reject_bad_magic(self):
        data = bytearray(comm.pack_roster((11, 3, 4, 10)))
        data[0] = 0
        self.assertEqual(comm.unpack_roster(data), ())

    def test_reject_bad_checksum(self):
        data = bytearray(comm.pack_roster((11, 3, 4, 10)))
        data[-1] ^= 1
        self.assertEqual(comm.unpack_roster(data), ())

    def test_reject_invalid_champion(self):
        data = bytearray(comm.pack_roster((11, 3, 4, 10)))
        data[4] = 12
        data[-1] = sum(data[:-1]) & 255
        self.assertEqual(comm.unpack_roster(data), ())

    def test_pair_has_distinct_slots(self):
        roster = (11, 3, 4, 10)
        self.assertEqual(comm.slot_for(roster, 3), 1)
        self.assertEqual(comm.slot_for(roster, 4), 2)

    def test_unknown_slot_disables_writes(self):
        signal = comm.TeamSignals(None)
        signal.publish(17)
        self.assertEqual(fake_cambc.shared_memory.data, [0] * 8)

    def test_objective_encoding_bounds(self):
        self.assertEqual(comm.encode_objective(223), 223)
        self.assertEqual(comm.encode_objective(None), 224)
        self.assertEqual(comm.encode_objective(224), 232)

    def test_status_byte_publish(self):
        signal = comm.TeamSignals(3)
        signal.publish(42)
        self.assertEqual(fake_cambc.shared_memory[3], 42)

    def test_recent_alert(self):
        signal = comm.TeamSignals(0)
        signal.publish_alert(3, 19, 10)
        self.assertEqual(signal.alert(11), (3, 19))

    def test_stale_alert(self):
        signal = comm.TeamSignals(0)
        signal.publish_alert(3, 19, 10)
        self.assertIsNone(signal.alert(13))

    def test_alert_priority(self):
        signal = comm.TeamSignals(0)
        signal.publish_alert(7, 19, 10)
        signal.publish_alert(1, 20, 10)
        self.assertEqual(signal.alert(10), (7, 19))


class DraftTests(unittest.TestCase):
    def test_default_three_picks(self):
        with patch.object(draft, "_features", return_value=(False, False, False)):
            self.assertEqual(draft._order([], [])[:3], [10, 3, 9])

    def test_pair_moves_back_against_revealed_danger(self):
        with patch.object(draft, "_features", return_value=(False, False, False)):
            self.assertGreater(draft._order([], [4, 8]).index(3), 2)

    def test_dense_map_prioritizes_varg(self):
        with patch.object(draft, "_features", return_value=(False, True, False)):
            self.assertEqual(draft._order([], [])[1], 9)


if __name__ == "__main__":
    unittest.main()
