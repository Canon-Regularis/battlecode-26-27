"""Add per-category losses and six previously omitted diagnostic bindings."""
import argparse,json
import numpy as np
from .protocol import ROOT,BASE,WORK,REPORT
from .data import read
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest

def run(identifier):
    receipt=ROOT/'tools/action_predictor/experiments/v7/data-ready.json';ready=json.loads(receipt.read_text());bindings={};results={};archives={}
    for split in ('train','validation'):
        for name in ('direction','available','near_obstacle'):
            path=BASE.parent/f'v7/{split}-{name}.npy';h=digest(path);assert h==ready['files'][path.name];bindings[str(path.relative_to(ROOT))]=h
        path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        with np.load(path) as z:y=z['y']
        forecasts={identifier:read(WORK/f'runs/{identifier}/{split}-predictions.npz'),'G00':read(BASE.parent/f'v9/runs/G00/{split}-predictions.npz')}
        paths={identifier:WORK/f'runs/{identifier}/{split}-predictions.npz','G00':BASE.parent/f'v9/runs/G00/{split}-predictions.npz'}
        if identifier=='X00':
            forecasts['S00']=read(WORK/f'runs/S00/{split}-predictions.npz');paths['S00']=WORK/f'runs/S00/{split}-predictions.npz'
        archives[split]={k:digest(p) for k,p in paths.items()};masks={'all':np.ones(len(y),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        results[split]={}
        for sampling,base in masks.items():
            rows=[]
            for k,name in enumerate(rt.LABELS):
                m=base&(y==k);n=int(m.sum());values={}
                for model,p in forecasts.items():values[model]=dict(observed_joint_nll=float(p['nll'][m].mean(dtype=np.float64)) if n else None,type_nll=float(p['type_nll'][m].mean(dtype=np.float64)) if n else None,observed_argument_nll=float(p['param_nll'][m].mean(dtype=np.float64)) if n and name!='shop' else None)
                unchanged=bool(np.array_equal(forecasts[identifier]['nll'][m],forecasts['G00']['nll'][m])) if name not in ('move','blocked') else None
                rows.append(dict(action=name,support=n,losses=values,nonmovement_loss_exactly_unchanged=unchanged,shop_argument_likelihood='absent, never correct or zero-imputed' if name=='shop' else None))
            results[split][sampling]=rows
    immutable_json(REPORT/f'{identifier}-loss-supplement.json',dict(results=results,diagnostic_inputs=bindings,V7_receipt_sha256=digest(receipt),prediction_archives_sha256=archives,fit_report_sha256=digest(REPORT/f'{identifier}.json'),completion_sha256=digest(REPORT/f'{identifier}-completion.json'),source_sha256=digest(__file__),command=f'python -m tools.action_predictor.movement_experts.loss_supplement {identifier}',interpretation='Additive S00 review correction; original category tables/receipts unchanged. All/natural sampling separated; observed loss only, no shop-argument likelihood. Six unchanged diagnostic arrays verified by their original V7 receipt, no extraction or inference rerun.',new_fits=0,reserved_opened=0));print(identifier,'category losses and diagnostic bindings complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');run(p.parse_args().identifier)
