"""S00 selection forensics: cached scores, saved epochs and gradients; NO fit."""
import json
from pathlib import Path
import numpy as np
import torch
from .saved import ROOT,OLD,WORK,REPORT,read,arrays,joint
from ..algorithmic.study import matches
from ..algorithmic_fit import Selector
from ..algorithmic_corrections import canonical
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def group_index(c):
    ids=np.full(c.shape[:2],31,np.int64);reps=np.zeros((len(c),32),np.int64)
    for i,row in enumerate(c):
        mapping={}
        for j,command in enumerate(row):
            if command[0]<0:continue
            key=tuple(command);k=mapping.setdefault(key,len(mapping));ids[i,j]=k;reps[i,k]=j
    return ids,reps

def group_mass(w,ids):
    mass=np.zeros((len(w),32),np.float64);np.add.at(mass,(np.arange(len(w))[:,None],ids),w[:,1:]);mass[:,31]=0
    return mass

def stats(raw,c,base,p,mask,ids,reps):
    w=p['selector_weights'];m=matches(c,raw['y'],raw['py'],raw['priority']);L=m.any(1);B=joint(raw,base);J=joint(raw,p);G=group_mass(w,ids);best=G.argmax(1);row=np.arange(len(w));point_correct=m[row,reps[row,best]];P=(w[:,1:]*m).sum(1);F=w[:,0];available=L|B;miss=mask&available&~J;rescue=mask&L&~B
    assert np.array_equal(J,((F>=G.max(1))&B)|((F<G.max(1))&point_correct))
    def quant(v):return {str(q):float(np.quantile(v,q)) for q in (.1,.5,.9)} if len(v) else None
    partition={
        'correct_point_is_top_point_but_fallback_vetoes':miss&L&point_correct&(F>=G.max(1)),
        'wrong_point_ranks_first_and_fallback_is_used':miss&L&~point_correct&(F>=G.max(1)),
        'wrong_point_is_selected':miss&L&~point_correct&(F<G.max(1)),
        'only_G00_correct_but_overridden':miss&~L&B}
    assert sum(int(v.sum()) for v in partition.values())==int(miss.sum())
    mixture=P+F*np.exp(-base['nll'].astype(np.float64));grad_correct=P-np.divide(P,mixture,out=np.zeros_like(P),where=mixture>0);gradF=F-np.divide(F*np.exp(-base['nll'].astype(np.float64)),mixture,out=np.zeros_like(P),where=mixture>0)
    return dict(rows=int(mask.sum()),available=int((available&mask).sum()),correct=int((J&mask).sum()),available_misses=int(miss.sum()),miss_partition={k:int(v.sum()) for k,v in partition.items()},rescuable_G00_errors=int(rescue.sum()),rescues=int((rescue&J).sum()),capture_rate=float(J[rescue].mean()) if rescue.any() else None,correct_point_top_among_points_on_rescuable=int((rescue&point_correct).sum()),fallback_weight_on_rescuable=quant(F[rescue]),correct_group_weight_on_rescuable=quant(P[rescue]),correct_group_probability_given_point_branch=quant(np.divide(P,1-F,out=np.zeros_like(P),where=1-F>0)[rescue]),correct_group_logit_gradient_on_rescuable=dict(mean=float(grad_correct[rescue].mean()) if rescue.any() else None,quantiles=quant(grad_correct[rescue])),fallback_logit_gradient_on_rescuable=dict(mean=float(gradF[rescue].mean()) if rescue.any() else None,quantiles=quant(gradF[rescue])),fallback_only_rows=int((mask&~L).sum()),fallback_only_mean_gradient=float(gradF[mask&~L].mean()) if (mask&~L).any() else None,wrong_type_on_available_misses=int((miss&(p['prediction']!=raw['y'])).sum()),correct_type_wrong_arguments_on_available_misses=int((miss&(p['prediction']==raw['y'])).sum()))

def loader(split):
    path=OLD/('v5/combined-train.npz' if split=='train' else 'v4/validation.npz')
    raw=arrays(path,['y','py','priority','group']);c=np.load(OLD/f'v10/{split}-candidates.npy',mmap_mode='r')[:,1];base=arrays(OLD/f'v9/runs/G00/{split}-predictions.npz');a={}
    for name in ('A00','A01'):a[name]=arrays(OLD/f'v10/runs/{name}/{split}-predictions.npz')
    return raw,c,base,a

def features(indices):
    path=OLD/'v5/combined-train.npz'
    with np.load(path) as z:x=z['x'][indices];h=z['history'][indices,-8:].copy()
    spatial=np.zeros(h.shape[:2],bool)
    for name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','end'):spatial|=h[:,:,rt.LABELS.index(name)]>0
    h[:,:,16:18]*=spatial[:,:,None]
    return np.concatenate((x,h.reshape(len(h),-1)),1).astype(np.float32)

