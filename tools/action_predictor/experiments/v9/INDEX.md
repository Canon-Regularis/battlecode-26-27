# V9: substantial representation and movement research

The category-wise 90% exact complete-command goal remains unmet. M01/P05 and all earlier negative results remain intact. The latest entity-input pair does not justify promotion or identical repeats.

| Model | Strict complete commands /14,439 | Macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| M01 | 11,411 (79.03%) | 0.63239 | 0.872799 |
| P05 | 11,472 (79.45%) | 0.63239 | 0.730903 |
| E00 zero-entity control | 11,461 (79.38%) | 0.62910 | 0.726085 |
| E01 actual-entity treatment | 11,437 (79.21%) | 0.63357 | 0.728824 |

## Findings and experiment

[D02](D02-REPORT.md) measures all training predictions, training/development gaps, information loss and local gradient conflict. Continuing move destinations are about94% exact, while direction changes are only33% exact on training and24% on development. The problem is not solely overfitting. Nearly all encoded inputs are unique, so collisions cannot establish inherent randomness or hidden-state limitations.

[D03](D03-NOTE.md) shows weaker change prediction away from obstacles and ward nominal weighted sample mass of5.03% versus0.759% naturally sampled. Those are diagnostic associations, not demonstrated causal mechanisms.

E00/E01 retrain the GRU, action classifier and independent movement branch, preserving strong argument paths through an independent frozen teacher. Both use identical41causal priority channels, initialization, rows, class weights, optimizer settings and loss-based checkpoint selection. E01 alone receives richer119-field personally visible entity tokens, without nearest-k or entity IDs. Buffs are summarized, not losslessly represented. Nominal233,566 trainable parameters match, but zeroing entity values disables some input-dependent control weights. Total model size is545,800 parameters including frozen components.

[E00](E00-REPORT.md), reviewed by a fresh GPT-6.1 Sol xhigh agent, does not improve complete commands over P05. [E01](E01-REPORT.md), pending its required fresh completed-fit review, loses24 strict successes versus E00 (369fixes,393regressions). The paired whole-group strict-gain interval is -0.289 to -0.061 percentage points; it is conditional on checkpoint selection and five reused groups. This is evidence against this particular global pooled entity-input package, not every attention architecture.

E01 changes destination exactness on continuing moves from E00's90.90% to88.65%, while changes rise27.81% to29.71%. Joint movement falls1,282 to1,275/2,362. Ward false positives decrease362 to338 versus E00, but remain above P05's282;301recorded recalls are predicted as ward. Stronger rare-category discrimination remains necessary. No retrospective threshold changes or accuracy-selected checkpoints.

## Evidence

- [Matched E01-E00 results, authoritative V2](E01-matched-comparison-v2.json) and [category table](E01-matched-categories-v2.csv): category supports, paired uncertainty, movement contexts, explicit ward false positives and targeting deltas. V1 ambiguous diagnostic parameter fields are preserved; V2 explicitly reports assessed parameter support and null for shops/no-required-argument categories. Joint results and benchmark rows are unchanged.
- [E01 complete category results](E01-per-category.csv), [confusion matrix](E01-confusion.csv), [train/development predictions report](E01.json), and [comparison table](comparison-v2.csv).
- [E01 causal inference proof](E01-causal-inference-roundtrip.json):75target personal-PRE streams,675family routes, exact reconstructed inputs and routing parity. Zero probability error compares identical reconstructed inputs; it is not by itself independent saved-probability reproduction. [Attention checks](E01-attention-checks.json) establish trained-model padding/permutation invariance and actual entity-value use, not quality.
- [P05](P05-serving.json), [E00](E00-serving.json) and [E01](E01-serving.json) CPU model-kernel serving timings and memory. Prepared inputs exclude feature construction; process RSS includes Torch/data, not only weights.
- [Ranked plan](ranked-plan.json), [category coverage](ranked-plan-category-addendum.json), [original checkpoints](CHECKPOINTS.md), [commands](COMMANDS.md), [review findings addressed](E00-review-response.json). E01 selects epoch5 of11,18,612updates,470.95seconds; all checkpoints and negative results remain local.

Next justified alternatives are a causal learned continuation/change mixture and independent natural-frequency/augmentation-weight studies; then a controlled fresh GRU versus causal transformer with identical full observation histories and budgets. No true next direction is an inference input. No automatic repeats of this failed pair.

All43shops remain unassessed strict failures. Altar/teleport each have two examples and remain uncertified; submit's22examples do not establish reliability. Original macro-F1, movement/loss and targeting targets remain binding, with three-seed consistency required. Both75-game reserved partitions remain sealed. No downloads, games, playing-bot changes, deployment, merge or auto-merge.

## Reproduction boundary

Use exact local replay data, checkpoints, pinned runtime assets and prepared caches identified by hashes in the plans/completion receipts. Raw replays, weights and large arrays remain ignored. Committed code/protocols/reports do not establish clean-checkout training reproducibility without those artifacts. Immutable cache hashes replace repeated unchanged495-game reconstruction checks; extraction changes require relevant causal checks. See the retained V8 index for prior studies and unavailable purchase evidence.
