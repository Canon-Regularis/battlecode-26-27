"""All-row fixed-state and causal-refiltered probability-consistent readouts."""
import json,subprocess
import sys
import numpy as np
import torch
from .sequence_data import ROOT,WORK,REPORT
from .data import load,chunks,causal_inputs,geometry
from .model import SPATIAL
from .inference import select_state
from .retention_gradients import fingerprint
from .pathway_inputs import contrast,CONTRASTS
from .pathway_protocol import LOCAL,OUT,freeze
from .pathway_reference import load_model,command_targets
from ..audit import immutable_json
from ..data import digest


def empty(n,priority):
    out={k:np.full(n,-1,np.int64) for k in ('prediction','coordinate','proposed_coordinate')}
    out.update(priority=priority.copy(),top5=np.full((n,5),-1,np.int64),
        nll=np.zeros(n,np.float64),type_nll=np.zeros(n,np.float64),param_nll=np.zeros(n,np.float64))
    return out


def first_rank(logp,target):
    row=torch.arange(len(target));truth=logp[row,target]
    earlier=torch.arange(logp.shape[1])[None]<target[:,None]
    return 1+((logp>truth[:,None])|((logp==truth[:,None])&earlier)).sum(1)


@torch.no_grad()
def run(identifier):
    freeze();torch.set_num_threads(2)
    execution_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    reference_path=OUT/f'Q01-{identifier}-reference.json'
    reference=json.loads(reference_path.read_text())['reference']
    directory=LOCAL/f'Q01/{identifier}';assert not directory.exists(),'Preserve previous attempted attribution'
    directory.mkdir(parents=True)
    model,saved,checkpoint=load_model(identifier);before=fingerprint(model);d=load('validation',saved)
    n=len(d['raw']['y']);assert n==14439
    labels=['baseline']+[f'{mode}/{name}' for mode in ('fixed','refilter') for name in CONTRASTS]
    states={name:model.empty(32) for name in ['baseline']+[f'refilter/{c}' for c in CONTRASTS]}
    predictions={name:empty(n,d['priority_mode']) for name in labels}
    diagnostics={name:dict(head_modes=np.full((n,4),-1,np.int64),
        recorded_probability=np.full(n,np.nan,np.float64),recorded_rank=np.full(n,-1,np.int64),
        conditional_TV=np.full(n,np.nan,np.float64),component_JS=np.full(n,np.nan,np.float64),
        prior=np.zeros((n,4),np.float32),retention=np.zeros(n,np.float32)) for name in labels}
    seen=np.zeros(n,np.uint8);normalization_error=0.;next_progress=5000
    for rows in chunks(d['sequences']):
        for ids in rows:
            valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid)
            inputs=causal_inputs(d,ix);geo=geometry(d,ix)
            original=model.begin(**inputs,state=states['baseline'])
            steps={'baseline':original}
            for c in CONTRASTS:
                steps[f'fixed/{c}']=contrast(model,original,inputs,reference,c)
                filtered=model.begin(**inputs,state=states[f'refilter/{c}'])
                steps[f'refilter/{c}']=contrast(model,filtered,inputs,reference,c)
            forecast={}
            for name,step in steps.items():
                # Every branch forecasts before the current recorded answer is
                # read. Future achieved labels are not accessed in this module.
                forecast[name]=model.decode(step,**geo,priority_mode=torch.from_numpy(d['priority_mode'][ix]),
                    priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ix]))
            target=command_targets(d,ix);y=target['y'].numpy()
            for name,step in steps.items():
                p=forecast[name];out=predictions[name];diag=diagnostics[name]
                out['prediction'][ids[valid]]=p['prediction'].numpy()[valid]
                out['proposed_coordinate'][ids[valid]]=p['coordinate'].numpy()[valid]
                loss,post=model.observed(step,**geo,**target)
                out['nll'][ids[valid]]=loss.numpy()[valid]
                type_nll=-p['type_logp'][torch.arange(32),target['y']].numpy()
                out['type_nll'][ids[valid]]=type_nll[valid]
                out['param_nll'][ids[valid]]=loss.numpy()[valid]-type_nll[valid]
                for family,lp in p['parameter_logp'].items():
                    selected=valid&(y==family)
                    if selected.any():
                        out['coordinate'][ids[selected]]=lp.argmax(-1).numpy()[selected]
                        out['top5'][ids[selected]]=lp.topk(5,-1).indices.numpy()[selected]
                diag['prior'][ids[valid]]=step['logprior'].exp().numpy()[valid]
                diag['retention'][ids[valid]]=step['retain'].numpy()[valid]
                normalization_error=max(normalization_error,float((p['type_logp'].double().exp().sum(-1)-1).abs().max()))
                for family in (8,3):
                    selected=valid&(y==family)
                    if not selected.any():continue
                    # Full original batch shape, exactly as the decoder. True
                    # family is used ONLY for postforecast diagnostics.
                    codes=torch.full((32,),family,dtype=torch.long)
                    heads=model.spatial_log_probs(step,**geo,family=codes)
                    diag['head_modes'][ids[selected]]=heads.argmax(-1).numpy()[selected]
                    lp=p['parameter_logp'][family];baseline=forecast['baseline']['parameter_logp'][family]
                    middle=torch.logsumexp(heads.double(),1)-np.log(4)
                    js=(.25*(heads.double().exp()*(heads.double()-middle[:,None])).sum((1,2))).numpy()
                    diag['component_JS'][ids[selected]]=js[selected]
                    diag['conditional_TV'][ids[selected]]=(.5*(lp.double().exp()-baseline.double().exp()).abs().sum(-1)).numpy()[selected]
                    available=selected&(d['raw']['py'][ix]>=0)&(d['raw']['py'][ix]<289)
                    if available.any():
                        truth=torch.from_numpy(d['raw']['py'][ix[available]]).long()
                        sub=lp[available].double()
                        diag['recorded_probability'][ids[available]]=sub[torch.arange(len(truth)),truth].exp().numpy()
                        diag['recorded_rank'][ids[available]]=first_rank(sub,truth).numpy()
                    normalization_error=max(normalization_error,float((lp.double().exp().sum(-1)-1).abs().max()))
                if name in states:states[name]=select_state(states[name],post,mask)
                # Fixed-state shadow posteriors are deliberately discarded.
            seen[ids[valid]]+=1
        if int(seen.sum())>=next_progress:
            print('Q01 causal forecasts',identifier,int(seen.sum()),'/',n,flush=True);next_progress+=5000
    assert np.all(seen==1) and fingerprint(model)==before
    assert normalization_error<=2e-6,normalization_error
    with np.load(WORK/f'runs/{identifier}/validation-predictions.npz') as z:archived={k:z[k] for k in z.files}
    baseline=predictions['baseline'];differences={}
    for key in ('prediction','coordinate','proposed_coordinate','priority','top5'):
        np.testing.assert_array_equal(baseline[key],archived[key])
    for key in ('nll','type_nll','param_nll'):
        differences[key]=float(np.abs(baseline[key]-archived[key]).max());assert differences[key]<=2e-5
    bindings={}
    for name in labels:
        tag=name.replace('/','--');path=directory/f'{tag}-predictions.npz';other=directory/f'{tag}-diagnostics.npz'
        np.savez_compressed(path,**predictions[name]);np.savez_compressed(other,**diagnostics[name])
        bindings[name]=dict(predictions_sha256=digest(path),diagnostics_sha256=digest(other))
    immutable_json(OUT/f'Q01-{identifier}-ready.json',dict(execution_commit=execution_commit,branches=bindings,rows=n,
        baseline_integer_arrays_exact=True,baseline_loss_max_discrepancy=differences,
        maximum_probability_normalization_error=normalization_error,weights_unchanged=True,
        checkpoint_sha256=digest(checkpoint),reference_receipt_sha256=digest(reference_path),
        original_predictions_sha256=digest(WORK/f'runs/{identifier}/validation-predictions.npz'),
        input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),protocol_sha256=digest(OUT/'Q01-plan.json'),
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0))
    print('Q01 completed causal attribution',identifier,len(labels),'branches; baseline parity passed',flush=True)


if __name__=='__main__':run(sys.argv[1])
