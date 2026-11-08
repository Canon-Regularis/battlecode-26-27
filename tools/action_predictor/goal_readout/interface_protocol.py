"""Prospective interface repair; original failed preflight remains retained."""
from pathlib import Path
from .protocol import OUT, freeze
from ..audit import immutable_json
from ..data import digest


def amend():
    freeze()
    directory = Path(__file__).parent
    names = ('decoder_interface.py', 'interface_protocol.py', 'preflight_v2.py',
             'fit_interface.py', 'test_decoder_interface.py')
    plan = dict(original_protocol_sha256=digest(OUT / 'protocol.json'),
        failure='Original preflight stopped on its first decode batch with KeyError world. '
                'The unused returned goal diagnostics required by GoalPolicy.decode were '
                'absent from the readout-only step. Initial/U00 attempt directory retained; '
                'no fit, optimizer or saved forecast archive existed.',
        repair='Parameter-free adapter supplies explicit None for unused world/known/retain '
               'decoder return fields. Original GoalPolicy.decode arithmetic and all trained '
               'heads, inputs, priors, loss, initialized tensors, masks, budgets and metrics '
               'unchanged. No claimed values for those unavailable diagnostics.',
        reuse='The completed common upstream cache is unaffected and retained without regeneration.',
        new_paths='initial-v2/<arm> and preflight-v2.json; original initial/U00 untouched.',
        fit_entry='goal_readout.fit_interface installs the parameter-free subclass in the '
                  'unchanged registered fit runner, after asserting the v2 preflight passed.',
        sources={name: digest(directory / name) for name in names},
        new_fits=0, reserved_opened=0)
    immutable_json(OUT / 'interface-recovery-plan.json', plan)
    return plan


if __name__ == '__main__':
    amend()
