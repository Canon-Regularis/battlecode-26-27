import unittest
import numpy as np
from .priority_inputs import PriorityMemory

class PriorityInputTests(unittest.TestCase):
    def step(self,kind=8,value=None,actor=0):
        result=dict(kind=kind,actor=dict(kind=1,index=actor))
        if value is not None:result['priority']=value
        return result

    def test_exact_signed_values_availability_and_latest_outside_window(self):
        memory=PriorityMemory(0)
        before,history=memory.inputs(dict(current=0,scheduled=None),'1:0',1)
        np.testing.assert_array_equal(before,[0,1,0,0,0,0,0])
        memory.observe(self.step(9,-2147483648),'2:0',1)
        for i in range(3,20):memory.observe(self.step(),f'{i}:0',1)
        values,history=memory.inputs(dict(current=2147483647,scheduled=-2147483648),'20:0',3)
        np.testing.assert_array_equal(values,[2147483647,1,-2147483648,1,-2147483648,1,2])
        self.assertFalse(history[:,1].any())

    def test_prior_target_causality_and_actor_order(self):
        memory=PriorityMemory(0);step=self.step(9,0)
        memory.observe(step,'4:0',1);step['priority']=999
        values,history=memory.inputs(dict(current=0,scheduled=0),'4:0',1)
        self.assertEqual(values[4],0);self.assertEqual(values[5],1)
        self.assertEqual(history[-1].tolist(),[0,1])
        with self.assertRaisesRegex(ValueError,'Future'):memory.inputs({},'3:0',1)
        with self.assertRaises(ValueError):memory.observe(self.step(),'4:0',1)
        with self.assertRaises(ValueError):memory.observe(self.step(actor=1),'5:0',1)
        with self.assertRaises(ValueError):memory.observe(self.step(9,1.5),'5:0',1)

    def test_complete_action_order_masks_zero_vs_missing(self):
        memory=PriorityMemory(0)
        memory.observe(self.step(9,0),'2:0',1)
        memory.observe(self.step(),'3:0',1)
        memory.observe(self.step(9,600),'5:0',2)
        values,history=memory.inputs(dict(current=0,scheduled=600),'6:0',2)
        np.testing.assert_array_equal(history[-3:],[[0,1],[0,0],[600,1]])
        np.testing.assert_array_equal(values,[0,1,600,1,600,1,0])

if __name__=='__main__':unittest.main()
