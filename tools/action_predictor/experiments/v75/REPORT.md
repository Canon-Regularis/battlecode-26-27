# V75: trained full-action movement integration

The trained router scores **12,141/14,439 complete commands (84.0848%)**, versus
JP02's **12,137 (84.0571%)** and unconditional V59 dispatch's **12,115 (83.9047%)**.
The net gain over the stronger JP02 reference is **four commands**, all direction
changes. Continuation and every nonmovement category remain unchanged.

This is a small exploratory gain, not an established reliable improvement. The
paired group interval includes zero, and most of the net gain comes from one
group. The router is opt-in; no default replacement or promotion is made.

## What was trained

Both experts remain frozen. A new 274-parameter linear readout with tanh output
learns the expected difference in complete-command correctness between their
destinations. Its 273 causal inputs are 253 canonical PRE features, nine V59
movement probabilities, and eleven confidence, coordinate and incoming-history
summaries. No current recorded command, destination, group identifier, future
goal or hindsight behavior code enters the router.

JP02 still chooses the action family. At an eligible located predicted-movement
disagreement, the router switches to V59 only when its predicted advantage is
positive. Ties, unavailable outputs, later within-turn queries and nonmovement
commands retain JP02. This remains decision-level dispatch, not joint MAP under
a new calibrated command distribution; no hybrid command NLL is claimed.

The objective is mean squared error on signed correctness differences: +1 for a
V59 rescue, -1 for a regression, zero when both destinations are wrong. There is
no class balancing. The readout starts at exactly zero, so the initial decision
policy reproduces JP02. All neural expert weights stay unchanged.

## Fitting-only data and selection

The frozen population contains 30,042 full-action decisions from the existing
32 fitting games. These are the same fitting games used by the movement study,
not its eight research evaluation games or any original DEV games. There are
799 eligible predicted-movement disagreements: 226 rescues, 284 regressions and
289 both-wrong ties under unconditional replacement. Only these disagreements
contribute optimizer losses; all 30,042 decisions contribute selection scores.

Forecast preparation uses V74's chronological history interface. Actual prior
turns, masked missing PREs, complete previous-turn commands and 32-turn resets
are preserved. The training loader additionally handles the original augmented
selected PREs. Each current prediction precedes assimilation of its command.
All fitting forecasts are saved before constructing correctness targets.

Four whole-game folds each train on 24 games and validate on eight. Normalizers
use only active training queries within that fold. The frozen experts previously
trained on these fitting games: **router update exclusion is real, but these are
not end-to-end unseen expert forecasts**. Their validation is for selecting the
new integration procedure, not certifying the full policy.

| Selected from fitting-game validation | Complete commands | Changes | Continuations |
| --- | ---: | ---: | ---: |
| Epoch 0 / JP02 | 23,689 | 707 | 2,219 |
| Epoch 4 | 23,700 | 718 | 2,219 |
| Epoch 8 | 23,694 | 711 | 2,220 |
| Epoch 16 | 23,699 | 721 | 2,215 |
| **Epoch 32** | **23,706** | **724** | **2,219** |

Selection maximizes complete commands, requires no net change-count loss and
at most 0.5 percentage points of continuation loss, and breaks ties toward an
earlier epoch. Epoch zero is eligible. All four selected-duration fold models
together gain 17 commands, with fold differences +10, -3, -9 and +19.

All fits use seed 75001, AdamW learning rate 0.003, weight decay 0.01, batch 128
and clipping threshold 5. Four 32-epoch fold fits use 640 updates. The single
32-game final refit uses the selected 32 epochs and 224 updates, totaling
**864 optimizer updates / 102,272 disagreement presentations**. No update clips;
all archived norms, losses and optimizer tensors are finite. Preparation takes
597.58 seconds. No DEV target enters fitting or checkpoint selection.

The final refit's in-sample gain is 119 commands, much larger than the held-fold
gain of 17. That gap is retained as an overfitting/generalization limitation,
not presented as expected deployed accuracy.

## Full development evaluation

The selected checkpoint is applied once to all 14,439 saved V74 forecasts.
There is no post-evaluation threshold adjustment, additional seed or retry.

