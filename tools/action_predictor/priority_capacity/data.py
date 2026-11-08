"""Consume approved TRAIN caches and freeze disjoint diagnostic cohorts."""
import json
import numpy as np
import torch
from .protocol import ROOT, OLD, LOCAL, OUT, SEED, freeze
from ..priority_fit_v3 import context_directory
from ..priority_head import flatten
from ..priority_residual_modes import AnchoredPriorityModes
from ..audit import immutable_json
from ..data import digest


def head():
    path=OLD/'v8/runs/P05/model.pt'
    report=json.loads((ROOT/'tools/action_predictor/experiments/v8/P05.json').read_text())
    assert digest(path)==report['checkpoint_sha256']
    saved=torch.load(path,weights_only=True,map_location='cpu')
    assert saved['architecture']=='frozen-M01-priority-anchored-modes-v1'
    vocab=json.loads((ROOT/'tools/action_predictor/experiments/v8/priority-residual-modes-vocabulary.json').read_text())
    model=AnchoredPriorityModes(torch.nn.Linear(128,2),vocab['absolute'],vocab['absolute_counts'],
                               vocab['residual'],vocab['residual_counts'])
    model.load_state_dict(saved['head_state'])
    model.requires_grad_(True)
    assert all(torch.equal(value,saved['head_state'][key]) for key,value in model.state_dict().items())
    return model,saved,path


def prepare():
    freeze()
    torch.set_num_threads(4)
    reports=ROOT/'tools/action_predictor/experiments'
    context=context_directory()
    ready=json.loads((reports/'v8/priority-context-ready-v3.json').read_text())
    recovered=json.loads((reports/'v8/priority-data-ready.json').read_text())
    p05,saved,checkpoint=head()
    paths=dict(context=context/'train.npy',normalizer=context/'extra-normalization.npz',
               priority=OLD/'v8/priority-train.npz',dataset=OLD/'v5/combined-train.npz',
               natural=OLD/'v9/frequency/natural-mask.npy',indices=OLD/'v11/R02-capacity/row-indices.npz',
               baseline=OLD/'v9/runs/G00/train-predictions.npz')
    r02=json.loads((reports/'v11/R02-capacity.json').read_text())
    g00=json.loads((reports/'v9/G00.json').read_text())
    expected=dict(context=ready['contexts']['train'],normalizer=ready['normalizer_sha256'],
                  priority=recovered['files']['train'],
                  dataset='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb',
                  natural='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd',
                  indices=r02['indices_sha256'],baseline=g00['train_predictions_sha256'])
    for key,path in paths.items():
        assert digest(path)==expected[key],key
    with np.load(paths['dataset']) as z:
        y,priority,groups=z['y'],z['priority'],z['group']
    natural=np.load(paths['natural'])
    with np.load(paths['indices']) as z:
        fit=z['fit'][y[z['fit']]==9]
        held=z['held_group'][y[z['held_group']]==9]
    assert len(fit)==len(held)==128 and natural[fit].all() and natural[held].all()
    fitgroups=np.unique(groups[fit])
    pool=np.flatnonzero(natural&(y==9)&np.isin(groups,fitgroups))
    pool=np.setdiff1d(pool,fit)
    seen=np.sort(np.random.default_rng(SEED).choice(pool,128,replace=False))
    indices={'fit':fit,'same_fit_groups':seen,'held_groups':held}
    assert not set(groups[fit])&set(groups[held])
    assert set(groups[seen])<=set(fitgroups)
    assert len(np.unique(np.concatenate(list(indices.values()))))==384
    with np.load(paths['normalizer']) as z:
        mean,std=z['mean'],z['std']
    np.testing.assert_array_equal(mean,saved['extra_mean'].numpy())
    np.testing.assert_array_equal(std,saved['extra_std'].numpy())
    with np.load(paths['priority']) as z:
        values,history=z['values'],z['history']
    assert values.dtype==history.dtype==np.int64
    contexts=np.load(paths['context'],mmap_mode='r')
    with np.load(paths['baseline']) as z:
        baseline_mode,baseline_nll=z['priority'],z['param_nll']
    directory=LOCAL/'PC00-cohorts'
    assert not directory.exists(),'Preserve attempted cohorts'
    directory.mkdir(parents=True)
    results={}
    for name,ix in indices.items():
        target=priority[ix].astype(np.int64)
        np.testing.assert_array_equal(target,priority[ix])
        v=values[ix]
        extra=(flatten(v,history[ix]).astype(np.float32)-mean)/std
        path=directory/f'{name}.npz'
        np.savez_compressed(path,context=np.array(contexts[ix]),features=extra,values=v,
            target=target,index=ix,group=groups[ix],baseline_mode=baseline_mode[ix].astype(np.int64),
            baseline_nll=baseline_nll[ix])
        results[name]=dict(rows=len(ix),groups=sorted(map(int,np.unique(groups[ix]))),
            unique_targets=len(np.unique(target)),target_min=int(target.min()),target_max=int(target.max()),
            last_argument_available=int((v[:,5]==1).sum()),
            absolute_vocabulary_contains_target=int(np.isin(target,p05.absolute.numpy()).sum()),
            sha256=digest(path))
        # Actual retained-head parity on this new consumption path, before fit.
        from .measurement import measure
        with torch.no_grad():
            raw=p05(torch.from_numpy(np.array(contexts[ix])),torch.from_numpy(extra))
            np.save(directory/f'{name}-initial-raw.npy',raw.numpy())
            prediction,metrics=measure(p05,raw,torch.from_numpy(v),torch.from_numpy(target))
        results[name]['initial_mode_mismatches']=int((prediction['integer'].numpy()!=baseline_mode[ix]).sum())
        results[name]['initial_NLL_max_difference']=float(np.abs(prediction['nll'].numpy()-baseline_nll[ix]).max())
        results[name]['initial_metrics']=metrics
        assert results[name]['initial_mode_mismatches']==0
        assert results[name]['initial_NLL_max_difference']<=2e-5
    bindings={str(path.relative_to(ROOT)):expected[key] for key,path in paths.items()}
    for path in [checkpoint,reports/'v8/priority-context-ready-v3.json',reports/'v8/priority-data-ready.json',
                 reports/'v8/priority-residual-modes-vocabulary.json',reports/'v11/R02-plan.json']:
        bindings[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(OUT/'PC00-data-ready.json',dict(cohorts=results,bindings=bindings,
        protocol_sha256=digest(OUT/'PC00-plan.json'),source_sha256=digest(__file__),
        exposure='Warm P05, M01 encoder, vocab and normalization previously saw TRAIN including controls. '
                 'Controls held out only from new optimization, not untouched full-policy generalization.',
        model_input_fields=['context','features','values'],metadata_only_fields=['index','group'],
        new_fits=0,reserved_opened=0))
    print('Prepared P05 capacity cohorts',results,flush=True)


def load():
    ready=json.loads((OUT/'PC00-data-ready.json').read_text())
    assert ready['protocol_sha256']==digest(OUT/'PC00-plan.json')
    result={}
    for name,info in ready['cohorts'].items():
        path=LOCAL/f'PC00-cohorts/{name}.npz'
        assert digest(path)==info['sha256']
        with np.load(path) as z:
            result[name]={key:torch.from_numpy(z[key]) for key in z.files}
    return result


if __name__ == '__main__':
    prepare()
