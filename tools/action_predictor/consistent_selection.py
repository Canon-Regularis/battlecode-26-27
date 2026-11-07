"""Matched opportunity capture on natural TRAIN and original DEV."""
import json,sys
import numpy as np
from .consistent_study import load
from .consistent_data import BASE,WORK,REPORT
from .algorithmic.study import matches
from .observation_metrics import correctness
from .data import digest
from .audit import immutable_json

def read(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}

def run(identifier):
    reports={}
    for split in ('train','validation'):
        d=load(split);r=d['raw'];p=read(WORK/f'runs/{identifier}/{split}-predictions.npz');_,joint=correctness(r,p);g=read(BASE.parent/f'v9/runs/G00/{split}-predictions.npz');g['coordinate']=g['proposed_coordinate'];_,gj=correctness(r,g);library=matches(d['c'],r['y'],r['py'],r['priority']).any(1)
        old=np.load(BASE.parent/f'v10/{split}-candidates.npy',mmap_mode='r')[:,1];oldcovered=matches(old,r['y'],r['py'],r['priority']).any(1);natural=np.load(BASE.parent/'v9/frequency/natural-mask.npy') if split=='train' else np.ones(len(joint),bool);masks={'all':np.ones(len(joint),bool),'natural':natural} if split=='train' else {'all':natural};result={}
        for name,m in masks.items():
            failure=m&library&~joint;oldop=m&~gj&oldcovered;op=m&~gj&library;n=int(op.sum());oldn=int(oldop.sum());wrongtype=failure&(p['prediction']!=r['y']);same=failure&(p['prediction']==r['y'])
            result[name]=dict(rows=int(m.sum()),exact=int((joint&m).sum()),repaired_library_G00_error_opportunities=n,captured=int((joint&op).sum()),capture_rate=float(joint[op].mean()) if n else None,original_C00_G00_error_opportunities=oldn,captured_on_original_opportunities=int((joint&oldop).sum()),capture_rate_on_original=float(joint[oldop].mean()) if oldn else None,available_command_failures=int(failure.sum()),available_command_wrong_type=int(wrongtype.sum()),available_command_wrong_parameter=int(same.sum()),G00_regressions=int((gj&~joint&m).sum()),per_group={str(int(g)):dict(rows=int((m&(r['group']==g)).sum()),opportunities=int((op&(r['group']==g)).sum()),captured=int((joint&op&(r['group']==g)).sum())) for g in np.unique(r['group'][m])})
        reports[split]=result
    immutable_json(REPORT/f'{identifier}-selection.json',dict(reports=reports,meaning='Achieved predictions on fixed oracle opportunity sets; natural TRAIN identical sampling/strict definitions to DEV, but in-sample TRAIN is not held-out evidence. Original C00 denominator retained to compare with historical13.2%TRAIN rescue rate; new repaired denominator separately labeled.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0));print(identifier,{s:{k:(v['captured'],v['repaired_library_G00_error_opportunities']) for k,v in r.items()} for s,r in reports.items()},flush=True)

if __name__=='__main__':run(sys.argv[1])
