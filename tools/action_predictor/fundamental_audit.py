"""V9 D02: measured bottlenecks; immutable cache reuse, no optimization."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,sys,time
import numpy as np
import torch
import torch.nn.functional as F
from .priority_fit_v3 import ROOT,BASE,VAL,read,load_base,context_directory
from .priority_residual_fit import head as priority_head
from .priority_head import flatten
from .more_replays import sha,frozen
from .rich_data import read_turns
from .observation_metrics import correctness
from . import reliable_train as rt

WORK=ROOT/'.cambc/action-predictor/v9';REPORTS=ROOT/'tools/action_predictor/experiments/v9'

def log(argv,**fields):
    WORK.mkdir(exist_ok=True)
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(argv=list(map(str,argv)),**fields))+'\n')

def dependencies():
    """Hash relevant frozen dependencies once; do not rerun unchanged recovery."""
    old=ROOT/'tools/action_predictor/experiments/v8';paths={}
    for file,key in [('priority-dependencies-v3.json','sources'),('priority-absolute-modes-sources.json','sources'),('priority-modes-control-sources.json','sources'),('priority-anchor-sources.json','sources'),('priority-residual-modes-sources.json','sources')]:
        p=old/file
        if not p.exists():continue
        for path,digest in read(p)[key].items():assert sha(path)==digest;paths[path]=digest
    for path,digest in read(old/'event-semantics-plan.json')['source_hashes'].items():assert sha(path)==digest;paths[path]=digest
    m01=read(ROOT/'tools/action_predictor/experiments/v5/M01.json');p05=read(old/'P05.json')
    expected={BASE/'combined-train.npz':'39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb',VAL:'01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed',BASE/'runs/M01/model.pt':m01['checkpoint_sha256'],BASE/'runs/M01/validation-predictions.npz':m01['predictions_sha256']}
    for filename,key in [('model.pt','checkpoint_sha256'),('validation-predictions.npz','predictions_sha256')]:expected[BASE.parent/'v8/runs/P05'/filename]=p05[key]
    ready=read(old/'priority-context-ready-v3.json')
    for split in ('train','validation'):expected[context_directory()/(split+'.npy')]=ready['contexts'][split]
    p05plan=read(old/'priority-residual-modes-plan.json')
    for split in ('train','validation'):expected[BASE.parent/('v8/priority-'+split+'.npz')]=p05plan['priority_'+split+'_sha256']
    for path,digest in expected.items():assert sha(path)==digest;paths[str(path)]=digest
    return paths

def arrays(path):
    with np.load(path) as z:return {key:z[key] for key in z.files}

def metrics(raw,pred,direction):
    score=rt.summarize(raw,pred);parameter,joint=correctness(raw,pred);rows=[]
    for i,name in enumerate(rt.LABELS):
        mask=raw['y']==i;n=int(mask.sum());guess=pred['prediction']==i;typed=mask&guess;j=int(joint[mask].sum());tp=int(typed.sum());g=int(guess.sum())
        required=name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority')
        rows.append(dict(action=name,support=n,joint_correct=j,joint_accuracy=j/n if n else None,type_precision=tp/g if g else 0.,type_recall=tp/n if n else None,type_f1=2*tp/(g+n) if g+n else 0.,type_FP=g-tp,joint_FP=g-j,
            parameter_exact=float(parameter[mask].mean()) if required and n else None,parameter_given_correct_type=j/tp if required and tp else None,unassessed=n if name=='shop' else 0))
    move=raw['y']==rt.LABELS.index('move');contexts={}
    for name,code in [('continuing',2),('direction_change',3),('no_previous',1),('zero',4)]:
        mask=move&(direction==code);n=int(mask.sum());contexts[name]=dict(support=n,parameter_exact=float(parameter[mask].mean()) if n else None,joint_exact=float(joint[mask].mean()) if n else None,loss=float(pred['nll'][mask].mean()) if n else None)
    return dict(summary=score,per_category=rows,direction_contexts=contexts,strict_correct=int(joint.sum()),per_group={str(int(g)):dict(rows=int((raw['group']==g).sum()),strict=float(joint[raw['group']==g].mean())) for g in np.unique(raw['group'])})

def p05_overlay(raw,baseline,model):
    checkpoint=torch.load(BASE.parent/'v8/runs/P05/model.pt',weights_only=True,map_location='cpu')
    branch=priority_head(model.priority);branch.load_state_dict(checkpoint['head_state']);branch.eval()
    with np.load(BASE.parent/'v8/priority-train.npz') as z:values=z['values'];features=(flatten(values,z['history']).astype(np.float32)-checkpoint['extra_mean'].numpy())/checkpoint['extra_std'].numpy()
    context=np.load(context_directory()/'train.npy',mmap_mode='r');result={k:v.copy() for k,v in baseline.items()};pcode=rt.LABELS.index('priority')
    with torch.no_grad():
        for a in range(0,len(values),256):
            b=min(a+256,len(values));out=branch(torch.from_numpy(np.array(context[a:b])),torch.from_numpy(features[a:b]));v=torch.from_numpy(values[a:b]);result['priority'][a:b]=branch.integer(out,v).numpy()
            selected=raw['y'][a:b]==pcode
            if selected.any():
                loss=-branch.log_mass(out[selected],torch.from_numpy(raw['priority'][a:b][selected]).long(),v[selected]).numpy();idx=a+np.flatnonzero(selected)
                result['param_nll'][idx]=loss;result['nll'][idx]=result['type_nll'][idx]+loss
            if a%65536==0:print('P05 TRAIN argument inference',a,'/',len(values),flush=True)
    return result,branch,values,features

def fingerprint(model):
    h=hashlib.sha256()
    for key,value in model.state_dict().items():h.update(key.encode());h.update(value.detach().numpy().tobytes())
    return h.hexdigest()

def gradients(model,branch,train,features,values,direction):
    before=fingerprint(model);model.requires_grad_(True);model.eval();branch.requires_grad_(False)
    shared=list(model.current.parameters())+list(model.history.parameters())+list(model.combine.parameters())
    counts=torch.bincount(train['y'],minlength=len(rt.LABELS)).float();weights=(counts.max()/counts.clamp_min(1)).pow(model.config['balance']).clamp_max(20);weights/=weights[train['y']].mean()
    rng=np.random.default_rng(20261107);results=[]
    for batch in range(12):
        indices=rng.choice(len(train['y']),512,replace=False);idx=torch.from_numpy(indices);y=train['y'][idx];py=train['py'][idx]
        logits,context=model(train['x'][idx],train['history'][idx]);ce=F.cross_entropy(logits,y,reduction='none');tasks={'action_weighted':(weights[y]*ce).mean(),'action_unweighted':ce.mean()}
        spatial=py>=0;sp=torch.flatnonzero(spatial) if hasattr(torch,'flatnonzero') else spatial.nonzero().flatten()
        conditional=model.parameter_logits(context[sp],train['grid'][idx[sp]].float(),train['valid'][idx[sp]],y[sp],train['rules'][idx[sp]])
        ce_coord=F.cross_entropy(conditional,py[sp],reduction='none');names=['move','move_change','move_continuing','attack_abilities']
        for name in names:
            mask=(y[sp]==rt.LABELS.index('move')) if name.startswith('move') else ((y[sp]==rt.LABELS.index('attack'))|(y[sp]==rt.LABELS.index('cast_0'))|(y[sp]==rt.LABELS.index('cast_1')))
            if name=='move_change':mask&=torch.from_numpy(direction[indices[sp.numpy()]]==3)
            if name=='move_continuing':mask&=torch.from_numpy(direction[indices[sp.numpy()]]==2)
            if mask.any():tasks[name]=ce_coord[mask].sum()/len(idx)
        priority=y==rt.LABELS.index('priority')
        if priority.any():
            from .reliable_model import priority_log_mass
            tasks['priority_M01']=-priority_log_mass(model.priority(context[priority]),train['priority'][idx[priority]]).sum()/len(idx)
            out=branch(context[priority],torch.from_numpy(features[indices[priority.numpy()]]))
            tasks['priority_P05']=-branch.log_mass(out,train['priority'][idx[priority]].long(),torch.from_numpy(values[indices[priority.numpy()]])).sum()/len(idx)
        vectors={}
        for i,(name,loss) in enumerate(tasks.items()):
            grad=torch.autograd.grad(loss,shared,retain_graph=i<len(tasks)-1,allow_unused=True)
            vectors[name]=torch.cat([g.flatten() if g is not None else torch.zeros_like(p).flatten() for p,g in zip(shared,grad)]).detach()
        pairs={}
        for a,ga in vectors.items():
            for b,gb in vectors.items():
                if a<b:pairs[a+' vs '+b]=float(F.cosine_similarity(ga,gb,dim=0))
        results.append(dict(batch=batch,norms={k:float(v.norm()) for k,v in vectors.items()},cosines=pairs));print('Gradient diagnostic',batch+1,'/12',flush=True)
    assert fingerprint(model)==before;model.requires_grad_(False)
    keys=set().union(*(r['cosines'] for r in results));aggregate={k:dict(mean=float(np.mean([r['cosines'][k] for r in results if k in r['cosines']])),negative_fraction=float(np.mean([r['cosines'][k]<0 for r in results if k in r['cosines']]))) for k in sorted(keys)}
    return dict(batches=results,aggregate=aggregate,checkpoint_values_unchanged=True,scope='Local gradients at one preserved checkpoint on12 fixed TRAIN minibatches, not proof an architectural split will improve validation')

def encoder_audit():
    jobs=read(BASE.parent/'v7/jobs.json');selected=[]
    for version in ('2.0.0','3.0.0'):selected.extend([j for j in jobs if j['split']=='train' and j['record']['engine_version']==version][:12])
    counts=Counter();bindings=[];sample_entities=[]
    for job in selected:
        turns=read_turns(job['manifest'],job['record']);bindings.append(dict(raw=job['record']['raw_sha256'],turns_sha=job['record'].get('augmented_sha256',job['record']['turns_sha256'])))
        for turn in turns:
            for d in turn['decisions']:
                obs=d['observation'];own=obs['own'];by=Counter()
                for e in obs['entities']:
                    if not e.get('known',0)&1 or not e.get('position') or e.get('health',0)<=0 or e['entity']['kind'] not in (1,2):continue
                    kind='camp' if e['entity']['kind']==2 else 'ally' if e.get('team')==own.get('team') else 'enemy';by[kind]+=1;counts['visible_entities']+=1
                    for field in ('type','buffs','cooldowns','abilities','abilityProps','charges'):
                        if field in e:counts['available_'+field]+=1
                    if len(sample_entities)<4:sample_entities.append(e)
                counts['target_rows']+=1
                for kind in ('enemy','ally','camp'):
                    counts[kind+'_entities']+=by[kind];counts[kind+'_omitted_by_nearest3']+=max(0,by[kind]-3);counts[kind+'_rows_over3']+=by[kind]>3
    return dict(sample_games=len(selected),counts=dict(counts),bindings=bindings,examples=sample_entities,
        scope='24 fixed TRAIN games; personally visible living entities only. M01 current-vector keeps nearest3/category and count, omitting entity type/buffs/abilities/cooldowns even for nearest entities. Candidate grid DOES retain aggregates from ALL visible positions/HP/distances; do not claim every far entity disappears. Action classifier does not directly receive that grid.')

def collisions(raw,train,values,features):
    # Representation ambiguity only; no inference inputs or new labels are made.
    tables=[{},{}];rules=train['rules'].numpy();x=train['x'].numpy();h=train['history'].numpy();n=len(x)
    for i in range(n):
        if raw['y'][i]==rt.LABELS.index('shop') or raw['py'][i]>=289:continue
        key=(int(raw['y'][i]),int(raw['py'][i]),int(raw['priority'][i]) if raw['y'][i]==rt.LABELS.index('priority') else 0)
        base=hashlib.blake2b(digest_size=16);base.update(x[i].tobytes());base.update(h[i,-16:].tobytes())
        a=base.digest();tables[0].setdefault(a,Counter())[key[0]]+=1
        base.update(raw['grid'][i].tobytes());base.update(raw['valid'][i].tobytes());base.update(rules[i].tobytes());base.update(features[i].tobytes())
        tables[1].setdefault(base.digest(),Counter())[key]+=1
    out={}
    for name,table in zip(('classifier_encoding','full_current_encoding'),tables):
        rows=sum(sum(c.values()) for c in table.values());conflicts=[c for c in table.values() if len(c)>1]
        out[name]=dict(rows=rows,unique_encodings=len(table),conflicting_encodings=len(conflicts),rows_in_conflicts=sum(sum(c.values()) for c in conflicts),empirical_majority_fraction=sum(max(c.values()) for c in table.values())/rows)
    return dict(results=out,scope='Assessed TRAIN label consistency at identical ENCODED inputs, not identical full personal evidence. Excludes unsupported args only for this diagnostic, retains all benchmark rows elsewhere. Ambiguity can reflect discarded information, missing longer history or stochastic behavior; cannot establish inherent unobservability/randomness. Unique inputs do not prove learnability.')

def run():
    REPORTS.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True);rt.setup(26);start=time.perf_counter();bindings=dependencies()
    frozen(REPORTS/'D02-plan.json',dict(source_sha256=sha(__file__),dependencies=bindings,training_evaluation='All433071originalTRAIN rows; original14439development rows from immutable saved predictions',gradients='12seeded512-row TRAIN minibatches; local gradients only,no optimizer',encoder='First12eligibleTRAIN games per engine,24total; no new context recovery',collision='Exact current encoded inputs, not a proof of latent randomness',no_fits=True,verification='User-requested immutable hash reuse; no unchanged495-game replay reconstruction',reserved='Both75-game partitions sealed, no oldtest,downloads,matches,botchanges,deployment'))
    print('Load original TRAIN arrays for measured predictions',flush=True);raw=arrays(BASE/'combined-train.npz');model,saved=load_base();data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    pred_path=WORK/'D02-M01-train.npz'
    if pred_path.exists():train_pred=arrays(pred_path)
    else:
        train_pred=rt.infer(model,data);np.savez_compressed(pred_path,**train_pred)
    print('M01 full TRAIN inference complete',flush=True)
    p05_path=WORK/'D02-P05-train.npz'
    p05_pred,branch,values,features=p05_overlay(raw,train_pred,model)
    if not p05_path.exists():np.savez_compressed(p05_path,**p05_pred)
    direction=np.load(BASE.parent/'v7/train-direction.npy');val=arrays(VAL);vd=np.load(BASE.parent/'v7/validation-direction.npy')
    result=dict(train_M01=metrics(raw,train_pred,direction),train_P05=metrics(raw,p05_pred,direction),validation_M01=metrics(val,arrays(BASE/'runs/M01/validation-predictions.npz'),vd),validation_P05=metrics(val,arrays(BASE.parent/'v8/runs/P05/validation-predictions.npz'),vd))
    result['gradient_conflicts']=gradients(model,branch,data,features,values,direction)
    result['encoder']=encoder_audit();print('Encoder audit complete',flush=True)
    result['representation_collisions']=collisions(raw,data,values,features)
    result.update(plan_sha256=sha(REPORTS/'D02-plan.json'),source_sha256=sha(__file__),train_predictions_sha256={p.name:sha(p) for p in (pred_path,p05_path)},seconds=time.perf_counter()-start,new_optimizer_steps=0,reserved_opened=0,unobservable_randomness_proven=False)
    frozen(REPORTS/'D02.json',result);print('D02 complete',result['seconds'],'seconds',flush=True)

if __name__=='__main__':
    argparse.ArgumentParser().parse_args();log([sys.executable,'-m','tools.action_predictor.fundamental_audit']);run()
