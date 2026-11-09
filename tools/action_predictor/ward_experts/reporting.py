"""Additive complete conditional metrics, matched contrasts and context strata."""
import argparse,json
from pathlib import Path
import numpy as np
from .protocol import ROOT,BASE,JOBS,WORK,REPORT
from .features import SCALARS
from .fit import load
from .evaluate import read,summarize
from ..observation_metrics import correctness,group_samples,interval
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

REQUIRED=('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority')

def freeze():
    value=dict(id='ward-reporting-r2',reason='FreshP00review: addall-familyconditionalmetrics,pairedspecialistcomparisons,TRAINcontexts and correctcompletionbindings;no newfits/thresholds/checkpointchoices.',
        strata=dict(ward_state=['available','unavailable'],charges=['zero','one','two_or_more'],prior_ward=['present_in32actualownroots','unavailable'],coverage=['ward_state_unavailable','no_known_allyordinaryward','known_allyward_disabled_or_not_covering_actor','active_allyward_geometriccoverage_at_actor'],readiness=['channelled','free'],movement=['previous_direction_continuation','direction_change','no_previous'],champion='allobservedchampiontypeswithsupport',engine='2/3separately;engine3DEVonegroupconfounded'),
        comparison='P01-P00 andT01-T00 directmatchedfeaturecontrols, alongsideeachcompletepredictionvsG00. C-vsA isolates typinggivenplacement;C-vsB isolatesplacementgiventyping. Samepaired2000wholeoriginalDEVgroupdraws seed20261106. Correctlytypedconditional ownsubsets andmatchedtypedintersection separated. Emptydenominatorsnull;nosparse-categorycertification.',
        coverage='GeometricallywithinSDKwardradius of knownnon-disabledallyward,notactualLOS. OriginalallDEVrowsretained;contextstrata diagnosticsneverreplaceoverallbenchmark.',
        no_fit_change=True,source_sha256=digest(__file__),new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'reporting-r2-plan.json',value);return value

def parameter_correct(raw,p):
    family=p['family_commands'][np.arange(len(raw['y'])),raw['y']];correct=(family[:,1]==raw['py'])&(raw['py']<289);priority=raw['y']==9;correct[priority]=family[priority,2]==raw['priority'][priority];return correct

def all_family_summary(raw,p,mask,direction):
    out=summarize(raw,p,mask,direction);parameter=parameter_correct(raw,p);_,joint=correctness(raw,p);details={}
    for row in out['per_category']:
        name=row['action'];k=rt.LABELS.index(name);m=mask&(raw['y']==k);typed=m&(p['prediction']==k);n=int(m.sum());tp=int(typed.sum())
        row['correctly_typed_support']=tp
        if name in REQUIRED:
            row['all_true_family_parameter_accuracy']=float(parameter[m].mean()) if n else None;row['all_true_family_parameter_exact']=int(parameter[m].sum());row['parameter_given_correct_type']=float(joint[typed].mean()) if tp else None
            details[name]=dict(support=n,all_true_family_exact=int(parameter[m].sum()),all_true_family_accuracy=float(parameter[m].mean()) if n else None,correctly_typed_support=tp,correctly_typed_parameter_exact=int(joint[typed].sum()),correctly_typed_parameter_accuracy=float(joint[typed].mean()) if tp else None)
    out['all_family_parameters']=details;return out

def paired(raw,p,old,mask,draws,groups):
    _,j=correctness(raw,p);_,oj=correctness(raw,old);a=group_samples(raw,p,mask,draws,groups);b=group_samples(raw,old,mask,draws,groups);out=dict(rows=int(mask.sum()),rescues=int((j&~oj&mask).sum()),regressions=int((~j&oj&mask).sum()),paired95={key:interval(a[key]-b[key]) for key in ('joint_accuracy','macro_f1','joint_nll')});pc=parameter_correct(raw,p);oc=parameter_correct(raw,old);targeting={}
    count=lambda x:np.array([(x&(raw['group']==g)).sum() for g in groups])
    ratio=lambda a,b:np.divide(a,b,out=np.full(a.shape,np.nan,float),where=b>0)
    for family in REQUIRED:
        code=rt.LABELS.index(family);m=mask&(raw['y']==code);pt=m&(p['prediction']==code);ot=m&(old['prediction']==code);both=pt&ot;values={}
        for name,num,den,on,od in [('all_true_family_parameter',pc&m,m,oc&m,m),('correctly_typed_parameter',j&pt,pt,oj&ot,ot),('matched_correctly_typed_parameter',j&both,both,oj&both,both),('joint',j&m,m,oj&m,m)]:
            values[name]=dict(new_correct=int(num.sum()),new_support=int(den.sum()),reference_correct=int(on.sum()),reference_support=int(od.sum()),paired95=interval(ratio(draws@count(num),draws@count(den))-ratio(draws@count(on),draws@count(od))))
        targeting[family]=values
    out['targeting']=targeting;return out

