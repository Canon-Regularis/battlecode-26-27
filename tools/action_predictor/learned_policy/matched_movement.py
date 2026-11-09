"""Matched original/natural-row movement counts from retained predictions."""
import sys
import numpy as np
from .sequence_data import ROOT, BASE, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    results, bindings = {}, {}
    for split in ('train', 'validation'):
        path = BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz'
        with np.load(path) as z: y, py = z['y'], z['py']
        direction_path = BASE.parent / f'v7/{split}-direction.npy'
        direction = np.load(direction_path)
        natural = np.load(BASE.parent / 'v9/frequency/natural-mask.npy') if split == 'train' else np.ones(len(y), bool)
        summaries = {}
        for name, run in [('G00', BASE.parent / f'v9/runs/G00/{split}-predictions.npz'),
                          (identifier, WORK / f'runs/{identifier}/{split}-predictions.npz')]:
            with np.load(run) as z: coordinate, prediction = z['coordinate'], z['prediction']
            counts = {}
            for code, label in ((1, 'startup'), (2, 'continuation'), (3, 'change')):
                m = natural & (y == 8) & (direction == code)
                counts[label] = dict(rows=int(m.sum()), conditional_exact=int(((coordinate == py) & m).sum()),
                                     joint_exact=int(((prediction == y) & (coordinate == py) & m).sum()))
            summaries[name] = counts; bindings[str(run.relative_to(ROOT))] = digest(run)
        results[split] = summaries; bindings[str(direction_path.relative_to(ROOT))] = digest(direction_path)
    immutable_json(REPORT / f'{identifier}-matched-movement.json', dict(results=results, bindings=bindings,
        qualification='Same identity-verified natural TRAIN rows and all original DEV movement rows, identical conditional/joint definitions. TRAIN remains in-sample; learned-policy augmented filter traversal cadence differs from natural DEV and is not isolated group-shift evidence.',
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


if __name__ == '__main__': run(sys.argv[1])
