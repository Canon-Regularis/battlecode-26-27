"""Reproducible saved-output fitting/transfer and category-loss diagnosis."""
import argparse
import json
import numpy as np
from .protocol import ROOT, BASE, LOCAL, OUT, V16, V16_REPORT, ARMS
from ..learned_policy.analysis import read, paired_categories
from ..observation_metrics import correctness
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    info = json.loads((OUT / f'{identifier}.json').read_text())
    oldinfo = json.loads((V16_REPORT / 'L02.json').read_text())
    evaluation_path = OUT / f'{identifier}-evaluation-v2.json'
    evaluation = json.loads(evaluation_path.read_text())
    expected_inputs = json.loads((V16_REPORT / 'policy-input-bindings.json').read_text())['files']
    results, bindings, losses = {}, {}, {}
    for split in ('train', 'validation'):
        dataset = BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz'
        assert digest(dataset) == expected_inputs[str(dataset.relative_to(ROOT))]
        with np.load(dataset) as z:
            raw = {key: z[key] for key in ('y', 'py', 'priority', 'group')}
        direction_path = BASE.parent / f'v7/{split}-direction.npy'
        assert digest(direction_path) == expected_inputs[str(direction_path.relative_to(ROOT))]
        direction = np.load(direction_path)
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            natural = BASE.parent / 'v9/frequency/natural-mask.npy'
            assert digest(natural) == '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
            sampling['natural'] = np.load(natural)
            bindings[str(natural.relative_to(ROOT))] = digest(natural)
        paths = {'L02': V16 / f'runs/L02/{split}-predictions.npz',
                 identifier: LOCAL / f'runs/{identifier}/{split}-predictions.npz'}
        expected_predictions = {'L02': oldinfo['predictions_sha256'][split],
                                identifier: info['predictions_sha256'][split]}
        if identifier == 'U01':
            controlinfo = json.loads((OUT / 'U00.json').read_text())
            paths['U00'] = LOCAL / f'runs/U00/{split}-predictions.npz'
            expected_predictions['U00'] = controlinfo['predictions_sha256'][split]
        predictions = {}
        for name, path in paths.items():
            assert digest(path) == expected_predictions[name]
            predictions[name] = read(path)
            bindings[str(path.relative_to(ROOT))] = digest(path)
        results[split] = {}
        for sample, selected in sampling.items():
            results[split][sample] = {}
            for name, prediction in predictions.items():
                parameter, joint = correctness(raw, prediction)
                value = dict(rows=int(selected.sum()), strict_correct=int(joint[selected].sum()),
                             NLL=float(prediction['nll'][selected].mean()))
                for code, label in ((2, 'continue'), (3, 'change')):
                    m = selected & (raw['y'] == 8) & (direction == code)
                    value[label] = dict(rows=int(m.sum()), conditional=int(parameter[m].sum()),
                        joint=int(joint[m].sum()), conditional_NLL=float(prediction['param_nll'][m].mean()) if m.any() else None,
                        joint_NLL=float(prediction['nll'][m].mean()) if m.any() else None)
                results[split][sample][name] = value
        if split == 'validation':
            initial_path = LOCAL / f'initial-v2/{identifier}/validation-predictions.npz'
            initial = read(initial_path)
            expected_initial = json.loads((OUT / 'preflight-v2.json').read_text())['results'][identifier]['predictions_sha256']
            assert digest(initial_path) == expected_initial
            initial_paired = paired_categories(raw, predictions[identifier], initial, sampling['all'])
            bindings[str(initial_path.relative_to(ROOT))] = digest(initial_path)
            for name, baseline in predictions.items():
                if name == identifier:
                    continue
                prediction = predictions[identifier]
                total = float((prediction['nll'] - baseline['nll']).sum())
                rows = []
                for code in range(15):
                    m = raw['y'] == code
                    joint_delta = float((prediction['nll'][m] - baseline['nll'][m]).sum())
                    type_delta = float((prediction['type_nll'][m] - baseline['type_nll'][m]).sum())
                    parameter_delta = float((prediction['param_nll'][m] - baseline['param_nll'][m]).sum())
                    rows.append(dict(code=code, support=int(m.sum()), joint_NLL_sum_difference=joint_delta,
                        type_NLL_sum_difference=type_delta, parameter_NLL_sum_difference=parameter_delta if code != 11 else None,
                        fraction_of_net_NLL_difference=joint_delta / total if total != 0 else None))
                losses[name] = dict(total_NLL_sum_difference=total, categories=rows,
                    meaning='Arithmetic contributions to net observed loss; may exceed100% when '
                            'other categories offset them. Not causal attribution of optimization. '
                            'Shop purchase likelihood is absent. Priority parameter differences can '
                            'contain roundoff despite an unchanged fixed integer model.')
        for path in (dataset, direction_path):
            bindings[str(path.relative_to(ROOT))] = digest(path)
    legacy_agreement = None
    legacy_path = OUT / 'U00-diagnosis.json'
    if identifier == 'U00':
        legacy = json.loads(legacy_path.read_text())
        assert results == legacy['results']
        assert initial_paired == legacy['trained_minus_initial_mean']
        legacy_agreement = True
        bindings[str(legacy_path.relative_to(ROOT))] = digest(legacy_path)
    immutable_json(OUT / f'{identifier}-diagnosis-v2.json', dict(results=results,
        trained_minus_initial_readout=initial_paired,
        DEV_movement_diagnostics=evaluation['results']['validation']['all']['movement_contexts']['move'],
        loss_difference_by_category=losses, legacy_U00_metrics_exact=legacy_agreement,
        evaluation_sha256=digest(evaluation_path), bindings=bindings, source_sha256=digest(__file__),
        reproduction='.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.goal_readout.diagnose ' + identifier,
        interpretation='Saved-output diagnostic only, no inference/refit or retrospective epoch0 selection. '
                       'Natural TRAIN remains in-sample under common augmented filtering. Per-direction '
                       'scores share definitions but do not isolate group shift. Original targets unchanged.',
        new_fits=0, reserved_opened=0))
    print('Reproduced diagnosis', identifier, 'legacy exact', legacy_agreement, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
