# PD00: continued fitting, worsening historical DEV loss

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
