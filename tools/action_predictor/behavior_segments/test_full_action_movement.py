import unittest
from .full_action_movement import TurnMovementAdapter, dispatch


class FakePredictor:
    def __init__(self):
        self.calls = []

    def predict(self, current, route, round_number, previous, previous_mask, state, *, previous_moves):
        self.calls.append((current, state, previous_moves))
        return dict(conditional_movement=(11, 9) if current else None,
                    state={'turns': 1 if state is None else state['turns'] + 1})


class Contract(unittest.TestCase):
    def test_dispatch_preserves_every_nonmovement_family(self):
        for family in range(15):
            if family != 8:
                self.assertEqual(dispatch(family, 17, (1, -1), True), 17)
        self.assertEqual(dispatch(8, 17, (1, -1), True), 7 * 17 + 9)

    def test_fallback_and_bounds(self):
        self.assertEqual(dispatch(8, 290, None, True), 290)
        self.assertEqual(dispatch(8, 290, (1, 1), False), 290)
        with self.assertRaises(ValueError):
            dispatch(8, 0, (2, 0), True)

    def test_prediction_cannot_depend_on_current_family(self):
        current = {'observation': {'own': {'position': {'x': 10, 'y': 10}}}}
        outcomes = []
        for family in ('move', 'attack', 'priority', 'end'):
            adapter = TurnMovementAdapter(FakePredictor())
            adapter.begin_turn()
            value = adapter.predict(current, {}, 1, [], [], [])
            outcomes.append((value['eligible'], value['movement']))
            adapter.observe(family)
        self.assertTrue(all(x == outcomes[0] for x in outcomes))

    def test_turn_clock_is_not_advanced_by_admin_queries(self):
        fake = FakePredictor(); adapter = TurnMovementAdapter(fake)
        adapter.begin_turn()
        adapter.predict(None, {}, 1, [], [], []); adapter.observe('priority')
        adapter.predict(None, {}, 1, [], [], []); adapter.observe('attack')
        value = adapter.predict(None, {}, 1, [], [], []); adapter.observe('move')
        self.assertFalse(value['eligible'])
        self.assertEqual(len(fake.calls), 2)
        self.assertIsNone(fake.calls[0][1]); self.assertIsNone(fake.calls[1][1])
        adapter.finish_turn({}, 1, [], [], [])
        adapter.begin_turn()
        adapter.predict(None, {}, 2, [], [], [(1, 0)]); adapter.observe('move')
        self.assertEqual(fake.calls[-1][1], {'turns': 1})
        adapter.finish_turn({}, 2, [], [], [])
        self.assertEqual(adapter.state, {'turns': 2})

    def test_missing_admin_only_turn_advances_once(self):
        adapter = TurnMovementAdapter(FakePredictor()); adapter.begin_turn()
        adapter.skip_admin(); adapter.finish_turn({}, 1, [], [], [])
        self.assertEqual(adapter.state, {'turns': 1})

    def test_ordering_rejected(self):
        adapter = TurnMovementAdapter(FakePredictor())
        with self.assertRaises(RuntimeError): adapter.observe('move')
        adapter.begin_turn(); adapter.predict(None, {}, 1, [], [], [])
        with self.assertRaises(RuntimeError): adapter.finish_turn({}, 1, [], [], [])
        with self.assertRaises(RuntimeError): adapter.predict(None, {}, 1, [], [], [])


if __name__ == '__main__': unittest.main()
