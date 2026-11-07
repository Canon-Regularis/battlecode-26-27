import unittest
from .goal_memory import GoalMemory

class MemoryBoundary(unittest.TestCase):
    def test_unavailable_root_is_accounted_and_future_rejected(self):
        memory=GoalMemory();memory.observe('10:0',dict(kind=8),2,None,{})
        features,belief,progress=memory.descriptors([None]*5,2,'10:1')
        self.assertEqual(memory.missing,1);self.assertEqual(features[12],1);self.assertFalse(belief.any())
        with self.assertRaises(ValueError):memory.descriptors([None]*5,2,'9:0')
        with self.assertRaises(ValueError):memory.observe('10:0',dict(kind=8),2,None,{})

if __name__=='__main__':unittest.main()
