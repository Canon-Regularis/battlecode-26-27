# V41: previous-vector dropout

D01 fails the frozen allocation conditions against both Z01 and R00. Training-only inverted dropout on movement grid channels 18:20 does not establish a movement improvement. It is not promoted.

The completed run uses fresh neutral-bias initialization, unchanged explicit history, eight fixed passes, 272 optimizer updates and 277,760 row presentations. A separate seed-270041 mask generator makes 43,776 movement-row draws, dropping 21,896. Evaluation uses clean inputs and consumes no mask draws. Final pass eight is the only selected endpoint.

Against Z01, D01 gains 79 complete commands but loses 55 moves, five direction changes and 50 continuations. Complete counts are 26,834 commands, 2,900 moves, 271 changes and 2,629 continuations. Full-command NLL worsens from 1.236638988 to 1.251673043. Change-coordinate NLL improves to 1.893405185, but within-alternative NLL worsens to 1.581566698. Lower repetition confidence did not fix alternative-destination ordering. Seven guards fail against Z01 and five against R00.

The saved parent verification reproduces all initial/final command and movement forecasts, summaries and comparisons, matched initialization, all schedules and mask RNG states, exact accounting, and finite optimizer/tensor changes. Thirty contract tests passed in the preceding work. The fit took 163.314179 seconds. No subagent approval is claimed; the user requested continued parent-only work.

This remains one fitting-only configuration and seed. It supports neither generalization nor recovered strategy. The subsequent V42 work follows the user's request to build a separate replay-inferred goal evaluator, full-map goal model and A* movement stage.
