"""Recovery denominator, permitted-field and unavailable-value contracts."""
import copy
import unittest
import numpy as np
from .recover import validate_jobs,request_row,validate_row
from .protocol import ROWS


class RecoveryContracts(unittest.TestCase):
    def test_canonical_denominators_and_reserved_rejection(self):
        jobs=[];serial=0
        for split,count in (('train',470),('validation',25)):
            offset=0
            for i in range(count):
                rows=ROWS[split]-(count-1) if i==0 else 1
                jobs.append(dict(split=split,offset=offset,rows=rows,record=dict(raw_sha256=f'{serial:064x}',engine_version='2.0.0')))
                serial+=1;offset+=rows
        validate_jobs(jobs[::-1])
        bad=copy.deepcopy(jobs);bad[0]['split']='reserved'
        with self.assertRaises(RuntimeError):validate_jobs(bad)
        bad=copy.deepcopy(jobs);bad[1]['offset']-=1
        with self.assertRaisesRegex(RuntimeError,'overlap|gap'):validate_jobs(bad)

    def test_request_cannot_receive_recorded_answer_and_unknown_is_not_observed_zero(self):
        turn=dict(actor=7,round=3,view={'team':0})
        decision=dict(pre_cursor='9:3',label={'kind':'priority','argument':900},transaction_label={'gold':-42})
        values=np.array([0,0,13,1,-7,1,4],np.int64)
        a=request_row(11,turn,decision,values,0)
        decision['label']={'kind':'ward','position':[1,2]};decision['transaction_label']={'gold':999}
        self.assertEqual(a,request_row(11,turn,decision,values,0))
        self.assertNotIn('label',a);self.assertNotIn('transaction_label',a)
        row=dict(record='order_pre',row=11,pre='9:3',actor=7,own=dict(current=None,current_available=False,scheduled=13,scheduled_available=True),
                 others=[dict(known=True,role='enemy',current=None,current_available=False,scheduled=2080375425,scheduled_available=True)])
        result=validate_row(row,a);self.assertIsNone(result['others'][0]['current'])
        poisoned=copy.deepcopy(row);poisoned['own']['transaction_label']={'gold':123};poisoned['others'][0]['answer']=999
        cleaned=validate_row(poisoned,a)
        self.assertNotIn('transaction_label',cleaned['own']);self.assertNotIn('answer',cleaned['others'][0])
        bad=copy.deepcopy(row);bad['others'][0]['current']=0
        with self.assertRaisesRegex(RuntimeError,'availability'):validate_row(bad,a)


if __name__=='__main__':unittest.main()