def strata(data,split):
    extra=data['global'][:,573:];value=lambda key:np.asarray(extra[:,33+SCALARS.index(key)]);n=len(extra);state=value('ward_state_available')>0;charges=np.rint(value('charges')*3).astype(int);prior=value('prior_ward_available')>0;coverage=np.full(n,0,np.int8)
    for job in [j for j in json.loads(JOBS.read_text()) if j['split']==split]:
        path=WORK/'games'/job['record']['raw_sha256']/'personal.jsonl'
        for line in path.open():
            row=json.loads(line)
            if row['record']!='ward_pre':continue
            idx=row['index'];ward=[w for w in row['wards'] if w['kind']==3 and w['team']==row['perspective']['team']];coverage[idx]=1 if not ward else 2
            # The SDKrange board includes the actor's cell; get its position
            # from the original query's PRE-only request table, not a label.
        query=json.loads((path.parent/'query.json').read_text());positions={r['index']:r['position'] for r in query['requests']}
        for line in path.open():
            row=json.loads(line)
            if row['record']!='ward_pre':continue
            idx=row['index'];p=positions[idx]
            if any(w['kind']==3 and w['team']==row['perspective']['team'] and not w['disabled'] and max(abs(w['position']['x']-p['x']),abs(w['position']['y']-p['y']))<=w['radius'] for w in row['wards']):coverage[idx]=3
    engine=np.empty(n,np.int8)
    for job in json.loads(JOBS.read_text()):
        if job['split']==split:engine[job['offset']:job['offset']+job['rows']]=int(job['record']['engine_version'][0])
    return {'ward_state_available':{'available':state,'unavailable':~state},'charges':{'zero':charges==0,'one':charges==1,'two_or_more':charges>=2},'prior_ward_history':{'available':prior,'unavailable':~prior},'coverage':{str(k):coverage==k for k in range(4)},'channel':{'channelled':value('channel')!=0,'free':value('channel')==0},'champion':{str(int(k)):data['champion']==k for k in np.unique(data['champion'])},'engine':{str(int(k)):engine==k for k in np.unique(engine)}}

def compact(raw,p,mask):
    _,j=correctness(raw,p);ward=mask&(raw['y']==14);guess=mask&(p['prediction']==14);typed=ward&guess;param=parameter_correct(raw,p);groups=np.unique(raw['group'][mask]);tp=int(typed.sum());fp=int((guess&~ward).sum());fn=int((ward&~guess).sum())
    return dict(rows=int(mask.sum()),ward_support=int(ward.sum()),ward_type_TP=tp,ward_type_FP=fp,ward_type_F1=2*tp/max(1,2*tp+fp+fn),ward_joint=int((j&ward).sum()),ward_conditional=int((param&ward).sum()),overall_exact=int((j&mask).sum()),groups=len(groups),support_by_group={str(int(g)):dict(rows=int((mask&(raw['group']==g)).sum()),ward_rows=int((ward&(raw['group']==g)).sum())) for g in groups})

def run(name,references=None):
    freeze();references=references or ['control'];result={};comparisons={}
    for split in ('train','validation'):
        d=load(split);raw=d['raw'];direction=np.load(BASE.parent/f'v7/{split}-direction.npy');base_masks={'all':np.ones(len(raw['y']),bool)}
        if split=='train':base_masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        context=strata(d,split);context['movement']={str(k):(raw['y']==8)&(direction==k) for k in (1,2,3)};decoders={}
        for decoder in ('primary','joint_MAP'):
            p=read(WORK/f'evaluations/{name}/{split}-{decoder}.npz');decoders[decoder]={sampling:dict(overall=all_family_summary(raw,p,m,direction),contexts={kind:{key:compact(raw,p,m&mask) for key,mask in values.items()} for kind,values in context.items()}) for sampling,m in base_masks.items()}
            if split=='validation':
                groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);comparisons[decoder]={}
                for ref in references:
                    old=read(WORK/f'evaluations/{ref}/{split}-{decoder}.npz');comparisons[decoder][ref]={key:paired(raw,p,old,mask,draws,groups) for key,mask in {'all':base_masks['all'],'ward':raw['y']==14,'recall':raw['y']==10,'move':raw['y']==8}.items()}
        result[split]=decoders
    immutable_json(REPORT/f'{name}-reporting-addendum.json',dict(results=result,paired_DEV=comparisons,source_sha256=digest(__file__),plan_sha256=digest(REPORT/'reporting-r2-plan.json'),original_evaluation_sha256=digest(REPORT/f'{name}-evaluation.json'),qualification='All-family conditional modes generated for everyrow beforemetrictruefamilylookup. Correctlytyped ownsubsets andmatchedintersection separate. Zero-supportstrata retained;five reusedDEVgroups,notuntouched or3seed evidence. Coverage codes0unknown/1noknownallyward/2knownbutnotgeometricallycovering/3geometricallycovering;notLOS.',new_fits=0,reserved_opened=0));print(name,'additive reporting complete',references,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('references',nargs='*');a=p.parse_args();run(a.name,a.references)
