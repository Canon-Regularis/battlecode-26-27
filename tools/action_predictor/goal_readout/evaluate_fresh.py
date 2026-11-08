"""Corrected evaluator for new fits, without emitting the legacy schema bug."""
import argparse
import json
import numpy as np
from .protocol import ROOT, BASE, LOCAL, OUT, V16, ARMS
from .comparator_schema import conditional_reference
from .evaluate import score
from ..learned_policy.analysis import read, paired_categories, readiness_flags
from ..movement_experts.evaluate import summary, support, masks
from ..audit import immutable_json
from ..data import digest


def calculate(identifier):
    info = json.loads((OUT / f'{identifier}.json').read_text())
    results, comparisons, bindings = {}, {}, {}
    for split in ('train', 'validation'):
        dataset = BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz'
        raw = read(dataset)
        directory = LOCAL / f'runs/{identifier}'
        prediction_path = directory / f'{split}-predictions.npz'
        assert digest(prediction_path) == info['predictions_sha256'][split]
        prediction = read(prediction_path)
        diagnostic_path = directory / f'{split}-diagnostics.npz'
        diagnostic = read(diagnostic_path)
        paths = {key: BASE.parent / f'v7/{split}-{name}.npy'
                 for key, name in [('direction', 'direction'), ('available', 'available'), ('near', 'near_obstacle')]}
        d = dict(raw=raw, **{key: np.load(path) for key, path in paths.items()})
        position_path = LOCAL / f'upstream/{split}/position_known.npy'
        positions = np.load(position_path, mmap_mode='r')
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            natural_path = BASE.parent / 'v9/frequency/natural-mask.npy'
            sampling['natural'] = np.load(natural_path)
            bindings[str(natural_path.relative_to(ROOT))] = digest(natural_path)
        results[split] = {}
        for sample, selected in sampling.items():
            value = score(d, prediction, diagnostic, selected)
            for key, context in masks(d).items():
                if key == 'all':
                    continue
                m = selected & context
                value['movement_contexts'][key]['conditional_nll'] = float(prediction['param_nll'][m].mean()) if m.any() else None
            value['position_contexts'] = {key: summary(d, prediction, selected & (positions == known))
                                         for key, known in [('known', True), ('unknown', False)]}
            results[split][sample] = value
        results[split]['partial_readiness'] = readiness_flags(raw, prediction)
        results[split]['movement_support'] = support(d, prediction)
        if split == 'validation':
            references = dict(L02=V16 / 'runs/L02/validation-predictions.npz',
                              L01=V16 / 'runs/L01/validation-predictions.npz',
                              G00=BASE.parent / 'v9/runs/G00/validation-predictions.npz',
                              B00=BASE.parent / 'v13/runs/B00/validation-predictions.npz')
            if identifier == 'U01':
                references['U00'] = LOCAL / 'runs/U00/validation-predictions.npz'
            for name, path in references.items():
                reference = conditional_reference(raw, read(path))
                comparisons[name] = dict(categories=paired_categories(raw, prediction, reference, sampling['all']),
                    contexts={key: paired_categories(raw, prediction, reference, m)['overall']
                              for key, m in masks(d).items()
                              if key in ('move', 'blocked', 'continue', 'change', 'startup')})
                bindings[str(path.relative_to(ROOT))] = digest(path)
        for path in [dataset, prediction_path, diagnostic_path, position_path] + list(paths.values()):
            bindings[str(path.relative_to(ROOT))] = digest(path)
    return dict(results=results, comparisons=comparisons, bindings=bindings,
        fit_sha256=digest(OUT / f'{identifier}.json'),
        sources={name: digest(__file__.replace('evaluate_fresh.py', name))
                 for name in ('evaluate_fresh.py', 'evaluate.py', 'comparator_schema.py')},
        qualification='Corrected evaluation schema; same point/paired/context definitions as U00-v2. '
                      'No legacy malformed B00 conditional comparison is generated for the new fit. '
                      'Natural TRAIN is in-sample/common augmented-filter cadence. Five reused DEV '
                      'groups, selected checkpoints and one seed. Oracle component bounds, absent '
                      'shop arguments, sparse support, identity and legality/calibration limits remain.',
        new_fits=0, reserved_opened=0)


def run(identifier, validate=False):
    result = calculate(identifier)
    path = OUT / f'{identifier}-evaluation-v2.json'
    if validate:
        existing = json.loads(path.read_text())
        assert result['results'] == existing['results']
        assert result['comparisons'] == existing['comparisons']
        immutable_json(OUT / f'{identifier}-fresh-evaluator-parity.json', dict(
            results_and_comparisons_exact=True, existing_evaluation_sha256=digest(path),
            source_sha256=digest(__file__), new_fits=0, reserved_opened=0))
    else:
        immutable_json(path, result)
    print('Corrected fresh evaluation', identifier, 'validate', validate, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    run(args.identifier, args.validate)
