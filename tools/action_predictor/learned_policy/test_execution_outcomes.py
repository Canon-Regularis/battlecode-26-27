"""SDK return/call recording, no engine or proposed game-state execution."""
import unittest
from types import SimpleNamespace
from .execution import Command
from .execution_outcomes import OutcomeExecutor


class TestOutcomes(unittest.TestCase):
    def setUp(self):
        self.calls = []; self.returned = False
        def call(name):
            def invoke(*args): self.calls.append((name, args)); return self.returned
            return invoke
        self.me = SimpleNamespace(
            move_absolute=call('move'), place_ward=call('ward'),
            abilities=lambda:[SimpleNamespace(valid_targets=lambda:16, use=call('cast_0')),
                              SimpleNamespace(valid_targets=lambda:16, use=call('cast_1'))],
            consumables=lambda:[SimpleNamespace(kind=lambda:1, use=call('altar')),
                                SimpleNamespace(kind=lambda:2, use=call('teleport'))],
            set_priority=lambda p:self.calls.append(('priority', (p,))))
        sdk = SimpleNamespace(me=lambda:self.me, Vec2=lambda x,y:(x,y),
                              ConsumableType=SimpleNamespace(ALTAR_LOCK=1, TP_CRYSTAL=2))
        self.executor = OutcomeExecutor(sdk, lambda:None)

    def test_boolean_success_and_obstruction_for_every_supported_family(self):
        for name in ('move', 'blocked', 'cast_0', 'cast_1', 'ward', 'altar', 'teleport'):
            for result in (False, True):
                with self.subTest(action=name, result=result):
                    self.returned = result; command = Command(name, (2,3))
                    outcome = self.executor.execute(command)
                    self.assertEqual(outcome.requested, command)
                    self.assertTrue(outcome.accepted_attempt)
                    self.assertEqual(outcome.effect_completed, result)
                    expected = ('move' if result else 'blocked') if name in ('move','blocked') else name
                    self.assertEqual(outcome.filter_action, expected)
                    self.assertEqual(outcome.effect_status, 'sdk_reported_completion' if result else 'newly_revealed_obstruction')

    def test_void_result_is_not_invented_effect_success(self):
        outcome = self.executor.execute(Command('priority', priority=-784))
        self.assertTrue(outcome.accepted_attempt)
        self.assertIsNone(outcome.effect_completed)
        self.assertEqual(outcome.effect_status, 'not_reported')

    def test_exception_has_no_assimilatable_family_or_claimed_effect(self):
        def fail(p): raise RuntimeError('SDK error')
        self.me.place_ward = fail
        with self.assertRaises(RuntimeError): self.executor.execute(Command('ward',(2,3)))
        outcome = self.executor.last_outcome
        self.assertIsNone(outcome.accepted_attempt)
        self.assertIsNone(outcome.effect_completed)
        with self.assertRaises(ValueError): _ = outcome.actual_action

    def test_wrong_boolean_abi_is_explicitly_unknown(self):
        self.returned = None
        with self.assertRaises(TypeError): self.executor.execute(Command('ward',(2,3)))
        self.assertEqual(self.executor.last_outcome.effect_status, 'unexpected_return_type')


if __name__ == '__main__': unittest.main()
