"""Explicit immutable fit/prediction/comparator reproduction inventory."""
import argparse
import json
from pathlib import Path
import subprocess
from .protocol import ROOT, OUT, LOCAL, ARMS
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    info = json.loads((OUT / f'{identifier}.json').read_text())
    protocol = json.loads((OUT / 'protocol.json').read_text())
    source = Path(__file__).parent
    for name, expected in protocol['sources'].items():
        assert digest(source / name) == expected, name
    files = list((LOCAL / f'runs/{identifier}').glob('*'))
    files += list(source.glob('*.py'))
    files += [OUT / name for name in ('protocol.json', 'upstream-ready.json', 'preflight-v2.json', 'interface-recovery-plan.json')]
    files += [p for p in OUT.glob(f'{identifier}*') if p.name != f'{identifier}-completion.json']
    for split in ('train', 'validation'):
        files += list((LOCAL / f'upstream/{split}').glob('*.npy'))
    for arm in ARMS:
        files += list((LOCAL / f'initial-v2/{arm}').glob('*.npz'))
    evaluation = json.loads((OUT / f'{identifier}-evaluation.json').read_text())
    files += [ROOT / name for name in evaluation['bindings']]
    files += [ROOT / name for name in protocol['bindings']]
    immutable_json(OUT / f'{identifier}-completion.json', dict(
        fit_source_commit=info['source_commit'],
        inventory_commit=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip(),
        selected_round=info['selected_round'], selected_updates=info['selected_updates'],
        completed_updates=info['completed_updates'],
        bindings={str(p.relative_to(ROOT)): digest(p) for p in sorted(set(files))},
        commands=['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.goal_readout.' + command
                  for command in ('protocol', 'cache', 'interface_protocol', 'preflight_v2', f'fit_interface {identifier}',
                                  f'evaluate {identifier}', f'report {identifier}', f'completion {identifier}')],
        tests='.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.goal_readout.test_model '
              'tools.action_predictor.learned_policy.test_pathway_inputs_v2',
        reproduction='Producers refuse existing fit/cache/preflight outputs. Do not rerun or overwrite '
                     'immutable attempts. This manifest binds cached causal inputs and retained earlier '
                     'extraction evidence, not an independent raw-PRE implementation.',
        new_fits=0, reserved_opened=0, promoted=False, three_seed_confirmed=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
