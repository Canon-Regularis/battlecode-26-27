"""Additive schema correction and explicit conditional context losses."""
import argparse
import copy
import json
import numpy as np
from .protocol import ROOT, BASE, LOCAL, OUT, ARMS
from .comparator_schema import conditional_reference
from ..learned_policy.analysis import read, paired_categories
from ..movement_experts.evaluate import masks
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    original_path = OUT / f'{identifier}-evaluation.json'
    result = copy.deepcopy(json.loads(original_path.read_text()))
    bindings = dict(result['bindings'])
    for split in ('train', 'validation'):
        dataset = BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz'
        with np.load(dataset) as z:
            raw = {key: z[key] for key in ('y', 'py', 'priority', 'group')}
        prediction = read(LOCAL / f'runs/{identifier}/{split}-predictions.npz')
        d = dict(raw=raw, direction=np.load(BASE.parent / f'v7/{split}-direction.npy'),
                 available=np.load(BASE.parent / f'v7/{split}-available.npy'),
                 near=np.load(BASE.parent / f'v7/{split}-near_obstacle.npy'))
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            sampling['natural'] = np.load(BASE.parent / 'v9/frequency/natural-mask.npy')
        for sample, selected in sampling.items():
            for key, context in masks(d).items():
                if key == 'all':
                    continue
                m = selected & context
                row = result['results'][split][sample]['movement_contexts'][key]
                row['conditional_nll'] = float(prediction['param_nll'][m].mean()) if m.any() else None
        if split == 'validation':
            path = BASE.parent / 'v13/runs/B00/validation-predictions.npz'
            reference = conditional_reference(raw, read(path))
            result['comparisons']['B00'] = dict(
                categories=paired_categories(raw, prediction, reference, sampling['all']),
                contexts={key: paired_categories(raw, prediction, reference, m)['overall']
                          for key, m in masks(d).items()
                          if key in ('move', 'blocked', 'continue', 'change', 'startup')})
            bindings[str(path.relative_to(ROOT))] = digest(path)
    result.update(original_evaluation_sha256=digest(original_path), bindings=bindings,
                  correction='B00 family_commands reconstruct true-family conditional coordinates '
                             'and priority. Chosen-command counts/NLL/correctly-typed comparisons '
                             'unchanged. All movement context tables now explicitly include true-family '
                             'conditional NLL, computed from retained param_nll. No fitted changes.',
                  sources={name: digest(__file__.replace('evaluate_v2.py', name))
                           for name in ('evaluate_v2.py', 'comparator_schema.py')})
    immutable_json(OUT / f'{identifier}-evaluation-v2.json', result)
    print('Corrected evaluation completed', identifier, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
