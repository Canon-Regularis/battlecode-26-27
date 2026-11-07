"""SDK call recording only: no engine or hypothetical game-state simulation."""
import unittest
from types import SimpleNamespace
from .execution import Command,SDK4Executor,UnsupportedCommand,AmbiguousTarget

class TestExecution(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.move_result=False;me=SimpleNamespace(move_absolute=lambda p:self.calls.append(('move',p)) or self.move_result,attack=lambda t:self.calls.append(('attack',t)),set_priority=lambda p:self.calls.append(('priority',p)),abilities=lambda:[SimpleNamespace(valid_targets=lambda:19,use=lambda p:self.calls.append(('cast',p)))],buy=lambda *args:self.calls.append(('buy',args)));self.executor=SDK4Executor(SimpleNamespace(me=lambda:me,Vec2=lambda x,y:(x,y)),lambda:self.calls.append(('cancel',)))
    def test_blocked_is_move_attempt_and_actual_result(self):
        r=self.executor.execute(Command('move',(2,3)));self.assertEqual(r.actual_action,'blocked');self.assertEqual(self.calls,[('move',(2,3))])
    def test_no_fabricated_shop(self):
        with self.assertRaises(UnsupportedCommand):self.executor.execute(Command('shop'))
        self.assertEqual(self.calls,[])
    def test_no_arbitrary_entity_resolution(self):
        with self.assertRaises(AmbiguousTarget):self.executor.execute(Command('attack',(2,3)),('a','b'))
        self.assertEqual(self.calls,[])
    def test_mixed_cast_not_silently_ground(self):
        with self.assertRaises(AmbiguousTarget):self.executor.execute(Command('cast_0',(2,3)))
        self.assertEqual(self.calls,[])
    def test_integer_priority_not_classifier_label(self):
        self.executor.execute(Command('priority',priority=-784));self.assertEqual(self.calls,[('priority',-784)])

if __name__=='__main__':unittest.main()
