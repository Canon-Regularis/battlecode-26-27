"""Oracle support of the current nonnegative mixture, separate from accuracy."""
import json,sys
import numpy as np
from .consistent_study import load
from .consistent_data import BASE,WORK,REPORT
from .algorithmic.study import matches
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

def run(split):
    d=load(split);r=d['raw'];library=matches(d['c'],r['y'],r['py'],r['priority']).any(1);modes=d['modes'];q=d['mode-logq'];globalmode=modes[np.arange(len(modes)),q.argmax(-1)][:,None];fallback=matches(globalmode,r['y'],r['py'],r['priority']).any(1);familymode=matches(modes,r['y'],r['py'],r['priority']).any(1);union=library|fallback
    masks={'all':np.ones(len(library),bool)}
    if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
    result={}
    for name,mask in masks.items():
        result[name]=dict(rows=int(mask.sum()),library_covered=int((library&mask).sum()),Q_global_mode_correct=int((fallback&mask).sum()),reachable_union=int((union&mask).sum()),unreachable=int((~union&mask).sum()),family_mode_union_upper_diagnostic=int(((library|familymode)&mask).sum()),per_category={a:dict(rows=int(((r['y']==k)&mask).sum()),library=int((library&(r['y']==k)&mask).sum()),reachable_union=int((union&(r['y']==k)&mask).sum())) for k,a in enumerate(rt.LABELS)})
    immutable_json(REPORT/f'{split}-support.json',dict(results=result,meaning='Points plus global Q mode give the actual hard-decoder oracle ceiling when only nonnegative mixture weights change. Any off-point command with lower Q than its global mode is dominated regardless of weights. Union with every family mode is only a looser diagnostic, not achieved accuracy or exact reachability. Conditional-family parameters still use every family mode.',source_sha256=digest(__file__),inputs_sha256=digest(REPORT/f'{split}-inputs.json'),probabilities_sha256=digest(REPORT/f'{split}-probabilities.json'),new_fits=0,reserved_opened=0))
    print(split,{k:{n:v[n] for n in ('rows','library_covered','reachable_union','unreachable')} for k,v in result.items()},flush=True)

if __name__=='__main__':run(sys.argv[1])
