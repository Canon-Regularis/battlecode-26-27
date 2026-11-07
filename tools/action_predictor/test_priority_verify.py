import copy
import unittest
import numpy as np
from .priority_verify import validate_metadata,validate_arrays,validate_layout,validate_slice

def arrays():
    v=np.zeros((3,7),np.int64);v[:,0]=[1,2,3];v[:,1]=1
    return dict(values=v,history=np.zeros((3,16,2),np.int64),last_outside_window=np.zeros(3,bool))

class PriorityVerificationTests(unittest.TestCase):
    def test_stale_cache_metadata_is_rejected(self):
        job=dict(record=dict(raw_sha256='raw',engine_version='2.0.0'),split='train',rows=737,shard='target.npz',shard_sha256='digest')
        receipt=dict(raw_sha256='raw',engine='2.0.0',split='train',rows=737,target_shard_sha256='digest')
        validate_metadata(job,copy.deepcopy(job),receipt)
        for field,value in [('rows',738),('split','invalid'),('shard','nonexistent.npz')]:
            changed=copy.deepcopy(job);changed[field]=value
            with self.assertRaises(AssertionError):validate_metadata(changed,job,receipt)
        for field,value in [('raw_sha256','other'),('engine','3.0.0'),('rows',738),('split','validation'),('target_shard_sha256','stale')]:
            changed=receipt|{field:value}
            with self.assertRaises(AssertionError):validate_metadata(job,job,changed)

    def test_permuted_merge_rejected_despite_valid_shape_masks(self):
        local=arrays();merged={k:v.copy() for k,v in local.items()}
        validate_slice(merged,local,0,3)
        merged['values']=merged['values'][[1,0,2]]
        validate_arrays(merged,3)
        with self.assertRaisesRegex(AssertionError,'Merged alignment'):validate_slice(merged,local,0,3)

    def test_offset_coverage_and_unique_membership(self):
        jobs=[dict(record=dict(raw_sha256='a'),split='train',offset=0,rows=2),
              dict(record=dict(raw_sha256='b'),split='train',offset=2,rows=1)]
        validate_layout(jobs,{'train':3})
        for offset in (0,1,3):
            wrong=copy.deepcopy(jobs);wrong[1]['offset']=offset
            with self.assertRaises(AssertionError):validate_layout(wrong,{'train':3})
        wrong=copy.deepcopy(jobs);wrong[1]['record']['raw_sha256']='a'
        with self.assertRaises(AssertionError):validate_layout(wrong,{'train':3})
        with self.assertRaises(AssertionError):validate_layout(jobs,{'train':4})

    def test_canonical_missing_values_and_mask_relationships(self):
        data=arrays();validate_arrays(data,3)
        for column,value in [(2,1),(4,99),(6,1),(1,2)]:
            bad={k:v.copy() for k,v in data.items()};bad['values'][0,column]=value
            with self.assertRaises(AssertionError):validate_arrays(bad,3)
        data['history'][0,-1]=[0,1];data['values'][0,5]=1
        validate_arrays(data,3) # observed zero argument remains available
        data['values'][0,4]=1
        with self.assertRaises(AssertionError):validate_arrays(data,3)

if __name__=='__main__':unittest.main()
