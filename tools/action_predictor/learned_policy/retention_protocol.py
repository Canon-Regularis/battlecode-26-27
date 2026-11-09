"""Prospective one-fit L02 protocol, additive to frozen L00/L01."""
import json
from pathlib import Path
from .sequence_data import ROOT, REPORT, WORK
from ..audit import immutable_json
from ..data import digest


def freeze():
    design = json.loads((REPORT/'policy-design.json').read_text())
    sources = {name:digest(Path(__file__).parent/name) for name in
        ('retention_protocol.py','retention_routing.py','retention_fit.py','retention_preflight.py')}
    for name, expected in design['sources'].items():
        assert digest(Path(__file__).parent/name) == expected, name
    reference = json.loads((REPORT/'L01.json').read_text())
    value = dict(id='L02-command-only-retention-gradient', fits=['L02'], additional_fit_budget=1,
        seed=design['seed'], control='Retained L01, no control refit',
        intervention='Compute command-loss gradients for retention.weight/bias through the entire eight-node BPTT graph. Compute original command + .05 future-position auxiliary gradients for every other trainable parameter. Before original global clipping, replace only retention gradients with command derivatives. No activation detach, no forward or architectural change.',
        unchanged='Architecture, data and augmentation, initialization, warm M01/P05 components, normalization, actor order/chunk RNG, auxiliary target/weight, decoder, all evaluation denominators/definitions, optimizer LR/weight decay/clipping, seed and original full-DEV NLL checkpoint rule remain L01 settings.',
        optimizer_qualification='Shared global clipping scale can differ because the gradient vector changes; AdamW weight decay still applies to retention. Auxiliary can indirectly affect retention later via learned upstream features/state. The intervention removes its direct parameter derivatives, not every indirect effect.',
        initialization='Fresh seed20261114 from warm M01, not fine-tuning L01. Same constructor and RNG draw order.',
        training=design['training'], architecture_sha256=digest(Path(__file__).parent/'model.py'),
        frozen_design_sha256=digest(REPORT/'policy-design.json'), sources=sources,
        control_checkpoint_sha256=reference['checkpoint_sha256'],
        control_predictions_sha256=reference['predictions_sha256'],
        primary='Full original DEV observed joint command NLL, min improvement .0001, patience6,max35. No checkpoint/threshold selection by accuracy, retention, auxiliary or movement.',
        metrics=['all original DEV and augmented/natural TRAIN complete-command exactness, action macro F1/confusion/false positives',
                 'per-category type/all-true-family/correctly-typed parameters/joint command and NLL',
                 'continuation/change/startup movement, blocked destinations and outcome accounting',
                 'paired 2000 whole-group resamples seed20261106 vs L01 (primary), L00/B00/G00 references',
                 'effective retention/soft age, component execution diversity/opportunities and fixed-distribution bounds',
                 'supplemental matched natural-cadence evaluation under existing definitions'],
        continuation='Finish one fit and required fresh Sol6.1xhigh review. No automatic repeats or further fits. No promotion unless original category/macro/movement/NLL/targeting and three-seed requirements are satisfied; meaningful single-seed evidence may justify only a separately declared replication budget.',
        interpretation='Matched causal intervention on the optimization graph, not proof of Fish objectives or guaranteed persistence usefulness. One seed and five reused DEV groups; paired intervals are conditional on checkpoint selection.',
        safety='Model training/evaluation only. Both75-game reserved partitions sealed. No matches, replay downloads, bot/runtime/native/SDK/fuel/export/deployment work. Every shop strict failure, unavailable purchase likelihood absent. Preserve sparse-category and identity/legality limitations.',
        new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'L02-protocol.json',value)
    return value


if __name__=='__main__': freeze()
