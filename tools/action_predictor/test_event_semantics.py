import unittest
from .event_semantics import classification,earlier

class EventSemanticsTests(unittest.TestCase):
    def test_automatic_cancel_is_not_root_cancel(self):
        step=dict(kind=16,phase=10,substep=0,actor=dict(kind=1,index=2))
        self.assertEqual(classification(step),'cancel')
        self.assertEqual(classification(step|dict(substep=1)),'effect')
        self.assertEqual(classification(step|dict(phase=14)),'system')

    def test_yield_rollover_error_stay_distinct(self):
        step=dict(phase=10,substep=0,actor=dict(kind=1,index=2))
        self.assertEqual([classification(step|dict(kind=k)) for k in (8,26,27)],['end','rollover','error'])

    def test_exact_prior_event_and_actor(self):
        current=dict(actor=2,pre='20:3',event='21:0')
        earlier(dict(actor=2,event='20:0'),current)
        earlier(None,current)
        with self.assertRaises(AssertionError):earlier(dict(actor=3,event='20:0'),current)
        with self.assertRaises(AssertionError):earlier(dict(actor=2,event='21:0'),current)

if __name__=='__main__':unittest.main()
