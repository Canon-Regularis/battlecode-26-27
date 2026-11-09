"""Bounded numerical repair check on retained Q01 contexts, never a fit."""
import argparse
import json
import subprocess

import torch

from .conditional_probability import conditional_log_probs
from .model import SPATIAL
from .pathway_protocol import LOCAL, OUT
from .pathway_reference import load_model
from ..audit import immutable_json
from ..data import digest


def freeze():
    sources = {name: digest(__file__.replace('conditional_assessment.py', name))
               for name in ('conditional_assessment.py', 'conditional_probability.py',
                            'test_conditional_probability.py')}
    inputs = {}
    for identifier in ('L01', 'L02'):
        ready = OUT / f'Q01-{identifier}-ready-v2.json'
        content = json.loads(ready.read_text())
        path = LOCAL / f'Q01-v2/{identifier}/normalization-worst-cases.pt'
        assert digest(path) == content['worst_cases_sha256']
        inputs[str(path)] = content['worst_cases_sha256']
        inputs[str(ready)] = digest(ready)
    plan = dict(
        purpose='Test an additive, algebraically equivalent conditional-probability helper. '
                'No integration into models/decoder, training, replacement or benchmark rescoring.',
        cohort='All saved worst-normalization Q01 batches for L01/L02, all spatial families. '
               'Selected numerical cohort, repeated contexts across scopes/branches and padding '
               'remain explicit. Not an independent performance sample.',
        assessment=dict(valid_probability_sum_error_limit=2e-6,
                        independent_float64_normalization_limit=1e-12,
                        observed_NLL_difference_reference_limit=2e-5,
                        semantic_modes='Report all disagreements; do not select a variant.'),
        unchanged='Selected model weights, saved contexts/priors, masks, existing decoder, '
                  'saved primary forecasts, original failed Q01 checks and all historical artifacts.',
        independent_reference='Normalize the frozen component outputs in float64 and sum their '
                              'conditional probabilities in probability space.',
        sources=sources, inputs=inputs, new_fits=0, reserved_opened=0)
    immutable_json(OUT / 'conditional-probability-plan.json', plan)
    return plan


