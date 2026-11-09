# V74: V59 movement dispatch into the full-action predictor

Using the strongest retained conditional movement checkpoint does **not** improve
the complete predictor in this frozen integration. JP02 scores **12,137/14,439
(84.0571%)** complete commands; JP02 with V59 destination dispatch scores
**12,115/14,439 (83.9047%)**. There are 119 rescues and 141 regressions, net -22.
No model is promoted, and all original weights remain unchanged.

## What was combined

JP02 continues to choose the action family through its original joint-MAP
decoder. Every nonmovement argument stays fixed. When it predicts movement,
V59 supplies the destination only if no earlier nonadministrative command has
occurred in the current own turn and a located prediction is available. Later
within-turn movements and unavailable outputs fall back to JP02.

The eligibility gate reads **past** actual commands, never the current recorded
family. Predictions are made before assimilating each scored command. This
avoids calling V59 only when a replay label says the current action is movement.
Every original DEV decision remains in the denominator, including combat,
administrative actions, missing arguments and fallback rows.

This is a decision-level destination override, **not** joint MAP under a newly
calibrated combined probability model. We do not report hybrid command NLL or
attach JP02's old likelihood to the changed decisions. Action-type macro-F1 is
unchanged at 0.620048, as expected from freezing the action choices.

## Results on the same complete population

| Recorded action | Rows | JP02 correct | Combined correct |
| --- | ---: | ---: | ---: |
| Attack | 985 | 891 | 891 |
| Cast 0 | 213 | 158 | 158 |
| Cast 1 | 243 | 71 | 71 |
| Move | 2,362 | 1,364 | 1,342 |
| Priority | 576 | 131 | 131 |
| Recall | 3,084 | 2,992 | 2,992 |
| Cancel | 2,589 | 2,542 | 2,542 |
| End | 4,096 | 3,964 | 3,964 |
| Ward | 112 | 0 | 0 |
| Shop | 43 | 0 | 0 |
| Submit | 22 | 20 | 20 |
| Blocked | 110 | 4 | 4 |
| Altar | 2 | 0 | 0 |
| Teleport | 2 | 0 | 0 |
| **All** | **14,439** | **12,137** | **12,115** |

Complete movement falls from **57.7477% to 56.8163%**. Conditional destination
correctness falls from 1,428 to 1,398/2,362. Complete continuations fall from
1,089 to 1,070/1,198; complete changes fall from 272 to 269/1,158. Startup
correctness stays at 3/6. Predicted-movement false positives stay at 195.
Every nonmovement complete-command outcome and conditional argument score is
unchanged. Shopping remains unassessed under the strict metric because purchase
arguments are unavailable; zero is not a measured shopping-policy accuracy.

Group net changes are -7, -3, -6, 0 and -6 commands. The descriptive paired
2,000 whole-group bootstrap interval is **[-0.2307, -0.0603] percentage points**
for overall accuracy. Five previously reused groups and the research history
preclude treating this as untouched certification or a three-seed result.

## Coverage and history

Of 14,439 queries, 6,884 precede any earlier nonadministrative command and 6,557
also have a located V59 output. The adapter routes 2,220 predicted movements;
450 complete predicted commands actually change their destination. Among true
movements, 2,158 have eligible outputs and 204 use fallback. On the eligible
movement cohort, complete correctness is 1,288 for JP02 and 1,266 for the hybrid.
The 204 fallback movements remain at 76 correct in both arms.

V59 was trained for first-nonadministrative queries within 32-turn windows.
The adapter preserves one recurrent transition per actual own turn and uses
the same incoming prior-turn state for administrative queries preceding that
turn's first nonadministrative command. Only after that command is observed is
its candidate state committed. Administrative-only turns receive a masked
transition. The descriptor ends at the current PRE; signed movement vectors
come only from the completed previous own turn. Separate actor streams reset
at 32 turns from the start of their indexed chronology.

Across the 25 games, reconstruction traverses 113,227 own turns: 14,594 observed
first-nonadministrative PREs, 68,554 missing ones and 30,079 administrative-only
turns. Missing observations are masked rather than stitched out. This clock and
availability differ from the narrow selected-window movement benchmark.

V59's 318/513 (61.99%) result therefore cannot be substituted for movement
accuracy on this full-action population. Its 40 research games are group-disjoint
from these five original DEV groups, but both studies remain historically
exposed research. The difference in score does not identify history gaps,
distribution shift, calibration or the weights as the sole cause. This result
rejects this direct dispatch, not every possible learned combination.

## Reproduction and use

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.behavior_segments.full_action_evaluate freeze
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.behavior_segments.full_action_evaluate forecast
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.behavior_segments.full_action_evaluate assess
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.behavior_segments.full_action_verify
```

Creation commands reject existing immutable destinations; use the verifier to
check the completed artifacts. The plan binds 101 source files and 209 inputs.
All forecasts were saved before scoring. No optimizer was constructed for this
experiment, and no fitting, reserved payload access, engine operation, replay
download, bot deployment or subagent was used. Forecasting took 368.43 seconds.

The opt-in `TurnMovementAdapter` requires one instance per actor, `begin_turn`,
`predict` before `observe`, and `finish_turn` for every indexed own turn. Real
gaps require a fresh adapter. Its `dispatch` helper changes only a supplied
predicted movement destination; it is not a standalone action classifier.

Twenty contract-test executions passed, including inherited movement tests.
Parent verification checks every canonical row, saved decisions and metrics,
eligibility from strictly preceding roots, coordinate conversion and PRE support.
Fresh streaming inference is reproduced for one game of each engine version.
The exact counts and hashes are recorded in `verification.json`.

The next defensible experiment would train or calibrate the integration on
fitting-only full-action queries using the same deployment history interface,
then freeze it before evaluation. Selecting confidence thresholds or cases
from this DEV result would not demonstrate a transferable improvement. No such
fit or evaluation-guided routing is included here. Original category, reliability,
multi-seed and playing-strength requirements remain open.
