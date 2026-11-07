"""R00: natural-sampling errors, oracle support and fixed-model generalization."""
import json
from pathlib import Path
from collections import Counter
import numpy as np
from ..data import digest
from ..audit import immutable_json
from ..algorithmic.study import matches
from .. import reliable_train as rt

ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'.cambc/action-predictor/v11';REPORT=ROOT/'tools/action_predictor/experiments/v11'
OLD=ROOT/'.cambc/action-predictor'
def read(path):return json.loads(Path(path).read_text())
def arrays(path,keys=None):
    with np.load(path) as z:return {k:z[k] for k in (keys or z.files)}
def joint(raw,p):return matches(np.stack((p['prediction'],p['coordinate'],p['priority']),-1)[:,None],raw['y'],raw['py'],raw['priority']).any(1)

def metrics(raw,p,mask,weights=None):
    y=raw['y'][mask];guess=p['prediction'][mask];j=joint(raw,p)[mask];n=len(y);w=np.ones(n) if weights is None else weights[mask];total=w.sum();k=len(rt.LABELS);matrix=np.bincount(y*k+guess,weights=w,minlength=k*k).reshape(k,k);f1=2*matrix.diagonal()/np.maximum(matrix.sum(0)+matrix.sum(1),1e-30)
    return dict(rows=n,weight_sum=float(total),strict_correct=int(j.sum()),strict=float(w@j/total) if total else None,macro_f1=float(f1[1:].mean()),observed_nll=float(w@p['nll'][mask]/total) if total else None,per_family={name:dict(rows=int((y==code).sum()),type_TP=int(((y==code)&(guess==code)).sum()),joint=int(j[y==code].sum()),joint_accuracy=float((w[y==code]@j[y==code])/w[y==code].sum()) if w[y==code].sum() else None,type_FP=int(((y!=code)&(guess==code)).sum()),joint_FP=int((guess==code).sum()-j[y==code].sum())) for code,name in enumerate(rt.LABELS)},confusion=matrix.tolist())

