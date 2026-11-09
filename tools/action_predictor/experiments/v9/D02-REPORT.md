# D02: measured model bottlenecks

No optimization or reserved evaluation was performed. All 433,071 training and 14,439 original development rows are retained. Training and development have different action frequencies; compare category/context results rather than interpreting the overall gap alone.

| Model / split | Strict complete command | Macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| train_M01 | 75.39% | 0.77245 | 0.825064 |
| validation_M01 | 79.03% | 0.63239 | 0.872799 |
| train_P05 | 75.94% | 0.77245 | 0.710915 |
| validation_P05 | 79.45% | 0.63239 | 0.730903 |

Movement is a substantial fitting bottleneck: continuing destinations are exact on 93.97% of training and 93.82% of development rows; direction-change destinations are exact on only 32.95% and 23.92%. Change/continuation shared-gradient cosine is negative in all 12 fixed diagnostic batches (mean -0.5305). This local measurement motivates testing specialization; it does not prove a redesigned branch will generalize.

In 24 fixed training games, observable entity type, buffs, abilities and cooldowns are absent from the legacy entity summary. Nearest-three summaries omit 56.44% of visible living camps in that sample. The candidate grid retains aggregates from all visible entities; not all distant information is lost. The classifier does not receive that grid directly.

P05 priority exactness is 25.16% on training versus 18.92% on development, with worsening validation loss after epoch two in the preserved study. Capacity/regularization and conditional structure remain hypotheses. Direction changes are weak even in training; enlarging an unchanged output alone has little supporting evidence.

Other sampled task-gradient cosines are near zero or mixed. No general gradient-interference claim is supported. Nearly all encoded inputs are unique; the few conflicting encoded rows cannot prove hidden-state dependence or randomness. Full personal-observation equivalence was not established.

Ward augmentation raises its share from 0.759% to 2.504% before class weighting. The planned natural-frequency and weighting comparisons remain separate from the entity experiment. Existing blanket suppression has negative evidence.

Ranked next experiments: matched entity-attention inputs with a trainable classifier/GRU/movement branch; recorded-change supervision/mixture; matched fresh GRU versus causal transformer with identical observation histories; sampling/weighting; nonlinear conditional full-support priority. All need measured complete-command predictions.

All 43 shop arguments remain unassessed strict failures. Altar and teleport each have only two development examples and remain uncertified. The 90% per-category goal, original targeting guards and three-seed requirement are unchanged. Both 75-game reserved partitions stay sealed.
