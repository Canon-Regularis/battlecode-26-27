"""TRAIN-only reference inputs from unchanged, forward-filtered checkpoints."""
import json,subprocess
import numpy as np
import torch
from .sequence_data import ROOT,BASE,WORK,REPORT
from .model import GoalPolicy
from .data import load,chunks,causal_inputs,geometry
from .inference import select_state
from .retention_gradients import fingerprint
from .pathway_inputs import features
from .pathway_protocol import LOCAL,OUT,freeze
from ..priority_fit_v3 import load_base
from ..audit import immutable_json
from ..data import digest


def command_targets(d,ix):
    """For loss/filter assimilation AFTER forecasting; no future-target fields."""
    return dict(y=d['inputs']['y'][ix],py=d['inputs']['py'][ix],
        priority_parameter_nll=torch.from_numpy(d['baseline']['param_nll'][ix]))


def load_model(identifier):
    teacher,saved=load_base();info=json.loads((REPORT/f'{identifier}.json').read_text())
    path=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(path)==info['checkpoint_sha256']
    checkpoint=torch.load(path,weights_only=False)
    assert torch.equal(saved['mean'],checkpoint['mean']) and torch.equal(saved['std'],checkpoint['std'])
    model=GoalPolicy(teacher,True);model.load_state_dict(checkpoint['state']);model.eval()
    return model,saved,path


@torch.no_grad()
def run():
    freeze();torch.set_num_threads(2)
    execution_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    directory=LOCAL/'Q01/references';directory.mkdir(parents=True,exist_ok=True)
    natural_path=BASE.parent/'v9/frequency/natural-mask.npy'
    assert digest(natural_path)=='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    natural=np.load(natural_path);index=np.flatnonzero(natural);assert len(index)==288801
    inverse=np.full(len(natural),-1,np.int64);inverse[index]=np.arange(len(index))
    d=None
    for identifier in ('L01','L02'):
        path=directory/f'{identifier}-features.npz';assert not path.exists(),'Preserve attempted reference producer'
        model,saved,checkpoint=load_model(identifier)
        if d is None:d=load('train',saved)
        before=fingerprint(model);state=model.empty(32);seen=np.zeros(len(natural),np.uint8)
        bank=np.full((len(index),4,5),np.nan,np.float32);known=np.asarray(d['goals']['position_known'][index])
        with np.load(WORK/f'runs/{identifier}/train-goals.npz') as z:archived_world=z['world'];archived_retention=z['retention']
        maximum_world_difference=0.;maximum_retention_difference=0.
        for rows in chunks(d['sequences']):
            for ids in rows:
                valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid)
                inputs=causal_inputs(d,ix);step=model.begin(**inputs,state=state)
                selected=valid&natural[ix]
                if selected.any():bank[inverse[ix[selected]]]=features(step,inputs).numpy()[selected]
                if valid.any():
                    maximum_world_difference=max(maximum_world_difference,float(np.abs(step['world'].numpy()[valid]-archived_world[ids[valid]]).max()))
                    maximum_retention_difference=max(maximum_retention_difference,float(np.abs(step['retain'].numpy()[valid]-archived_retention[ids[valid]]).max()))
                # Only the action already forecast/represented by this PRE is
                # assimilated now, so it is past evidence at the next decision.
                target=command_targets(d,ix)
                _,post=model.observed(step,**geometry(d,ix),**target)
                state=select_state(state,post,mask);seen[ids[valid]]+=1
        assert np.all(seen==1) and np.isfinite(bank).all()
        np.testing.assert_array_equal(bank[:,:,4],np.repeat(known[:,None],4,axis=1))
        assert (bank[~known,:,:2]==0).all() and known.any() and (~known).any()
        assert maximum_world_difference==0 and maximum_retention_difference==0 and fingerprint(model)==before
        refs=dict(geometry_known=bank[known,:,:2].mean(0,dtype=np.float64).astype(np.float32),
            uncertainty_by_position_known=np.stack([bank[known==v,:,2:4].mean(0,dtype=np.float64) for v in (False,True)]).astype(np.float32),
            availability=bank[:,:,4].mean(0,dtype=np.float64).astype(np.float32))
        actual_mean=bank.mean(0,dtype=np.float64);frequency=float(known.mean())
        reference_mean=np.concatenate((frequency*refs['geometry_known'].astype(np.float64),
            (1-frequency)*refs['uncertainty_by_position_known'][0].astype(np.float64)+frequency*refs['uncertainty_by_position_known'][1].astype(np.float64),
            refs['availability'][:,None].astype(np.float64)),1)
        w=model.goal_condition.weight.double().numpy()
        mean_projection_difference=float(np.abs((actual_mean-reference_mean)@w.T).max())
        assert mean_projection_difference<=1e-6
        np.savez_compressed(path,index=index,position_known=known,features=bank)
        payload=dict(execution_commit=execution_commit,reference={k:v.tolist() for k,v in refs.items()},natural_rows=len(index),
            position_known_rows=int(known.sum()),position_unknown_rows=int((~known).sum()),
            actual_mean_input=actual_mean.tolist(),mean_reference_input=reference_mean.tolist(),
            max_mean_projection_difference=mean_projection_difference,
            original_world_max_difference=maximum_world_difference,original_retention_max_difference=maximum_retention_difference,
            weights_unchanged=True,checkpoint_sha256=digest(checkpoint),feature_bank_sha256=digest(path),
            natural_mask_sha256=digest(natural_path),input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
            protocol_sha256=digest(OUT/'Q01-plan.json'),source_sha256=digest(__file__),new_fits=0,reserved_opened=0)
        immutable_json(OUT/f'Q01-{identifier}-reference.json',payload)
        print('TRAIN reference completed',identifier,len(index),'max mean projection difference',mean_projection_difference,flush=True)


if __name__=='__main__':run()
