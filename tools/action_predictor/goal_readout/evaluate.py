"""Complete-command and matched parameter/context evidence from saved fits."""
import argparse
import json
import numpy as np
from .protocol import ROOT, BASE, LOCAL, OUT, V16, ARMS
from ..learned_policy.analysis import read, paired_categories, readiness_flags
from ..movement_experts.evaluate import summary, support, masks
from ..observation_metrics import correctness
from ..audit import immutable_json
from ..data import digest


def score(d, prediction, diagnostics, mask):
    raw = d['raw']
    result = summary(d, prediction, mask)
    for code, row in enumerate(result['per_category']):
        m = mask & (raw['y'] == code)
        row['observed_nll'] = float(prediction['nll'][m].mean()) if m.any() else None
        row['type_nll'] = float(prediction['type_nll'][m].mean()) if m.any() else None
        row['parameter_nll'] = float(prediction['param_nll'][m].mean()) if m.any() and code != 11 else None
    parameter, joint = correctness(raw, prediction)
    movement = {}
    for name, context in masks(d).items():
        if name == 'all':
            continue
        m = mask & context
        n = int(m.sum())
        modes = diagnostics['component_modes'][m]
        gold = raw['py'][m]
        ranks = diagnostics['rank'][m]
        available = ranks > 0
        common_wrong = (modes == modes[:, :1]).all(-1) & (modes[:, 0] != gold)
        movement[name] = dict(rows=n,
            conditional_correct=int((parameter & m).sum()), joint_correct=int((joint & m).sum()),
            target_rank_coverage=int(available.sum()),
            mean_target_rank=float(ranks[available].mean()) if available.any() else None,
            target_probability=float(np.exp(-prediction['param_nll'][m]).mean()) if n else None,
            component_mode_union=int((modes == gold[:, None]).any(-1).sum()),
            common_wrong_components=int(common_wrong.sum()),
            frozen_component_reweighting_upper_bound=n - int(common_wrong.sum()),
            observed_nll=float(prediction['nll'][m].mean()) if n else None)
    result['movement_contexts'] = movement
    return result


def run(identifier):
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
        diagnostics = read(diagnostic_path)
        d = dict(raw=raw, direction=np.load(BASE.parent / f'v7/{split}-direction.npy'),
                 available=np.load(BASE.parent / f'v7/{split}-available.npy'),
                 near=np.load(BASE.parent / f'v7/{split}-near_obstacle.npy'))
        positions = np.load(LOCAL / f'upstream/{split}/position_known.npy', mmap_mode='r')
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            sampling['natural'] = np.load(BASE.parent / 'v9/frequency/natural-mask.npy')
        results[split] = {name: score(d, prediction, diagnostics, mask) for name, mask in sampling.items()}
        for name, mask in sampling.items():
            results[split][name]['position_contexts'] = {
                key: summary(d, prediction, mask & (positions == known))
                for key, known in [('known', True), ('unknown', False)]}
        results[split]['partial_readiness'] = readiness_flags(raw, prediction)
        results[split]['movement_support'] = support(d, prediction)
        if split == 'validation':
            paths = dict(L02=V16 / 'runs/L02/validation-predictions.npz',
                         L01=V16 / 'runs/L01/validation-predictions.npz',
                         G00=BASE.parent / 'v9/runs/G00/validation-predictions.npz',
                         B00=BASE.parent / 'v13/runs/B00/validation-predictions.npz')
            if identifier == 'U01':
                paths['U00'] = LOCAL / 'runs/U00/validation-predictions.npz'
            for name, path in paths.items():
                reference = read(path)
                comparisons[name] = dict(categories=paired_categories(raw, prediction, reference, sampling['all']),
                    contexts={key: paired_categories(raw, prediction, reference, mask)['overall']
                              for key, mask in masks(d).items() if key in ('move', 'blocked', 'continue', 'change', 'startup')})
                bindings[str(path.relative_to(ROOT))] = digest(path)
        for p in (dataset, prediction_path, diagnostic_path):
            bindings[str(p.relative_to(ROOT))] = digest(p)
    immutable_json(OUT / f'{identifier}-evaluation.json', dict(results=results, comparisons=comparisons,
        bindings=bindings, fit_sha256=digest(OUT / f'{identifier}.json'), source_sha256=digest(__file__),
        qualification='One-seed frozen-upstream readout comparison. Natural TRAIN membership retains '
                      'common augmented-traversal baseline filtering, not natural cadence or held-out folds. '
                      'Five repeatedly reused DEV groups after checkpoint selection, not selection-adjusted '
                      'or untouched uncertainty. Component bounds hold distributions and upstream states '
                      'fixed, not architecture/data limits. Complete predictions use predicted action types. '
                      'All43DEV shops strict failures; argument likelihood absent. Sparse categories, '
                      'identity and full legality/calibration uncertified. No policy promotion.',
        new_fits=0, reserved_opened=0))
    print('Evaluation completed', identifier, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