def run():
    rt.setup(20261123);WORK.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
    immutable_json(REPORT/'S00-plan.json',dict(source_sha256=digest(__file__),purpose='Why does selection fail when correctcommandalreadyavailable? Nooptimizer,refit,architecturechange,newcandidates orreplayrecovery. Previousproductiontrainingpausepersists.',analyses=['Exact command-group ranking/fallback partition using savedTRAIN/DEVA00/A01scores','Actualmixtureprobability versus hardchosencommand using existingDEVG00candidateprobabilities and fixedD00','Analytic same-loss logit gradients on all storedscores;gradient directions are local diagnostics,notcauses bythemselves','All23savedA00epochs on fixed8192naturalTRAINsample andalloriginalDEV;descriptiveonly,noalternatecheckpointselected','Local8pairedgradientmeasurements betweenrescuable andfallback-onlynaturalTRAINstrata,512rowspersubset;nooptimizer','Tanh saturation/clippingonfixedsample;descriptivenotproofofoptimizerfailure'],selection='Currentanswers onlyfor scoring/conditionaldiagnostics;nevermodelinput. Initialweightsderivedfromfrozenbias4/-4. Originalround17remainsselected. Bothreservedpartitionssealed. No oldexposedtest.',new_fits=0))
    natural=np.load(OLD/'v9/frequency/natural-mask.npy');rng=np.random.default_rng(20261123);sample=rng.choice(np.flatnonzero(natural),8192,replace=False);sample.sort();allstats={};saved={}
    for split in ('train','validation'):
        raw,c,base,a=loader(split);ids,reps=group_index(c);mask=natural if split=='train' else np.ones(len(c),bool);summary={}
        for name,p in a.items():
            summary[name]={'all':stats(raw,c,base,p,mask,ids,reps)}
            for code,label in enumerate(rt.LABELS):
                if (mask&(raw['y']==code)).any():summary[name][label]=stats(raw,c,base,p,mask&(raw['y']==code),ids,reps)
        allstats[split]=summary
        # Retain only the fixed natural sample for costly checkpoint/gradient work.
        ix=sample if split=='train' else np.arange(len(c));saved[split]=dict(raw={k:v[ix] for k,v in raw.items()},c=np.array(c[ix]),base={k:v[ix] for k,v in base.items()},ids=ids[ix],reps=reps[ix],a={name:{k:v[ix] for k,v in p.items()} for name,p in a.items()})
        if split=='validation':
            probability_path=OLD/'v10/validation-G00-candidate-probability.npy';prob=np.load(probability_path);assert digest(probability_path)==read(ROOT/'tools/action_predictor/experiments/v10/D00.json')['G00_candidate_probability_sha256'];p=a['A00'];w=p['selector_weights'];m=matches(c,raw['y'],raw['py'],raw['priority']);P=(w[:,1:]*m).sum(1);G=group_mass(w,ids);best=G.argmax(1);row=np.arange(len(c));fallback=w[:,0]>=G.max(1);slot=reps[row,best];qchosen=np.where(fallback,prob[:,0],prob[row,slot+1]);chosen_mass=np.where(fallback,0,G[row,best])+w[:,0]*qchosen;true_mass=P+w[:,0]*np.exp(-base['nll'].astype(float));J=joint(raw,p);B=joint(raw,base);available=m.any(1)|B;d=arrays(OLD/'v10/runs/A00/D00-validation-predictions.npz');D=joint(raw,d)
            allstats['decoder']=dict(available_misses=int((available&~J).sum()),correct_command_higher_mixture_probability_than_chosen=int((available&~J&(true_mass>chosen_mass+1e-7)).sum()),fixed_D00_fixes_A00_errors=int((~J&D).sum()),fixed_D00_regresses_A00_correct=int((J&~D).sum()),fixed_D00_fixes_available_misses=int((available&~J&D).sum()),fixed_D00_remaining_available_misses=int((available&~D).sum()),meaning='D00isfixednonfittingboundedobservedrepresentationdecoder,notglobalMAPorcompletepurchaseprobability. Strictshopsstillfail. Nochoosingnewdecoderfromthisstudy.')
    # New forward passes ask how ranking evolved, not whether old inference still
    # reproduces. Existing immutable data/prediction receipts are reused.
    train=saved['train'];dev=saved['validation'];train['x']=features(sample)
    with np.load(OLD/'v4/validation.npz') as z:x=z['x'];h=z['history'][:,-8:].copy()
    spatial=np.zeros(h.shape[:2],bool)
    for name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','end'):spatial|=h[:,:,rt.LABELS.index(name)]>0
    h[:,:,16:18]*=spatial[:,:,None];dev['x']=np.concatenate((x,h.reshape(len(h),-1)),1).astype(np.float32);trace=[];directory=OLD/'v10/runs/A00';receipt=read(ROOT/'tools/action_predictor/experiments/v10/A00-completion-addendum.json');bindings={}
    for epoch in range(1,24):
        cp=directory/f'round-{epoch:02d}.pt';expected=receipt['files'][str(cp.relative_to(ROOT))];assert digest(cp)==expected;bindings[str(cp.relative_to(ROOT))]=expected;s=torch.load(cp,weights_only=False,map_location='cpu');model=Selector(len(s['mean']));model.load_state_dict(s['state']);model.eval();row=dict(epoch=epoch,sets={})
        for split,d in saved.items():
            norm=np.clip((d['x']-s['mean'])/s['std'],-10,10);available=np.column_stack((np.ones(len(norm),bool),d['c'][:,:,0]>=0));weights=[]
            with torch.no_grad():
                for start in range(0,len(norm),1024):weights.append(model(torch.from_numpy(norm[start:start+1024]),torch.from_numpy(available[start:start+1024])).exp().numpy())
            w=np.concatenate(weights);m=matches(d['c'],d['raw']['y'],d['raw']['py'],d['raw']['priority']);B=joint(d['raw'],d['base']);G=group_mass(w,d['ids']);best=G.argmax(1);point=m[np.arange(len(w)),d['reps'][np.arange(len(w)),best]];J=np.where(w[:,0]>=G.max(1),B,point);rescue=m.any(1)&~B;mixture=(w[:,1:]*m).sum(1)+w[:,0]*np.exp(-d['base']['nll'].astype(float))
            row['sets'][split]=dict(rows=len(w),joint_correct=int(J.sum()),rescuable=int(rescue.sum()),rescues=int((J&rescue).sum()),capture=float(J[rescue].mean()),nll=float(-np.log(np.maximum(mixture,1e-300)).mean()),fallback_rows=int((w[:,0]>=G.max(1)).sum()))
        trace.append(row)
    # Analytic gradient directions at the selected checkpoint, no optimizer.
    selected=torch.load(directory/'round-17.pt',weights_only=False,map_location='cpu');model=Selector(len(selected['mean']));model.load_state_dict(selected['state']);model.eval();norm_unclipped=(train['x']-selected['mean'])/selected['std'];X=torch.from_numpy(np.clip(norm_unclipped,-10,10));available=torch.from_numpy(np.column_stack((np.ones(len(X),bool),train['c'][:,:,0]>=0)));M=matches(train['c'],train['raw']['y'],train['raw']['py'],train['raw']['priority']);B=joint(train['raw'],train['base']);strata=[np.flatnonzero(M.any(1)&~B),np.flatnonzero(~M.any(1))];q=np.exp(-train['base']['nll'].astype(float));mass=torch.from_numpy(np.column_stack((q,M.astype(float))));gradient=[]
    for k in range(8):
        vectors=[]
        for pool in strata:
            ix=rng.choice(pool,min(512,len(pool)),replace=False);lp=model(X[ix],available[ix]);loss=-torch.logsumexp(lp.double()+mass[ix].clamp_min(1e-300).log(),-1).mean();gs=torch.autograd.grad(loss,list(model.parameters()));vectors.append((torch.cat([g.flatten() for g in gs]),torch.cat([g.flatten() for g in gs[:2]]),float(loss.detach())))
        gradient.append(dict(pair=k,all_parameter_cosine=float(F_cos(vectors[0][0],vectors[1][0])),shared_input_layer_cosine=float(F_cos(vectors[0][1],vectors[1][1])),rescusable_loss=vectors[0][2],fallback_only_loss=vectors[1][2]))
    with torch.no_grad():activation=torch.tanh(model.net[0](X)).numpy()
    diagnostics=dict(input_clipped_element_fraction=float((np.abs(norm_unclipped)>10).mean()),tanh_abs_over_099_fraction=float((np.abs(activation)>.99).mean()),local_gradient_pairs=gradient,interpretation='Samefrozenloss,selectedcheckpoint,evalmode(no dropout),naturalTRAINsample. Conflict/saturationmeasurementsarenotproofwhyoptimizationfailed;nooptimizerupdated.')
    immutable_json(REPORT/'S00-selection.json',dict(plan_sha256=digest(REPORT/'S00-plan.json'),source_sha256=digest(__file__),stats=allstats,epoch_trace=trace,input_diagnostics=diagnostics,checkpoint_bindings=bindings,natural_sample_seed=20261123,natural_sample_rows=len(sample),new_fits=0,reserved_opened=0,original_selected_epoch=17))
    print(json.dumps(dict(dev=allstats['validation']['A00']['all'],train=allstats['train']['A00']['all'],decoder=allstats['decoder'],diagnostics=diagnostics),indent=2),flush=True)

def F_cos(a,b):return torch.nn.functional.cosine_similarity(a[None],b[None])[0]
if __name__=='__main__':run()
