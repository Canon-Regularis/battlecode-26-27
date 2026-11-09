"""Future achieved positions are TRAINING TARGETS, never inferred Fish intent."""
import argparse,json
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from .sequence_data import ROOT,BASE,JOBS,WORK,REPORT
from ..rich_data import read_turns
from ..audit import immutable_json
from ..data import digest

def positions(job):
    values=[];known=[]
    for t in read_turns(job['manifest'],job['record']):
        for d in t['decisions']:
            p=d['observation']['own'].get('position');values.append([p['x']/32,p['y']/32] if p else [0,0]);known.append(p is not None)
    assert len(values)==job['rows'];return job['offset'],np.asarray(values,np.float32),np.asarray(known,bool)

def prepare(split):
    plan=REPORT/'achieved-goal-plan.json'
    immutable_json(plan,dict(purpose='Ground latent strategic hypotheses in demonstrated future achieved position, not hand-named goals or true-intent labels.',target='First recorded personal PRE in SAME actor stream at least16actualownroots later and at most64later. Target is achieved worldposition; availability explicit, no nearest-future-convenient destination selection. Horizon is supervision only, never a runtime switch deadline.',inference='Current position is a personal input. Future target position/index/availability and current recorded action NEVER enter predict/proposal/retention; used only loss and postprediction evaluation. Forward filter posterior updated using previous actualcommand only. No backward smoothing.',model='4learned latent embeddings, learned predicted relative goal positions and Gaussian uncertainties. Persistent arm carries prior world-goal estimates plus belief; reset arm recomputes. Execution receives learned predicted relative goal, never future truth. Both arms same auxiliaryweight.05, underlyingfullcommandNLL unchanged.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0))
    jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split];n=sum(j['rows'] for j in jobs);p=np.zeros((n,2),np.float32);known=np.zeros(n,bool)
    with ProcessPoolExecutor(max_workers=2) as pool:
        for k,(start,values,available) in enumerate(pool.map(positions,jobs),1):
            p[start:start+len(values)]=values;known[start:start+len(values)]=available
            if k%20==0 or k==len(jobs):print('Achieved goal positions',split,k,'/',len(jobs),flush=True)
    with np.load(BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz') as z:np.testing.assert_array_equal(known,z['pos_known'])
    with np.load(WORK/f'{split}-sequences.npz') as z:order=z['order'];offsets=z['offsets'];g=z['gap']
    # Exact integer gaps are encoded by log1p; check rounding error before using.
    decoded=np.expm1(g[:,0].astype(np.float64)*8);delta=np.rint(decoded).astype(np.int64);assert np.abs(decoded-delta).max()<.05
    future=np.full(n,-1,np.int32);valid=np.zeros(n,bool);goal=np.zeros((n,2),np.float32)
    for a,b in zip(offsets[:-1],offsets[1:]):
        ids=order[a:b];ordinal=np.cumsum(delta[a:b])-1;j=np.searchsorted(ordinal,ordinal+16)
        for i,at in enumerate(j):
            if at<len(ids) and ordinal[at]-ordinal[i]<=64 and known[ids[i]] and known[ids[at]]:
                row=ids[i];future[row]=ids[at];valid[row]=True;goal[row]=p[ids[at]]
    dest=WORK/f'{split}-goals.npz';assert not dest.exists();np.savez_compressed(dest,position=p,position_known=known,future_row=future,achieved_position=goal,goal_target_available=valid)
    immutable_json(REPORT/f'{split}-goals.json',dict(rows=n,available_targets=int(valid.sum()),sha256=digest(dest),plan_sha256=digest(plan),source_sha256=digest(__file__),sequence_receipt_sha256=digest(REPORT/f'{split}-sequences.json'),qualification='Missing goal targets do NOT remove command rows or count as strategy failures. Future endpoint is demonstrated achieved state, not Fish intent. Target fields may be consumed only by training losses/postprediction metrics.',new_fits=0,reserved_opened=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);prepare(p.parse_args().split)
