"""Posthoc saved-output decomposition, not a predictor or fitted experiment."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
from tools.action_predictor.audit import immutable_json
from tools.action_predictor.data import digest


def read(path):
    with np.load(path) as archive:
        return {key: archive[key] for key in archive.files}


def states(raw, prediction):
    parameter = prediction['coordinate'] == raw['py']
    typed = prediction['prediction'] == raw['y']
    return 2 * typed.astype(np.uint8) + parameter.astype(np.uint8)


def run():
    local = ROOT / '.cambc/action-predictor'
    reports = ROOT / 'tools/action_predictor/experiments'
    infos = {name: json.loads((reports / folder / f'{name}.json').read_text())
             for name, folder in [('L02', 'v16'), ('U00', 'v18')]}
    results, bindings = {}, {}
    for split in ('train', 'validation'):
        dataset = local / ('v5/combined-train.npz' if split == 'train' else 'v4/validation.npz')
        with np.load(dataset) as archive:
            raw = {key: archive[key] for key in ('y', 'py')}
        prediction = {}
        for name, folder in [('L02', 'v16'), ('U00', 'v18')]:
            path = local / folder / f'runs/{name}/{split}-predictions.npz'
            assert digest(path) == infos[name]['predictions_sha256'][split]
            prediction[name] = read(path)
            bindings[str(path.relative_to(ROOT))] = digest(path)
        direction_path = local / f'v7/{split}-direction.npy'
        direction = np.load(direction_path)
        diagnostic_path = local / f'v18/runs/U00/{split}-diagnostics.npz'
        heads = read(diagnostic_path)['component_modes']
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            natural = local / 'v9/frequency/natural-mask.npy'
            assert digest(natural) == '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
            sampling['natural'] = np.load(natural)
            bindings[str(natural.relative_to(ROOT))] = digest(natural)
        old, new = states(raw, prediction['L02']), states(raw, prediction['U00'])
        contexts = {'move': raw['y'] == 8, 'blocked': raw['y'] == 3}
        contexts.update({label: (raw['y'] == 8) & (direction == code)
                         for code, label in [(1, 'startup'), (2, 'continue'), (3, 'change')]})
        results[split] = {}
        for sample, selected in sampling.items():
            results[split][sample] = {}
            for label, context in contexts.items():
                m = selected & context
                matrix = np.bincount(4 * old[m] + new[m], minlength=16).reshape(4, 4)
                support = int(m.sum())
                assert matrix.sum() == support
                available = (heads == raw['py'][:, None]).any(-1)
                common_wrong = (heads == heads[:, :1]).all(-1) & (heads[:, 0] != raw['py'])
                correctly_typed_destination_error = m & (new == 2)
                assert not (m & common_wrong & ((new == 1) | (new == 3))).any()
                results[split][sample][label] = dict(rows=support,
                    old_to_new_state_matrix=matrix.tolist(),
                    rescues=int(matrix[:3, 3].sum()), regressions=int(matrix[3, :3].sum()),
                    before=dict(wrong_type=int(np.isin(old[m], [0, 1]).sum()),
                                correctly_typed_wrong_destination=int((old[m] == 2).sum()),
                                correct_destination_wrong_type=int((old[m] == 1).sum())),
                    after=dict(wrong_type=int(np.isin(new[m], [0, 1]).sum()),
                               correctly_typed_wrong_destination=int((new[m] == 2).sum()),
                               correct_destination_wrong_type=int((new[m] == 1).sum())),
                    correctly_typed_destination_errors_with_correct_head_mode=int((correctly_typed_destination_error & available).sum()),
                    correctly_typed_destination_errors_without_correct_head_mode=int((correctly_typed_destination_error & ~available).sum()),
                    correctly_typed_destination_errors_common_wrong=int((correctly_typed_destination_error & common_wrong).sum()))
        for path in (dataset, direction_path, diagnostic_path):
            bindings[str(path.relative_to(ROOT))] = digest(path)
    immutable_json(local / 'v18/U00-movement-transitions.json', dict(results=results,
        state_order=['wrong_type_wrong_conditional_destination', 'wrong_type_correct_conditional_destination',
                     'correct_type_wrong_destination', 'correct_complete_command'],
        meaning='Movement/blocked diagnostic only. When type is wrong the archived coordinate is '
                'the recorded-family conditional diagnostic, NOT an emitted movement command. '
                'Matrices describe overlapping changes; no single-cause or hidden-intent attribution. '
                'Head-mode availability is an oracle diagnostic, not achieved routing or full coordinate support. '
                'No new policy, inference, fit, variant selection or changed denominator.',
        bindings=bindings, source_sha256=digest(__file__), new_fits=0, reserved_opened=0))
    print(json.dumps(results['validation']['all'], indent=2))


if __name__ == '__main__':
    run()
