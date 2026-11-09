"""Immutable correction: separate pure uniform ties from the G00 probability tail."""
import json
import numpy as np
from .protocol import BASE,WORK,REPORT
from .features import INDICES
from .fit import load
from ..audit import immutable_json
from ..data import digest

def run():
    original=REPORT/'placement-baselines.json';old=json.loads(original.read_text());results={}
    for split in ('train','validation'):
        data=load(split);ward=np.flatnonzero(data['raw']['y']==14);mask=np.array(data['mask'][ward]);have=mask.any(-1);coordinate=np.where(have,INDICES[mask.argmax(-1)],290);target=data['raw']['py'][ward];correct=(coordinate==target)&have;count=mask.sum(-1)
        row=dict(rows=len(ward),exact=int(correct.sum()),accuracy=float(correct.mean()),conditional_nll=float(np.log(count).mean()) if have.all() else None,unsupported_target_rows=int((~have).sum()),tie='Lowest coordinate index among valid cells; no G00 probabilities or learned tail')
        if split=='train':
            m=np.load(BASE.parent/'v9/frequency/natural-mask.npy')[ward];row['natural']=dict(rows=int(m.sum()),exact=int(correct[m].sum()),accuracy=float(correct[m].mean()))
        retained=dict(old['results'][split]);retained['uniform_plus_G00_tail']=retained.pop('uniform');retained['pure_uniform']=row;results[split]=retained
    immutable_json(REPORT/'placement-baselines-correction.json',dict(original_receipt_sha256=digest(original),results=results,correction='The old uniform control was mixed with1e-4G00tail, which selects its mode on exactuniformties. Preserve itsmeasurement withcorrectname; pureuniformdoesnotuseG00. No model/checkpoint/prediction changes.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0));print({s:r['pure_uniform'] for s,r in results.items()},flush=True)

if __name__=='__main__':run()
