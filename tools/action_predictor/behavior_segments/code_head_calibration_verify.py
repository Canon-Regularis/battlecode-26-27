"""Reproduce the negative V50 calibration and its unchanged V49 checkpoint."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import code_head_calibration as calibration,expanded_code_fit as previous,code_weight_fit as first,model
from .rare_code_edit import metrics
from ..audit import immutable_json
from ..data import digest


def run():
    torch.set_num_threads(1);start=time.perf_counter();root=calibration.ROOT
    plan=json.loads((calibration.REPORT/'plan.json').read_text())
    result=json.loads((calibration.REPORT/'result.json').read_text())
    selected=json.loads((calibration.REPORT/'selection.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in plan[kind].items():assert digest(root/p)==h,p
    for p,h in result['bindings'].items():assert digest(root/p)==h,p
    assert result['selection_sha256']==digest(calibration.REPORT/'selection.json')
    assert selected['plan_sha256']==digest(calibration.REPORT/'plan.json')
    _,architecture,data,ids=previous.inputs();x=[];y=[];folds=[]
    net=model.SegmentPolicy(architecture['schema'],8).eval()
    with torch.no_grad():
        for fold in range(4):
            net.load_state_dict(torch.load(root/plan['fold_checkpoints'][str(fold)],map_location='cpu',weights_only=False)['model'])
            _,held=previous.partition_indices(ids,fold)
            for begin in range(0,len(held),16):
                item=first.take(data,held[begin:begin+16]);mask=item['observed'].bool()
                logits=first.code_forward(net,item)[mask];labels=item['labels'][mask]
                x.extend(logits.double().numpy());y.extend(labels.tolist());folds.extend([fold]*len(labels))
    x=np.asarray(x);y=np.asarray(y);folds=np.asarray(folds)
    bank=np.load(calibration.WORK/'fitting-logits.npz')
    for name,value in [('logits',x),('labels',y),('folds',folds)]:np.testing.assert_array_equal(value,bank[name])
    maps=json.loads((calibration.WORK/'fold-maps.json').read_text());traces=json.loads((calibration.WORK/'trace.json').read_text())
    def summary(values):
        return dict(correct=int((values.argmax(1)==y).sum()),rows=len(y),codes=metrics(y,values.argmax(1)),
                    nll=float(F.cross_entropy(torch.from_numpy(values),torch.from_numpy(y))))
    candidates={'identity':summary(x)}
    for reg in plan['regularizations']:
        values=np.empty_like(x)
        for fold in range(4):
            train,held=folds!=fold,folds==fold
            a,b,trace=calibration.solve(x[train],y[train],reg,time.perf_counter()+60)
            saved=maps[f'{reg:g}/{fold}']
            np.testing.assert_array_equal(a,saved['matrix']);np.testing.assert_array_equal(b,saved['bias'])
            assert trace==traces[f'{reg:g}/{fold}'];values[held]=x[held]@a.T+b
        candidates[f'{reg:g}']=summary(values)
    assert candidates==selected['candidates']
    winner=min(candidates,key=lambda k:(-candidates[k]['correct'],candidates[k]['nll'],-(float(k) if k!='identity' else float('inf'))))
    assert winner==selected['selected']==result['selected']=='identity'
    base=torch.load(previous.WORK/'selected.pt',map_location='cpu',weights_only=False)['model']
    saved=torch.load(calibration.WORK/'selected.pt',map_location='cpu',weights_only=False)
    assert all(torch.equal(v,saved['model'][k]) for k,v in base.items())
    assert digest(calibration.WORK/'selected.pt')==selected['checkpoint_sha256']
    assert result['changed_tensors']==[] and result['new_outer_inference'] is False
    prior=json.loads((previous.REPORT/'result.json').read_text())
    for split in ('fit','evaluation'):
        assert result['results'][split]==prior['results'][split]
        assert json.loads((calibration.WORK/f'{split}-predictions.json').read_text())==json.loads((previous.WORK/f'{split}-predictions.json').read_text())
    proof=json.loads((previous.REPORT/'verification.json').read_text())
    assert proof['result_sha256']==digest(previous.REPORT/'result.json')
    assert result['target_met'] is False
    immutable_json(calibration.REPORT/'verification.json',dict(result_sha256=digest(calibration.REPORT/'result.json'),
        source_sha256=digest(Path(__file__)),fitting_logits_reproduced=len(y),calibration_fits_reproduced=16,
        all_maps_and_objective_traces_exact=True,selection_reproduced=True,all_model_tensors_unchanged=True,
        copied_forecasts_exact=dict(fit=2945,evaluation=699),
        inherited_inference_proof_sha256=digest(previous.REPORT/'verification.json'),new_outer_inference=False,
        seconds=time.perf_counter()-start))
    print('Verified identity selection,16calibrations and unchanged V49 results',flush=True)


if __name__=='__main__':run()
