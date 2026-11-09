"""Read-only checks of actual H00/H01 initial tensors and update schedule."""
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from .data import ROOT, WORK, REPORT


def run():
    paths = {a: WORK/f'runs/{a}/initial.pt' for a in ('H00', 'H01')}
    saved = {a: torch.load(p, weights_only=False, map_location='cpu') for a, p in paths.items()}
    a, b = saved['H00'], saved['H01']
    common = sorted(set(a['state']) & set(b['state']))
    mismatches = [name for name in common if not torch.equal(a['state'][name], b['state'][name])]
    normalization = all(torch.equal(a[k], b[k]) for k in ('mean', 'std')) and a['config'] == b['config']
    schedule = []
    for old in sorted((WORK/'runs/H00').glob('round-*.pt')):
        other = WORK/'runs/H01'/old.name
        if not other.exists(): continue
        h = torch.load(old, weights_only=False, map_location='cpu')
        n = torch.load(other, weights_only=False, map_location='cpu')
        schedule.append(dict(round=h['round'], H00_updates=h['updates'], H01_updates=n['updates'],
            numpy_rng_equal=h['numpy_rng'] == n['numpy_rng']))
    names = ('lr', 'betas', 'eps', 'weight_decay', 'amsgrad', 'maximize')
    optimizer = all(a['optimizer']['param_groups'][0][k] == b['optimizer']['param_groups'][0][k] for k in names)
    raw = dict(common_tensor_count=len(common), common_tensor_mismatches=mismatches,
        normalization_and_config_identical=normalization, optimizer_settings_identical=optimizer,
        initial_optimizer_state_empty=not a['optimizer']['state'] and not b['optimizer']['state'],
        initial_numpy_rng_identical=a['numpy_rng'] == b['numpy_rng'],
        initial_torch_rng_identical=torch.equal(a['torch_rng'], b['torch_rng']),
        completed_common_rounds=schedule,
        bindings={str(p.relative_to(ROOT)): digest(p) for p in paths.values()},
        source_sha256=digest(__file__),
        scope='Actual initial checkpoints and already completed common schedules. Architecture-specific tensors and final Torch RNG differ by architecture; common tensors and NumPy sampling must match. No dropout/Torch random sampling in either frozen training loop. This is not output equality, performance, or identical realized gradient influence.',
        new_fits=0, optimizer_updates=0, reserved_opened=0)
    immutable_json(REPORT/'H01-initial-contract.json', raw)
    if mismatches or not normalization or not optimizer or not raw['initial_optimizer_state_empty'] or not raw['initial_numpy_rng_identical']:
        raise RuntimeError('Matched initialization contract failed; evidence preserved')
    if any(not v['numpy_rng_equal'] or v['H00_updates'] != v['H01_updates'] for v in schedule):
        raise RuntimeError('Common schedule differs; evidence preserved')


if __name__ == '__main__': run()