def run():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    immutable_json(REPORT/'R00-plan.json',dict(source_sha256=digest(__file__),purpose='Root-cause investigation;pause production training/architecture experiments. Use saved predictions/candidates and identity-verified naturalmask; no unchangedheavyrecovery.',definitions='Only fixed-support missing-vs-selection errors form a disjoint partition. Representation/training/semantics are possible overlapping causes, not assignable labels. Coverage is oracle diagnostic, not accuracy.',sampling='Natural288801TRAINrows from original470games/94groups vs all14439DEVrows25games/5groups. Original denominators preserved. Also report originalaugmentedTRAIN433071rows. Directstandardization by originalDEVaction,engine,andmovementcontinuationcontext on commoncells is diagnosticonly; disclose missing support.',movement='Frozen prospective R01 diagnostic:49eligiblegames(first12TRAINperengine+all25DEV), naturalTRAINselectedrows, originalDEV. Compare nearestcamp/lowestHPcamp/enemy/bank/home objectives, geometric and uniformterrainfield costs, bothyx/xyties, optimumtiesets/progresssets as separateoracles. Also fixed past5move-progress goal ranking (roundgap<=3) from trueearlierownrootencodings, no future smoothing. Currenttruth used only to score. No costthreshold tunedonDEV.',fit='Only one bounded R02 capacity probe may be used: existing M01 architecture from scratch,small natural diverse subset, freshgroup-separatedTRAINfold, noDEVcheckpoint selection, no newlarge model. Protocol must be frozen separately before any optimization. Required freshSolxhighreview after completedfit.',safety='Reserved75+75sealed;nooldexposedtest,matches/proposedsimulations,downloads,botchanges,deployment. Old artifacts preserved.'))
    maskpath=OLD/'v9/frequency/natural-mask.npy';ready=read(ROOT/'tools/action_predictor/experiments/v9/frequency-data-ready.json');assert digest(maskpath)==ready['mask_sha256'];natural=np.load(maskpath);assert natural.sum()==288801 and len(natural)==433071
    paths={'train':OLD/'v5/combined-train.npz','validation':OLD/'v4/validation.npz'};expected={'train':'39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb','validation':'01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'};raw={}
    for s,path in paths.items():assert digest(path)==expected[s];raw[s]=arrays(path,['y','py','priority','group'])
    jobs=read(OLD/'v7/jobs.json');engine={s:np.zeros(len(r['y']),np.int8) for s,r in raw.items()};bindings={str(maskpath):digest(maskpath)}
    for j in jobs:
        assert j['split'] in engine;engine[j['split']][j['offset']:j['offset']+j['rows']]=int(j['record']['engine_version'][0])
    direction={s:np.load(OLD/f'v7/{s}-direction.npy') for s in raw};pred={};results={}
    for model in ('M01','P05','G00','G01','A00','A01'):
        pred[model]={};results[model]={}
        for s in raw:
            if model in ('M01','P05'):path=OLD/f'v9/D02-{model}-train.npz' if s=='train' else OLD/f"{'v5' if model=='M01' else 'v8'}/runs/{model}/validation-predictions.npz"
            else:path=OLD/f"{'v10' if model.startswith('A') else 'v9'}/runs/{model}/{s}-predictions.npz"
            p=arrays(path);pred[model][s]=p;bindings[str(path)]=digest(path)
            masks={'all':np.ones(len(raw[s]['y']),bool)}
            if s=='train':masks['natural']=natural;masks['augmentation_only']=~natural
            results[model][s]={name:metrics(raw[s],p,m) for name,m in masks.items()}
            base=natural if s=='train' else masks['all'];contexts={}
            for name,m in [('move_continuing',(raw[s]['y']==8)&(direction[s]==2)),('move_change',(raw[s]['y']==8)&(direction[s]==3)),('engine2',engine[s]==2),('engine3',engine[s]==3)]:contexts[name]=metrics(raw[s],p,base&m)
            results[model][s]['contexts']=contexts
            results[model][s]['groups']={str(int(g)):metrics(raw[s],p,base&(raw[s]['group']==g)) for g in np.unique(raw[s]['group'])}
    # Standardize natural TRAIN frequencies to DEV cells; no redefined benchmark.
    cells={s:list(zip(raw[s]['y'].tolist(),engine[s].tolist(),np.where(raw[s]['y']==8,direction[s],0).tolist())) for s in raw};traincounts=Counter(c for c,m in zip(cells['train'],natural) if m);devcounts=Counter(cells['validation']);w=np.array([devcounts[c]/traincounts[c] if m and c in devcounts else 0 for c,m in zip(cells['train'],natural)]);common=np.array([c in traincounts for c in cells['validation']]);standard={}
    for model in results:standard[model]=dict(TRAIN_natural_standardized=metrics(raw['train'],pred[model]['train'],natural,w),DEV_common_cells=metrics(raw['validation'],pred[model]['validation'],common),DEV_unmatched_rows=int((~common).sum()))
    partitions={}
    for s in raw:
        c=np.load(OLD/f'v10/{s}-candidates.npy',mmap_mode='r')[:,1];L=matches(c,raw[s]['y'],raw[s]['py'],raw[s]['priority']).any(1);B=joint(raw[s],pred['G00'][s]);ceiling=L|B;base=natural if s=='train' else np.ones(len(L),bool);partitions[s]={}
        for model in ('G00','A00','A01'):
            actual=joint(raw[s],pred[model][s]);items={}
            for name,m in [('all',base)]+[(n,base&(raw[s]['y']==i)) for i,n in enumerate(rt.LABELS)]:
                error=m&~actual;missing=error&~ceiling;selection=error&ceiling;assert missing.sum()+selection.sum()==error.sum()
                items[name]=dict(rows=int(m.sum()),actual_correct=int((actual&m).sum()),point_library_covered=int((L&m).sum()),union_with_G00_ceiling=int((ceiling&m).sum()),errors=int(error.sum()),missing_from_point_plus_G00=int(missing.sum()),available_but_not_selected=int(selection.sum()),point_available_but_wrong=int((error&L).sum()),G00_errors_rescuable=int((m&L&~B).sum()),rescued_G00_errors=int((m&~B&actual).sum()))
            partitions[s][model]=items
    # Existing support revisions are TRAIN only; never generate DEV library rows.
    support={}
    for name in ('C01','C02'):
        c=np.load(OLD/f'v10/{name}-train-candidates.npy',mmap_mode='r');c=c[:,0] if name=='C01' else c;L=matches(c,raw['train']['y'],raw['train']['py'],raw['train']['priority']).any(1);B=joint(raw['train'],pred['G00']['train']);support[name]={a:dict(rows=int((natural&(raw['train']['y']==i)).sum()),covered=int((L&natural&(raw['train']['y']==i)).sum()),with_G00=int(((L|B)&natural&(raw['train']['y']==i)).sum())) for i,a in enumerate(rt.LABELS)}
    output=dict(source_sha256=digest(__file__),bindings=bindings,original_data_sha256=expected,natural_mask_receipt_sha256=digest(ROOT/'tools/action_predictor/experiments/v9/frequency-data-ready.json'),models=results,natural_standardized=standard,fixed_support_partition=partitions,natural_support_revisions=support,notes=['All original DEV rows retained;43shops always strictfailures','Existingmodel TRAINpredictions are in-sample,notgroupheldout;fresh diagnosticfold must initializefromscratch','Standardization controls observedcellfrequencies only,not maps/opponents/policyversions or all difficulty','Representation/generalization/semantics hypotheses overlap;cannot add them as five causal error buckets'],new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'R00-saved.json',output);print('R00 saved evidence complete',flush=True)
    for name in ('G00','A00','A01'):print(name,results[name]['train']['natural']['strict'],results[name]['validation']['all']['strict'],partitions['validation'][name]['all'],flush=True)

if __name__=='__main__':run()
