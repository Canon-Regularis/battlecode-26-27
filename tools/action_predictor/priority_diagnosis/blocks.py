"""PD02: fixed PC01 parameter-block interventions, no optimization/selection."""
import itertools
import json
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head, load
from ..priority_capacity.measurement import measure
from .trajectory import ROOT, OUT


def run():
    torch.set_num_threads(4)
    assert not (OUT / 'PD02.json').exists()
    directory = ROOT / '.cambc/action-predictor/v21/runs/PC01'
    paths = {step:directory/f'step-{step:04d}.pt' for step in (0,2000)}
    receipt_path = ROOT/'tools/action_predictor/experiments/v21/PC01.json'
    receipt = json.loads(receipt_path.read_text())
    bindings = {str(receipt_path.relative_to(ROOT)):digest(receipt_path),
                str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))}
    for p in paths.values():
        expected = receipt['bindings'][str(p.relative_to(ROOT))]
        assert digest(p) == expected
        bindings[str(p.relative_to(ROOT))] = expected
    state = {step:torch.load(p,weights_only=True,map_location='cpu')['head_state']
             for step,p in paths.items()}
    assert torch.equal(state[0]['absolute'],state[2000]['absolute'])
    assert torch.equal(state[0]['residual'],state[2000]['residual'])
    data = load()
    ready_path = ROOT/'tools/action_predictor/experiments/v19/PC00-data-ready.json'
    ready = json.loads(ready_path.read_text())
    bindings[str(ready_path.relative_to(ROOT))] = digest(ready_path)
    for name in data:
        p = ROOT/f'.cambc/action-predictor/v19/PC00-cohorts/{name}.npz'
        bindings[str(p.relative_to(ROOT))] = ready['cohorts'][name]['sha256']
    for name in ('priority_residual_modes.py','priority_modes.py','priority_capacity/data.py',
                 'priority_capacity/measurement.py'):
        p=ROOT/'tools/action_predictor'/name
        bindings[str(p.relative_to(ROOT))] = digest(p)
    immutable_json(OUT/'PD02-plan.json',dict(bindings=bindings,
        purpose='Locate fixed-weight dependence in the learned PC01-minus-warm readout changes. '
                'This is not a training-process causal decomposition or a replacement search.',
        factors=['context linear-weight columns0:128','explicit priority linear-weight columns128:167',
                 'all output biases, including fallback location/scale'],
        contrasts='ALL8 binary combinations of warm versus PC01final blocks, no branch selection. '
                  'Same unchanged raw inputs/anchors/probability arithmetic. '
                  'All mode, fallback-gate and fallback-parameter rows participate.',
        cohorts='Original128fit plus same two128controls; all previously seen by warm encoder/head. '
                'Fit rows in-sample, controls excluded only from PC01 optimization.',
        metrics='Conditional integer exactness, normalized NLL, bounded candidate rank, '
                'marginalized explanation shares; preserve both endpoint parity.',
        limitations='Explicit-input weight intervention does not remove indirect priority information '
                    'from context or analytic exact anchor. Block effects can interact through probability '
                    'normalization and duplicate point aggregation. No Fish-intent attribution.',
        new_fits=0,reserved_opened=0))
    local = ROOT/'.cambc/action-predictor/v20/PD02'
    local.mkdir(parents=True,exist_ok=False)
    model,_,_=head()
    model.requires_grad_(False)
    results={}
    for factors in itertools.product((0,1),repeat=3):
        name=''.join(map(str,factors))
        mixed={key:value.clone() for key,value in state[0].items()}
        if factors[0]: mixed['linear.weight'][:,:128]=state[2000]['linear.weight'][:,:128]
        if factors[1]: mixed['linear.weight'][:,128:]=state[2000]['linear.weight'][:,128:]
        if factors[2]: mixed['linear.bias']=state[2000]['linear.bias'].clone()
        model.load_state_dict(mixed)
        results[name]={}
        for cohort,d in data.items():
            with torch.inference_mode():
                raw=model(d['context'],d['features'])
                prediction,metrics=measure(model,raw,d['values'],d['target'])
            path=local/f'{cohort}-blocks-{name}.npz'
            np.savez_compressed(path,**{key:value.numpy() for key,value in prediction.items()})
            bindings[str(path.relative_to(ROOT))]=digest(path)
            results[name][cohort]=metrics
            if name in ('000','111'):
                current='original_fit' if cohort=='fit' else cohort
                step=0 if name=='000' else 2000
                original=directory/f'{current}-step-{step:04d}-predictions.npz'
                expected=receipt['bindings'][str(original.relative_to(ROOT))]
                assert digest(original)==expected
                bindings[str(original.relative_to(ROOT))]=expected
                with np.load(original) as z:
                    for key,value in prediction.items():
                        np.testing.assert_array_equal(value.numpy(),z[key])
    immutable_json(OUT/'PD02.json',dict(results=results,bindings=bindings,
        protocol_sha256=digest(OUT/'PD02-plan.json'),endpoint_prediction_arrays_exact=True,
        branch_selected=False,neural_upstream_recomputed=False,new_fits=0,reserved_opened=0))
    print(json.dumps({name:{c:{k:v for k,v in m.items() if k in ('exact','mean_NLL')}
                            for c,m in cohorts.items()} for name,cohorts in results.items()},indent=2))


if __name__=='__main__':
    run()