| Same original DEV population | JP02 | V74 unconditional dispatch | Trained router |
| --- | ---: | ---: | ---: |
| Complete commands / 14,439 | 12,137 | 12,115 | **12,141** |
| Complete moves / 2,362 | 1,364 | 1,342 | **1,368** |
| Complete changes / 1,158 | 272 | 269 | **276** |
| Complete continuations / 1,198 | 1,089 | 1,070 | **1,089** |

Complete movement accuracy rises from 57.7477% to 57.9170%. The router changes
207 destinations, rescuing 61 commands and regressing 57. Combat, other
nonmovement commands, all action-type predictions and their macro-F1 (0.620048)
are unchanged. Predicted-movement false positives remain 195.

| Nonmovement category | Correct / support, unchanged |
| --- | ---: |
| Attack | 891 / 985 |
| Cast 0 | 158 / 213 |
| Cast 1 | 71 / 243 |
| Priority | 131 / 576 |
| Recall | 2,992 / 3,084 |
| Cancel | 2,542 / 2,589 |
| End | 3,964 / 4,096 |
| Ward | 0 / 112 |
| Shop | 0 / 43 |
| Submit | 20 / 22 |
| Blocked | 4 / 110 |
| Altar | 0 / 2 |
| Teleport | 0 / 2 |

Shops lack purchase arguments and remain strict unassessed failures. Sparse
categories and ambiguous entity targets retain their previous limitations.

Group net changes are **-1, -1, +2, +8, -4**. The descriptive 2,000 whole-group
bootstrap interval for the overall accuracy difference is **[-0.0802, +0.1505]
percentage points**. Removing the +8 group reverses the overall gain. Thus the
result does not establish a dependable improvement across games. Five reused
research groups, prior recipe selection and one seed remain material limits.

`result.json` retains V74's metric schema. Its `eligible_queries` field now counts
router-admitted disagreements, not original interface coverage. Full original
interface eligibility and fallback coverage are preserved in the V74 report.
The `routing` block is the primary admission/complete-command summary.

## Weight inspection and verification

The selected readout has 189 nonzero coefficients, L2 norm 0.650985 and bias
-0.078475. Its largest normalized coefficient is -0.307640 on JP02's conditional
movement log probability; V59 entropy has coefficient -0.139462. Holding other
inputs fixed within the unclipped range, greater baseline confidence or more
diffuse V59 predictions discourages switching. Correlated standardized features
make coefficient magnitude unsuitable as a causal attribution or a strategy
explanation. `weight-audit.json` preserves the numerical inspection.

Ten synthetic contract tests pass. Direct parent verification checks all 30,042
canonical fitting identities, prepared features/targets and fold memberships;
fit-only normalizers and zero initial tensors; every sampler order, RNG state,
optimizer step and finite archived gradient; every fold checkpoint score and
the selected full-refit tensors. All 14,439 runtime decisions match evaluation.
Fresh fitting forecasts reproduce exactly on one game of each engine version
(1,911 selected queries). No subagents or optimizer replay were used.

The plan binds 103 source files, 299 training inputs and seven assessment inputs.
The eight movement-research evaluation games, original tuning/assessment payloads
and reserved partitions are not used for this router fit. No engine operation,
download, match, deployment or playing-bot modification occurred.

## Use and reproduction

The opt-in `TrainedMovementRouter` loads the hash-bound checkpoint at
`.cambc/action-predictor/v75/selected.pt`. Use it alongside `TurnMovementAdapter`.
Its runtime `predict` receives canonical current PRE features, the V59 movement
record, JP02's predicted action/coordinate, and JP02's conditional-movement and
movement-family log probabilities. The movement record contains eligibility,
offset, nine probabilities and incoming history age. It returns the chosen
coordinate and routing score; it accepts no correctness label.

Creation order was:

```powershell
python -m tools.action_predictor.behavior_segments.integration_router_fit freeze
python -m tools.action_predictor.behavior_segments.integration_router_fit prepare
python -m tools.action_predictor.behavior_segments.integration_router_verify prefit
python -m tools.action_predictor.behavior_segments.integration_router_fit fit
python -m tools.action_predictor.behavior_segments.integration_router_fit assess
python -m tools.action_predictor.behavior_segments.integration_router_verify final
```

Use the final verifier for existing completed artifacts instead of rerunning
creation commands. All original checkpoints and prior results remain preserved.
The small observed gain does not establish learned strategy, autonomous playing
strength, 80% movement accuracy, category reliability or three-seed robustness.
