"""Run the registered fit with the reviewed-command-math interface repair."""
import argparse
import json
from . import fit
from .protocol import OUT, ARMS
from .interface_protocol import amend
from .decoder_interface import ReadoutDecoderInterface
from ..data import digest


def run(identifier):
    amend()
    preflight = json.loads((OUT / 'preflight-v2.json').read_text())
    assert preflight['passed']
    assert preflight['recovery_plan_sha256'] == digest(OUT / 'interface-recovery-plan.json')
    fit.FrozenGoalReadout = ReadoutDecoderInterface
    fit.run(identifier)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
