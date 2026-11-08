"""One declared fixed-weight projection-geometry diagnostic, no new fit."""
import argparse
import json
import numpy as np
import torch
from .protocol import LOCAL, OUT
from .model import FrozenGoalReadout
from .decoder_interface import ReadoutDecoderInterface
from .data import load, geometry_reference
from .inference import infer
from .preflight import semantic_equal
from ..learned_policy.pathway_reference import load_model
from ..learned_policy.retention_gradients import fingerprint
from ..learned_policy.analysis import read, paired_categories
from ..movement_experts.evaluate import summary, masks
from ..audit import immutable_json
from ..data import digest


def freeze():
    immutable_json(OUT / 'U01-sensitivity-plan.json', dict(
        registration_stage='Supplemental plan during U01 fitting, after early round1/2 DEV NLL '
                           'was observed; before selected-checkpoint/sensitivity evaluation. '
                           'Not represented as part of the original before-fit protocol.',
        intervention='One fixed-weight TRAIN-mean replacement of the named geometry projection '
                     'in selected U01. Keep uncertainty, availability, bias, all trained weights '
                     'and common frozen upstream cache/filter unchanged. Other geometry paths remain.',
        purpose='Separate dependence of selected readout decisions on variable geometry from '
                'the between-fit effect of dynamic versus mean training. No replacement selection '
                'or influence on checkpoint, budget, primary metrics or allocation criterion.',
        checks='All14439DEV rows; save predictions/diagnostics, unknown-position equality, '
               'conditional/joint direction results, per-category paired loss/targeting, '
               'semantic mode changes and fixed-weight tensor fingerprint.',
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


@torch.no_grad()
def run():
    freeze()
    torch.set_num_threads(4)
    info = json.loads((OUT / 'U01.json').read_text())
    checkpoint = LOCAL / f"runs/U01/round-{info['selected_round']:02d}.pt"
    assert digest(checkpoint) == info['checkpoint_sha256']
    upstream, _, _ = load_model('L02')
    model = ReadoutDecoderInterface(upstream, geometry_reference(), True)
    model.load_state_dict(torch.load(checkpoint, weights_only=False)['state'])
    before = fingerprint(model)
    d = load('validation')
    primary_path = LOCAL / 'runs/U01/validation-predictions.npz'
    assert digest(primary_path) == info['predictions_sha256']['validation']
    primary = read(primary_path)
    directory = LOCAL / 'sensitivity/U01-geometry-mean'
    assert not directory.exists(), 'Preserve attempts'
    directory.mkdir(parents=True)
    model.dynamic = False
    prediction, diagnostic = infer(model, d)
    np.savez_compressed(directory / 'validation-predictions.npz', **prediction)
    np.savez_compressed(directory / 'validation-diagnostics.npz', **diagnostic)
    same = semantic_equal(prediction, primary)
    unknown = ~np.asarray(d['cache']['position_known'])
    unchanged = fingerprint(model) == before
    results = {key: summary(d, prediction, mask) for key, mask in masks(d).items()
               if key in ('all', 'move', 'blocked', 'continue', 'change', 'startup')}
    immutable_json(OUT / 'U01-sensitivity.json', dict(results=results,
        paired=paired_categories(d['raw'], prediction, primary, np.ones(len(same), bool)),
        semantic_mode_changes=int((~same).sum()), unknown_position_rows=int(unknown.sum()),
        unknown_position_semantic_changes=int((unknown & ~same).sum()), weights_unchanged=unchanged,
        predictions_sha256=digest(directory / 'validation-predictions.npz'),
        diagnostics_sha256=digest(directory / 'validation-diagnostics.npz'),
        selected_checkpoint_sha256=digest(checkpoint), primary_sha256=digest(primary_path),
        plan_sha256=digest(OUT / 'U01-sensitivity-plan.json'),
        qualification='Fixed-weight selected-checkpoint diagnostic, no replacement or intent claim. '
                      'Common upstream filtering makes a separate readout-refilter variant unnecessary. '
                      'Mean preserves defined TRAIN reference contributions, not all goal paths.',
        new_fits=0, reserved_opened=0))
    assert unchanged and (same[unknown]).all()
    print('Fixed-weight sensitivity completed', int((~same).sum()), 'mode changes', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    if parser.parse_args().freeze:
        freeze()
    else:
        run()