@torch.no_grad()
def run():
    plan = freeze()
    torch.set_num_threads(2)
    output = {}
    for identifier in ('L01', 'L02'):
        model, _, checkpoint = load_model(identifier)
        path = LOCAL / f'Q01-v2/{identifier}/normalization-worst-cases.pt'
        cases = torch.load(path, weights_only=False)
        records = []
        for branch, scopes in cases.items():
            for scope, case in scopes.items():
                step, geo = case['step'], case['geometry']
                valid = torch.as_tensor(case['valid'])
                n = len(valid)
                typ = model.types(step)
                type_mass = torch.logsumexp(step['logprior'][:, :, None] + typ, 1)
                scores = type_mass.clone()
                coordinates = torch.full((n, 15), -1, dtype=torch.long)
                old_error = new_error = oracle_error = 0.
                oracle_lp_difference = family_mass_difference = 0.
                conditional_modes_changed = oracle_modes_changed = 0
                checked_distributions = 0
                family_records = {}
                # No recorded action is used in constructing these probabilities/modes.
                for family in SPATIAL:
                    codes = torch.full((n,), family, dtype=torch.long)
                    heads = model.spatial_log_probs(step, **geo, family=codes)
                    stable, mass = conditional_log_probs(step['logprior'], typ[:, :, family], heads)
                    joint = torch.logsumexp(step['logprior'][:, :, None] + typ[:, :, family, None] + heads, 1)
                    old = joint - type_mass[:, family, None]
                    # Independent normalized probability-space mixture in double.
                    prior64 = step['logprior'].double().softmax(-1)
                    type64 = typ.double().softmax(-1)[:, :, family]
                    weights = prior64 * type64
                    weights = weights / weights.sum(-1, keepdim=True)
                    expected = (weights[:, :, None] * heads.double().softmax(-1)).sum(1)
                    old_error = max(old_error, float((old[valid].double().exp().sum(-1) - 1).abs().max()))
                    new_error = max(new_error, float((stable[valid].double().exp().sum(-1) - 1).abs().max()))
                    oracle_error = max(oracle_error, float((expected[valid].sum(-1) - 1).abs().max()))
                    # Compare probability rather than log-probability for zero-support buckets.
                    oracle_lp_difference = max(oracle_lp_difference, float((stable[valid].double().exp() - expected[valid]).abs().max()))
                    family_mass_difference = max(family_mass_difference, float((mass[valid] - type_mass[valid, family]).abs().max()))
                    conditional_modes_changed += int((old.argmax(-1)[valid] != stable.argmax(-1)[valid]).sum())
                    oracle_modes_changed += int((expected.argmax(-1)[valid] != stable.argmax(-1)[valid]).sum())
                    checked_distributions += int(valid.sum())
                    scores[:, family], coordinates[:, family] = (type_mass[:, family, None] + stable).max(-1)
                    family_records[family] = stable
                scores[:, 9] += case['priority_mode_logp']
                prediction = scores.argmax(-1)
                row = torch.arange(n)
                coordinate = coordinates[row, prediction]
                primary = case['primary']
                spatial = torch.zeros(n, dtype=torch.bool)
                for family in SPATIAL:
                    spatial |= prediction == family
                same = (prediction == primary['prediction']) & (~spatial | (coordinate == primary['coordinate']))
                same &= (prediction != 9) | (case['priority_mode'] == primary['priority'])
                # Recorded answers enter only after all numerical predictions above.
                y, py = case['target']['y'], case['target']['py']
                logmass = type_mass[row, y].clone()
                for family, conditional in family_records.items():
                    m = y == family
                    logmass[m] += conditional[m][torch.arange(int(m.sum())), py[m]]
                logmass[y == 9] -= case['target']['priority_parameter_nll'][y == 9]
                nll_difference = float((-logmass[valid] - case['primary_nll'][valid]).abs().max())
                records.append(dict(branch=branch, scope=scope, valid_rows=int(valid.sum()),
                    padded_rows=int((~valid).sum()), checked_conditional_distributions=checked_distributions,
                    old_normalization_error=old_error, stable_normalization_error=new_error,
                    independent_normalization_error=oracle_error,
                    stable_vs_independent_probability_max_difference=oracle_lp_difference,
                    family_mass_max_difference=family_mass_difference,
                    old_vs_stable_conditional_mode_changes=conditional_modes_changed,
                    stable_vs_independent_conditional_mode_changes=oracle_modes_changed,
                    primary_vs_reconstructed_semantic_MAP_changes=int((valid & ~same).sum()),
                    primary_vs_reconstructed_NLL_max_difference=nll_difference))
        output[identifier] = dict(records=records, checkpoint_sha256=digest(checkpoint),
            cases_sha256=digest(path), batches=len(records),
            valid_case_rows=sum(r['valid_rows'] for r in records),
            checked_conditional_distributions=sum(r['checked_conditional_distributions'] for r in records),
            old_normalization_max=max(r['old_normalization_error'] for r in records),
            stable_normalization_max=max(r['stable_normalization_error'] for r in records),
            independent_normalization_max=max(r['independent_normalization_error'] for r in records),
            conditional_mode_changes=sum(r['old_vs_stable_conditional_mode_changes'] for r in records),
            independent_conditional_mode_changes=sum(r['stable_vs_independent_conditional_mode_changes'] for r in records),
            semantic_MAP_changes=sum(r['primary_vs_reconstructed_semantic_MAP_changes'] for r in records),
            NLL_max_difference=max(r['primary_vs_reconstructed_NLL_max_difference'] for r in records))
        print(identifier, {k: v for k, v in output[identifier].items() if k != 'records'}, flush=True)
    immutable_json(OUT / 'conditional-probability-assessment.json', dict(
        execution_commit=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip(),
        plan_sha256=digest(OUT / 'conditional-probability-plan.json'), results=output,
        interpretation='Numerical-method assessment on selected frozen contexts only. No policy '
                       'quality improvement, full raw-serving verification, retraction of the '
                       'original Q01 failure or replacement checkpoint is claimed.',
        new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    if parser.parse_args().freeze:
        freeze()
    else:
        run()
