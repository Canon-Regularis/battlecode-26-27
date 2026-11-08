"""Saved-output comparison of original P05 epochs; never selects a checkpoint."""
import json
from pathlib import Path

import numpy as np

from ..audit import immutable_json
from ..data import digest
from .trajectory import ROOT, LOCAL, OUT


def run():
    info = json.loads((OUT / 'PD00.json').read_text())
    for relative, expected in info['outputs'].items():
        assert digest(ROOT / relative) == expected, relative
    with np.load(LOCAL / 'row-table.npz') as z:
        target, group, natural = z['target'], z['group'], z['natural']
    with np.load(LOCAL / 'epoch-2-predictions.npz') as z:
        before, old_nll = z['integer'] == target, z['nll']
    with np.load(LOCAL / 'epoch-8-predictions.npz') as z:
        after, new_nll = z['integer'] == target, z['nll']
    result = {}
    for label, mask in [('augmented', np.ones(len(target), bool)), ('natural', natural)]:
        groups = np.unique(group[mask])
        support = np.array([(mask & (group == g)).sum() for g in groups])
        gains = np.array([(after.astype(int) - before)[mask & (group == g)].sum() for g in groups])
        losses = np.array([(new_nll - old_nll)[mask & (group == g)].sum() for g in groups])
        rng = np.random.default_rng(20261106)
        draws = np.stack([np.bincount(rng.integers(len(groups), size=len(groups)),
                                     minlength=len(groups)) for _ in range(2000)])
        denominator = draws @ support
        result[label] = dict(rows=int(mask.sum()),
            rescues=int((mask & ~before & after).sum()),
            regressions=int((mask & before & ~after).sum()),
            net=int(gains.sum()), group_net_commands=dict(zip(map(str, groups), map(int, gains))),
            paired_whole_group_accuracy_difference_interval=np.quantile(draws @ gains / denominator, [.025, .975]).tolist(),
            paired_whole_group_NLL_difference_interval=np.quantile(draws @ losses / denominator, [.025, .975]).tolist())
    immutable_json(OUT / 'PD00-comparison.json', dict(
        comparisons=result, analysis_sha256=digest(OUT / 'PD00.json'),
        source_sha256=digest(Path(__file__)),
        inference='In-sample TRAIN checkpoint comparison; not out-of-sample uncertainty. '
                  'Historical epoch2 remains selected; epoch8 is not a replacement.',
        units=dict(accuracy='Difference in accuracy fraction', NLL='Mean difference in nats per recorded priority'),
        whole_group_draws=2000, seed=20261106, new_fits=0, reserved_opened=0))
    text = '''# PD00: continued fitting, worsening historical DEV loss

This read-only diagnosis scores all eight preserved original P05 checkpoints on identical TRAIN priority rows. No optimizer runs, checkpoint selection or policy replacement occur. The original selected epoch remains 2.

| Diagnostic | Epoch 2 | Epoch 8 |
| --- | ---: | ---: |
| Natural TRAIN exact integer | 2,416/9,815 (24.62%) | 4,112/9,815 (41.90%) |
| Natural TRAIN conditional NLL | 3.007926 | 2.157002 |
| Augmented TRAIN exact integer | 3,727/14,816 (25.16%) | 6,231/14,816 (42.06%) |
| Augmented TRAIN conditional NLL | 2.927051 | 2.106969 |
| Historical full DEV joint NLL | 0.730903 | 0.748819 |

The original model was still improving its in-sample fitting when its historical DEV loss worsened. This contradicts a claim that optimization had simply stopped learning at the selected checkpoint. It does not establish that training longer would improve held-out imitation. TRAIN conditional losses and full DEV joint losses have different denominators and must not be compared as absolute values.

Natural TRAIN targets with frequency 1–9 improve from 136/1,056 to 643/1,056; frequency 10–99 from 913/4,387 to 1,736/4,387; frequency 100+ from 1,367/4,372 to 1,733/4,372. Poor fitting is therefore not confined to rare integer labels. Strata are descriptive; their different context/group distributions prevent attributing these differences to frequency itself.

Selected-epoch inference reproduces every retained G00/P05 TRAIN integer. All targets are in the existing absolute vocabulary. Missing coordinate/value vocabulary is not an explanation for these conditional integer errors. The context encoder is frozen, and current evidence does not isolate representation, optimization or omitted personal information.

The original trainer used unweighted priority NLL divided by the full minibatch length, approximately 8.76 priority rows per 256-row batch on average. PC00 used 128 priorities per full batch with different learning rate, decay and warm initialization. Thus the two studies do not isolate batching, representation, architecture, optimization or exposure. PC00 establishes small-set fit, while PD00 establishes continued original-data fit with worsening historical DEV loss.

Paired whole-group bootstrap intervals and rescue/regression counts are in PD00-comparison.json. These are in-sample comparisons over the same 94 TRAIN groups, not untouched generalization evidence. Original DEV losses are copied from the frozen report; no DEV payload is read. No new fit, match, download, bot/runtime work or reserved access occurs.

Reproduce: `.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_diagnosis.trajectory`, then `... -m tools.action_predictor.priority_diagnosis.compare`. Completed outputs are immutable, so use preserved artifacts rather than rerunning into existing destinations. PC00's independent review covers its declared scope; this subsequent diagnosis is separate evidence.
'''
    path = OUT / 'PD00-REPORT.md'
    assert not path.exists()
    path.write_text(text, encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
