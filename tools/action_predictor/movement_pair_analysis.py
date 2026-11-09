"""Whole-group matched G01-G00 effects and initialization/compute accounting."""
from pathlib import Path
import csv,sys
import numpy as np
import torch
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base
from .movement_mixture import MovementMixture
from .observation_metrics import correctness,interval,ratio
from .more_replays import frozen,sha

def run():
    reports={n:read(REPORTS/(n+'.json')) for n in ('G00','G01')};plans={n:read(REPORTS/(n+'-plan.json')) for n in reports}
    assert {k:v for k,v in plans['G00'].items() if k not in ('id','specialized')}=={k:v for k,v in plans['G01'].items() if k not in ('id','specialized')}
    initial=[]
    for flag in (False,True):
        rt.setup(26);base,_=load_base();initial.append({k:v.clone() for k,v in MovementMixture(base,flag).state_dict().items()})
    assert all(torch.equal(v,initial[1][k]) for k,v in initial[0].items())
    epochs=min(len(reports['G00']['history']),len(reports['G01']['history']))
    for e in range(1,epochs+1):
        states=[torch.load(WORK/'runs'/n/('epoch-'+str(e)+'.pt'),weights_only=True,map_location='cpu')['rng'] for n in reports];assert torch.equal(*states)
    raw=arrays(VAL);pred={};joint={};param={}
    for n,r in reports.items():
        path=WORK/'runs'/n/'validation-predictions.npz';assert sha(path)==r['predictions_sha256'];pred[n]=arrays(path);param[n],joint[n]=correctness(raw,pred[n])
    for key in ('prediction','priority','type_nll'):np.testing.assert_array_equal(pred['G00'][key],pred['G01'][key])
    direction_path=BASE.parent/'v7/validation-direction.npy';ready=read(REPORTS.parent/'v7/data-ready.json');assert sha(direction_path)==ready['files'][direction_path.name];direction=np.load(direction_path)
    groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(0,len(groups),len(groups)),minlength=len(groups)) for _ in range(2000)])
    def effect(mask,parameters=False):
        values=param if parameters else joint;n=int(mask.sum());counts=np.array([int((mask&(raw['group']==g)).sum()) for g in groups]);delta=values['G01'].astype(np.int8)-values['G00'].astype(np.int8);sums=np.array([int(delta[mask&(raw['group']==g)].sum()) for g in groups])
        return dict(support=n,G00_correct=int(values['G00'][mask].sum()),G01_correct=int(values['G01'][mask].sum()),fixed=int((mask&values['G01']&~values['G00']).sum()),regressed=int((mask&~values['G01']&values['G00']).sum()),paired_gain=interval(ratio(draws@sums,draws@counts)))
    contexts={}
    for name,code in [('continuing',2),('direction_change',3),('no_previous',1),('zero',4)]:
        mask=(raw['y']==8)&(direction==code);contexts[name]=dict(joint=effect(mask),parameter=effect(mask,True))
    categories={n:effect(raw['y']==i) for i,n in enumerate(rt.LABELS) if (raw['y']==i).any()}
    result=dict(reports={n:sha(REPORTS/(n+'.json')) for n in reports},source_sha256=sha(__file__),initial_states_reconstructed_equal=True,initial_scope='Reconstructed from pinned M01/seed26/source; original warm decoded parity asserted before each fit. Epoch-zero tensors were not separately serialized.',matching_saved_shuffle_rng_epochs=epochs,actual_fit_accounting={n:dict(selected_epoch=r['best_epoch'],completed_epochs=len(r['history']),optimizer_calls=r['optimizer_calls'],head_updates=r['head_updates'],seconds=r['seconds']) for n,r in reports.items()},overall=effect(np.ones(len(raw['y']),bool)),categories=categories,movement_contexts=contexts,gate_interpretation='G01 disjoint supports already supervise gate through primary NLL; extra0.05BCE raises gate coefficient1.00to1.05. Package effect includes support/optimization/weighting and separately loss-selected epochs; no isolated auxiliary claim.',scope='All14439original rows retained, including43unassessed strict shop failures. Parameter effects only for actual moves with required recorded destinations. Five-group pointwise uncertainty conditional on checkpoint selection, not3seed/untouched/generalization proof.',reserved_opened=0,new_fits=0)
    frozen(REPORTS/'G01-matched-comparison.json',result);(REPORTS/'G01-matched-analysis-source.txt').write_bytes(Path(__file__).read_bytes())
    with (REPORTS/'G01-matched-categories.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['category','support','G00_joint','G01_joint','fixed','regressed','paired_gain_low','paired_gain_high'])
        for n,r in categories.items():w.writerow([n,r['support'],r['G00_correct'],r['G01_correct'],r['fixed'],r['regressed'],r['paired_gain']['low'],r['paired_gain']['high']])
    print(result['overall']);print(contexts)

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_pair_analysis']);run()
