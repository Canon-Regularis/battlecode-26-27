"""Post-A01 review corrections. No altered predictions, fits or old receipts."""
import json
import numpy as np
from .algorithmic.study import ROOT,WORK,REPORT
from .algorithmic_fit import load,evaluate
from .observation_metrics import correctness,group_samples,interval
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

SPATIAL={rt.LABELS.index(x) for x in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport')}
def canonical(pred):
    n=len(pred['prediction']);c=np.column_stack((pred['prediction'],np.full(n,-1),np.zeros(n,np.int64)))
    mask=np.isin(c[:,0],list(SPATIAL));c[mask,1]=pred['coordinate'][mask];mask=c[:,0]==9;c[mask,2]=pred['priority'][mask]
    return c

def paired(raw,new,old,mask):
    _,j=correctness(raw,new);_,b=correctness(raw,old);groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);a=group_samples(raw,new,mask,draws,groups);c=group_samples(raw,old,mask,draws,groups)
    return dict(rows=int(mask.sum()),new_correct=int(j[mask].sum()),old_correct=int(b[mask].sum()),rescues=int((j&~b&mask).sum()),regressions=int((~j&b&mask).sum()),paired95={key:interval(a[key]-c[key]) for key in ('joint_accuracy','joint_nll','macro_f1')},group_net=[int(((j.astype(int)-b.astype(int))*mask)[raw['group']==g].sum()) for g in groups],qualification='2000pairedwholegroupdrawsseed20261106;5reusedDEVgroups,conditionaloncheckpointselection;notselectionadjusted/untouched/3seed')

def run():
    d=load('validation');raw=d['raw'];n=len(raw['y']);paths={name:WORK/f'runs/{name}/validation-predictions.npz' for name in ('A00','A01')};paths['D00']=WORK/'runs/A00/D00-validation-predictions.npz';p={}
    for name,path in paths.items():
        with np.load(path) as z:p[name]={k:z[k] for k in z.files}
    probability_path=WORK/'validation-G00-candidate-probability.npy';d00=json.loads((REPORT/'D00.json').read_text());assert digest(probability_path)==d00['G00_candidate_probability_sha256'];prob=np.load(probability_path)
    assert digest(paths['D00'])==d00['prediction_sha256']
    changes=(canonical(p['D00'])!=canonical(p['A00'])).any(1);types=p['D00']['prediction']!=p['A00']['prediction']
    with np.load(ROOT/'.cambc/action-predictor/v5/combined-train.npz') as z:ty=z['y'];tp=z['priority']
    v,c=np.unique(tp[ty==9],return_counts=True);freq=dict(zip(v,c));support=np.array([freq.get(x,0) for x in raw['priority']]);priority={}
    for name in ('A00','A01'):
        priority[name]={};_,joint=correctness(raw,p[name])
        for stratum,mask in [('all',raw['y']==9),('rare',(raw['y']==9)&(support>0)&(support<20)),('unseen',(raw['y']==9)&(support==0))]:
            typed=mask&(p[name]['prediction']==9);error=p[name]['priority'][typed].astype(np.int64)-raw['priority'][typed].astype(np.int64)
            priority[name][stratum]=dict(true_support=int(mask.sum()),typed_coverage=int(typed.sum()),joint_correct=int(joint[mask].sum()),all_true_family_MAE=None,all_true_family_max_error=None,correctly_typed_MAE=float(np.abs(error).mean()) if len(error) else None,correctly_typed_max_error=int(np.abs(error).max()) if len(error) else None,correctly_typed_wrong_sign=int((np.sign(p[name]['priority'][typed])!=np.sign(raw['priority'][typed])).sum()))
    base=d['baseline'];basecommand=canonical(dict(prediction=base['prediction'],coordinate=base['proposed_coordinate'],priority=base['priority']));commands=np.concatenate((basecommand[:,None],d['c']),1);control=basecommand.copy()
    for i in range(n):
        valid=np.flatnonzero(commands[i,:,0]>=0);control[i]=commands[i,valid[np.argmax(prob[i,valid])]]
    controlpred=dict(prediction=control[:,0],coordinate=control[:,1],priority=control[:,2],nll=base['nll'])
    controlpath=WORK/'runs/A00/D00-posthoc-G00-probability-control.npz'
    if not controlpath.exists():np.savez_compressed(controlpath,**controlpred)
    else:
        with np.load(controlpath) as z:
            for key in controlpred:np.testing.assert_array_equal(z[key],controlpred[key])
    info=json.loads((REPORT/'A01.json').read_text());direction=np.load(ROOT/'.cambc/action-predictor/v7/validation-direction.npy')
    result=dict(source_sha256=digest(__file__),review_sha256=digest(REPORT/'A01-review.md'),supersedes_fields={'D00.json':['changed_commands','unqualified exact command probability/confidence interpretation'],'A00-analysis.json':['priority all-true error scalars'],'A01-analysis.json':['priority all-true error scalars'],'A01-completion-addendum.json':['commands','serving_receipt']},D00_semantic_changes=dict(total=int(changes.sum()),types=int(types.sum()),same_type_required_arguments=int((changes&~types).sum())),priority=priority,A01_vs_A00={name:paired(raw,p['A01'],p['A00'],mask) for name,mask in [('overall',np.ones(n,bool)),('except_recall',raw['y']!=10)]},posthoc_G00_probability_control=dict(scope='Added after reviewer observed D00 results. Same bounded commands, G00probability only, no learned point mass or fit. Not prospective confirmation or promotion.',metrics=evaluate(raw,controlpred,direction),D00_vs_control=paired(raw,p['D00'],controlpred,np.ones(n,bool)),predictions_sha256=digest(controlpath)),D00_probability_qualification='Bounded ranking/confidence is for implemented observed command representation where modeled; shop is an action-only marginalized bucket, NOT complete original APIcommand probability.51shopforecasts remain strictfailures;coordinate ambiguity does not certify entity identity. Not globalMAP.',A01_reproduction=dict(shared_prerequisites=['algorithmic.study train','algorithmic.study validation'],execution_modules=['algorithmic_conditioned','algorithmic_conditioned_roundtrip','algorithmic_analysis A01','algorithmic_corrections'],interpreter='.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.<module> from repo root',descriptor_receipt_sha256=digest(REPORT/'A01-descriptors.json'),serving_receipt_sha256=digest(REPORT/'A01-causal-roundtrip.json'),selected_updates=info['selected_round']*846,completed_updates=len(info['trace'])*846),cost_scope=dict(A01_measured_interval_seconds=info['training_seconds'],A01_sum_round_intervals_seconds=sum(t['seconds'] for t in info['trace']),meaning='Measured interval begins after data/descriptor loading and normalization, includes training rounds, DEV inference, finalTRAIN/DEVinference, serialization and evaluation. Roundintervals includeDEVinference. Neither pureoptimizer time nor totalexperiment cost. Servingcase sets differ;no speedadvantageclaim.',A00_walltime=None),bindings={str(path.relative_to(ROOT)):digest(path) for path in paths.values()},new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'A01-review-corrections.json',result)
    print('semanticchanges',result['D00_semantic_changes']);print('control',result['posthoc_G00_probability_control']['metrics']['strict_correct']);print('paired',result['A01_vs_A00']['overall']);print('priority',priority)

if __name__=='__main__':run()
