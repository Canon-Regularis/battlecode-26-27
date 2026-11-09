"""Actual initialization, frozen tensors, ordering and optimizer contracts."""
import json
import numpy as np
import torch
from .protocol import LOCAL, OUT
from ..audit import immutable_json
from ..data import digest


def run():
    directories = {name: LOCAL / f'runs/{name}' for name in ('U00', 'U01')}
    initial = {name: torch.load(path / 'initial-state.pt', weights_only=False)
               for name, path in directories.items()}
    assert initial['U00'].keys() == initial['U01'].keys()
    assert all(torch.equal(value, initial['U01'][key]) for key, value in initial['U00'].items())
    active = ('goal_condition.', 'execution.action.', 'execution.query.', 'execution.candidate.',
              'execution.family.', 'execution.offset_bias.', 'execution.special.')
    frozen = [key for key in initial['U00'] if not key.startswith(active)]
    records, bindings = [], {}
    infos = {name: json.loads((OUT / f'{name}.json').read_text()) for name in directories}
    for path in sorted(directories['U00'].glob('round-*.pt')):
        other = directories['U01'] / path.name
        if not other.exists():
            continue
        a, b = [torch.load(p, weights_only=False) for p in (path, other)]
        assert not a['dynamic'] and b['dynamic']
        for key in ('round', 'upstream_checkpoint_sha256', 'protocol_sha256', 'numpy_rng'):
            assert a[key] == b[key], (path.name, key)
        assert torch.equal(a['torch_rng'], b['torch_rng'])
        assert a['optimizer']['param_groups'] == b['optimizer']['param_groups']
        for name, value in [('U00', a), ('U01', b)]:
            assert all(torch.equal(value['state'][key], initial[name][key]) for key in frozen)
        records.append(dict(round=a['round'], frozen_tensors_exact=True,
                            RNG_and_optimizer_parameter_order_exact=True))
        for p in (path, other):
            bindings[str(p)] = digest(p)
    for name, info in infos.items():
        path = directories[name] / f"round-{info['selected_round']:02d}.pt"
        assert digest(path) == info['checkpoint_sha256']
    immutable_json(OUT / 'U01-pair-contract.json', dict(
        initial_state_tensors_identical=True, initial_tensor_count=len(initial['U00']),
        frozen_state_tensor_count=len(frozen), common_rounds=records,
        selected_rounds={name: info['selected_round'] for name, info in infos.items()},
        completed_updates={name: info['completed_updates'] for name, info in infos.items()},
        bindings=bindings, source_sha256=digest(__file__),
        qualification='Same seeded sequence-chunk implementation and NumPy RNG at common rounds. '
                      'Optimization gradients/states and trained weights are intentionally different. '
                      'These checks establish controls, not identical learned predictions or robustness.',
        new_fits=0, reserved_opened=0))
    print('Matched fit contract passed', len(records), 'common rounds', flush=True)


if __name__ == '__main__':
    run()
