# Frozen full-policy priority comparison

The selected L02 policy, upstream filtering, family probabilities, other argument heads and joint MAP remain fixed. Only the normalized priority conditional distribution changes. These are no-fit model evaluations; bot work remains paused.

| Arm | Priority head | Complete DEV commands | Macro F1 | Observed joint NLL | Priority conditional / joint | Priority type FP |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| JP00 | P05 | 12,064/14,439 | 0.610444 | 0.656567 | 109/576 / 50/576 | 24 |
| JP01 | RC00 | 12,126/14,439 | 0.618026 | 0.634247 | 237/576 / 118/576 | 31 |
| JP02 | RC01 | 12,137/14,439 | 0.620048 | 0.629052 | 248/576 / 131/576 | 34 |
| JP03 | P03 | 12,049/14,439 | 0.608078 | 0.675026 | 96/576 / 32/576 | 17 |

The P05 null preserves the original semantic commands and conditional modes; its measured numerical differences are retained in the null receipts. All four arms were forecast and archived before current answers were read. No softmax over family modes or type-first decoder is used.

The primary contrast is real-trained RC01 against P05 and shuffled-trained RC00. P03 is a retained comparator, not a matched-capacity treatment.

A historical handoff error is corrected separately: retained P03 is 96/576 conditional integers, not 125/576. Its original frozen report agrees and every current P03 integer reproduces the original archive. The number 125 was an exploratory P05 continuation target; no historical artifact is rewritten.

Against JP00, JP02 rescues **88** commands and regresses **15**; paired whole-group accuracy-difference interval **[0.121, 1.123] percentage points**. NLL-difference interval **[-0.055500, -0.010643]**. Group net differences: `{'1': 13, '10': 5, '11': 0, '17': 8, '31': 47}`.

Against JP01, JP02 rescues **21** commands and regresses **10**; paired whole-group accuracy-difference interval **[-0.105, 0.294] percentage points**. NLL-difference interval **[-0.008179, -0.002588]**. Group net differences: `{'1': 3, '10': 0, '11': -6, '17': 0, '31': 14}`.

Against JP03, JP02 rescues **103** commands and regresses **15**; paired whole-group accuracy-difference interval **[0.208, 1.243] percentage points**. NLL-difference interval **[-0.089519, -0.022646]**. Group net differences: `{'1': 15, '10': 6, '11': 3, '17': 13, '31': 51}`.

## Where conditional gains go

- JP00: 109 correct integers; 50 correct complete priorities; 59 correct integers lose family competition; 232 true priorities cannot win even with hypothetical conditional point mass one, holding family beliefs and other heads fixed.
- JP01: 237 correct integers; 118 correct complete priorities; 119 correct integers lose family competition; 232 true priorities cannot win even with hypothetical conditional point mass one, holding family beliefs and other heads fixed.
- JP02: 248 correct integers; 131 correct complete priorities; 117 correct integers lose family competition; 232 true priorities cannot win even with hypothetical conditional point mass one, holding family beliefs and other heads fixed.
- JP03: 96 correct integers; 32 correct complete priorities; 64 correct integers lose family competition; 232 true priorities cannot win even with hypothetical conditional point mass one, holding family beliefs and other heads fixed.

The last count is an optimistic frozen-distribution bound, not achieved accuracy or an inference rule. Family beliefs are identical across arms. Correctly typed integer errors, wrong types and false-positive priority forecasts remain separately reported. Absolute/residual/fallback target-mass shares describe probability explanations, not Fish intent.

## Category and sampling evidence

| Recorded family | Support | JP00 complete | JP01 complete | JP02 complete | JP03 complete |
| --- | ---: | ---: | ---: | ---: | ---: |
| altar | 2 | 0 | 0 | 0 | 0 |
| attack | 985 | 892 | 892 | 891 | 892 |
| blocked | 110 | 4 | 4 | 4 | 4 |
| cancel | 2589 | 2542 | 2542 | 2542 | 2542 |
| cast_0 | 213 | 158 | 158 | 158 | 158 |
| cast_1 | 243 | 71 | 71 | 71 | 71 |
| end | 4096 | 3966 | 3965 | 3964 | 3966 |
| move | 2362 | 1365 | 1364 | 1364 | 1365 |
| priority | 576 | 50 | 118 | 131 | 32 |
| recall | 3084 | 2996 | 2992 | 2992 | 2999 |
| shop | 43 | 0 | 0 | 0 | 0 |
| submit | 22 | 20 | 20 | 20 | 20 |
| teleport | 2 | 0 | 0 | 0 | 0 |
| ward | 112 | 0 | 0 | 0 | 0 |

The JSON report contains type PRF/confusion, joint false positives, all-true-family and correctly typed parameters, category losses, continuation/change/startup movement, partial readiness, blocked-attempt versus successful-move mask flags, and direct paired targeting comparisons. Conditional nonpriority parameter paths remain fixed; their joint counts can change when priority wins or loses family competition.

| Arm | Natural TRAIN complete | Natural TRAIN priority conditional / joint | DEV complete |
| --- | ---: | ---: | ---: |
| JP00 | 247,646/288,801 | 2416/9815 / 1212/9815 | 12,064/14,439 |
| JP01 | 248,279/288,801 | 3278/9815 / 1971/9815 | 12,126/14,439 |
| JP02 | 248,392/288,801 | 3506/9815 / 2105/9815 | 12,137/14,439 |
| JP03 | 247,546/288,801 | 2141/9815 / 1040/9815 | 12,049/14,439 |

Augmented TRAIN and natural membership are distinct report strata. The report further separates natural rows in correction-fit groups, correction-held groups and other groups. These groups were previously seen by the warm encoder/head and research; they are not untouched full-policy evidence. Frozen upstream state uses the original augmented traversal cadence.

## Provenance and limits

Causal field recovery covers 433,071 TRAIN and 14,439 DEV rows. It reused 6,132 exact earlier TRAIN records and newly queried every remaining eligible decision. Personally unknown other champions are not imputed; rows with no known other units remain in evaluation. Scoped values and their availability are checked against the historical-engine contract. The original priority-chain audit was reused rather than repeated.

The five DEV groups are repeatedly inspected development evidence. Paired 2,000 whole-group resamples (seed 20261106) describe this exploratory comparison, with null empty denominators; they do not adjust for research selection or establish three-seed robustness. No arm is promoted automatically. All original category, macro-F1, movement, likelihood and targeting targets remain binding.

All 43 DEV shops remain strict failures; missing purchase-argument likelihood is absent from observed loss. Sparse altar/teleport/submit categories, coordinate/entity ambiguity, full legality and global calibration remain uncertified. The observed shop bucket is not complete original API-command probability. Both reserved partitions remain sealed; no matches, simulations, replay downloads, bot/runtime changes or deployments occurred.

Reproduction commands are in the completion inventory. Existing immutable destinations are consumed rather than overwritten. No training or optimizer update was performed; experiment wall time and end-to-end serving latency were not instrumented.
