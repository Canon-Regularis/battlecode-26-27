"""Empirical error partitions, not mutually exclusive latent root causes."""
import argparse
import numpy as np
from .protocol import ROOT,BASE,WORK,REPORT
from .data import read
from ..audit import immutable_json
from ..data import digest
from ..observation_metrics import correctness

def run(identifier):
    results={};bindings={}
    for split in ('train','validation'):
        path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        with np.load(path) as z:r={k:z[k] for k in ('y','py','priority','group')}
        p=read(WORK/f'runs/{identifier}/{split}-predictions.npz');parameter,joint=correctness(r,p);typed=p['prediction']==r['y'];shop=r['y']==11;masks={'all':np.ones(len(typed),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        results[split]={}
        for sampling,base in masks.items():
            partitions={}
            for name,m in [('all',base),('move',base&(r['y']==8)),('blocked',base&(r['y']==3))]:
                counts=dict(rows=int(m.sum()),complete_correct=int((joint&m).sum()),wrong_type=int((~typed&m).sum()),correctly_typed_missing_shop_arguments=int((typed&shop&m).sum()),correctly_typed_incorrect_or_unassessed_parameters=int((typed&~shop&~joint&m).sum()),correct_parameter_but_wrong_type=int((parameter&~shop&~typed&m).sum()),perfect_parameters_under_fixed_types_ceiling=int((typed&~shop&m).sum()),perfect_types_under_current_parameters_ceiling=int((parameter&~shop&m).sum()))
                assert sum(counts[k] for k in ('complete_correct','wrong_type','correctly_typed_missing_shop_arguments','correctly_typed_incorrect_or_unassessed_parameters'))==counts['rows'];partitions[name]=counts
            results[split][sampling]=partitions
        bindings[split]=digest(WORK/f'runs/{identifier}/{split}-predictions.npz')
    immutable_json(REPORT/f'{identifier}-error-ledger.json',dict(results=results,prediction_sha256=bindings,source_sha256=digest(__file__),command=f'python -m tools.action_predictor.movement_experts.error_ledger {identifier}',qualification='Disjoint empirical command failures; representation/optimization/history/policy causes remain unresolved and can overlap. Ceilings are for the declared recorded representation/current heads or fixed types, not observation sufficiency or complete unseen API argument recovery. Shops never counted correct.',new_fits=0,reserved_opened=0));print(identifier,'empirical error ledger complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');run(p.parse_args().identifier)
