"""PD01: fixed-bin conditional integer confidence from saved P05 outputs.

No calibration fitting, score modification, model selection or DEV payloads.
"""
import json
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head, load
from .trajectory import ROOT, OUT


def run():
    torch.set_num_threads(4)
    assert not (OUT / 'PD01.json').exists()
    model, _, _ = head()
    model.requires_grad_(False)
    data = load()
    records = {}
    bindings = {str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))}
    old_path = ROOT / 'tools/action_predictor/experiments/v19/PC00.json'
    new_path = ROOT / 'tools/action_predictor/experiments/v21/PC01.json'
    old, new = json.loads(old_path.read_text()), json.loads(new_path.read_text())
    bindings.update({str(p.relative_to(ROOT)):digest(p) for p in (old_path, new_path)})
    for cohort, d in data.items():
        current_name = 'original_fit' if cohort == 'fit' else cohort
        for condition, version, step, name, receipt in (
            ('warm_P05','v19',0,cohort,old),
            ('small_PC00','v19',2000,cohort,old),
            ('broad_PC01','v21',2000,current_name,new)):
            directory = ROOT / f'.cambc/action-predictor/{version}/runs/' / ('PC00' if version == 'v19' else 'PC01')
            raw_path = directory / f'{name}-step-{step:04d}-raw.npy'
            prediction_path = directory / f'{name}-step-{step:04d}-predictions.npz'
            for p in (raw_path, prediction_path):
                expected = receipt['bindings'][str(p.relative_to(ROOT))]
                assert digest(p) == expected, p
                bindings[str(p.relative_to(ROOT))] = expected
            records[(cohort,condition)] = (raw_path,prediction_path)
    immutable_json(OUT / 'PD01-plan.json',dict(
        bindings=bindings,
        purpose='Distinguish higher confidence in wrong integer commands from lower recorded-target '
                'probability without sharper winning commands. Posthoc diagnostic, not a causal '
                'explanation of fitting/transfer or a calibration remedy.',
        bins='Fixed 10 equal-width probability bins [0,.1),...,[.9,1], empty-bin accuracy null.',
        metrics='Exact conditional integer-mode confidence; mode confidence on correct/error rows; '
                'fixed-bin ECE; binary correctness Brier (not full integer-distribution Brier); '
                'mean recorded-target probability and target rank from retained prediction archives.',
        comparisons='Warm P05, fixed PC00 final, fixed PC01 final on identical 128-row cohorts. '
                    'Original fit in-sample in both; controls excluded only from new optimization, '
                    'previously seen by warm head and frozen encoder.',
        scoring='Original normalized P05 probability arithmetic. No neural recomputation; '
                'reuse saved raw neural outputs. No fitting, threshold selection or score changes.',
        constraints='TRAINonly; no DEV payload, reserved access, matches, downloads or bot/runtime work.',
        new_fits=0,reserved_opened=0))
    results = {}
    for (cohort,condition),(raw_path,prediction_path) in records.items():
        d = data[cohort]
        raw = torch.from_numpy(np.load(raw_path))
        with torch.inference_mode():
            candidates, masses = model.candidate_log_masses(raw,d['values'])
            maximum, at = masses.max(-1)
            mode = candidates.gather(1,at[:,None])[:,0]
            target_logp = model.log_mass(raw,d['target'],d['values'])
        confidence = maximum.exp().numpy()
        target_probability = target_logp.exp().numpy()
        with np.load(prediction_path) as z:
            np.testing.assert_array_equal(mode.numpy(),z['integer'])
            np.testing.assert_allclose(-target_logp.numpy(),z['nll'],rtol=1e-12,atol=1e-12)
            rank = z['rank']
        correct = mode.numpy() == d['target'].numpy()
        assert np.isfinite(confidence).all() and ((confidence >= 0) & (confidence <= 1+1e-12)).all()
        bin_index = np.minimum((confidence*10).astype(int),9)
        bins=[]
        for index in range(10):
            mask = bin_index == index
            n = int(mask.sum())
            bins.append(dict(lower=index/10,upper=(index+1)/10,rows=n,
                mean_confidence=float(confidence[mask].mean()) if n else None,
                accuracy=float(correct[mask].mean()) if n else None))
        ece = sum(row['rows']/len(correct)*abs(row['mean_confidence']-row['accuracy'])
                  for row in bins if row['rows'])
        results.setdefault(cohort,{})[condition] = dict(rows=len(correct),exact=int(correct.sum()),
            mean_mode_confidence=float(confidence.mean()),
            mean_mode_confidence_correct=float(confidence[correct].mean()) if correct.any() else None,
            mean_mode_confidence_wrong=float(confidence[~correct].mean()) if (~correct).any() else None,
            binary_correctness_Brier=float(np.square(confidence-correct).mean()),
            fixed_bin_ECE=ece,bins=bins,
            mean_recorded_target_probability=float(target_probability.mean()),
            mean_bounded_candidate_rank=float(rank.mean()))
    immutable_json(OUT / 'PD01.json',dict(results=results,
        protocol_sha256=digest(OUT/'PD01-plan.json'),bindings=bindings,
        neural_forward_recomputed=False,conditional_family_supplied=True,
        calibration_fit=False,policy_replaced=False,new_fits=0,reserved_opened=0))
    print(json.dumps({name:{c:{k:v for k,v in row.items() if k!='bins'} for c,row in conditions.items()}
                      for name,conditions in results.items()},indent=2))


if __name__ == '__main__':
    run()
