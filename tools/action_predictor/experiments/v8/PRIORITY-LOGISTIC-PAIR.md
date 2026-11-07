# Priority logistic pair: metric clarification and measured results

- Exact parameter prediction supplied the recorded true action family, over ALL recorded rows in that category, including wrong predicted action types. Not conditioned on correct action classification.
- Action-TYPE classification only, not full-command precision/recall/F1.
- Correct predicted action type AND all required exact recorded parameters; unavailable shop arguments fail.
- Observed action plus observed conditional parameter negative log likelihood; purchase-argument likelihood is unassessed.
- Null conditional parameter accuracy means not applicable; shop null means unavailable arguments.
- 2000 paired resamples of five whole reused development groups, conditional on checkpoint selection; not selection-adjusted, three-seed or untouched-test confirmation.

| Model | Exact priority /576 | Joint priority /576 | Priority NLL | Mean / median / maximum integer error | Full observed joint NLL |
|---|---:|---:|---:|---:|---:|
| M01 | 13 | 10 | 7.08824 | 355.20 / 514 / 822 | 0.87280 |
| P01 | 22 | 15 | 6.75922 | 355.13 / 512 / 823 | 0.85967 |
| P02 | 15 | 11 | 6.78100 | 354.90 / 517 / 827 | 0.86054 |

P02 versus P01 isolates restored inputs within this logistic head. Comparisons against M01 also include head refitting. All action and spatial paths remain frozen. The fixed priority action decisions cap joint correctness at 343/576 (59.55%).

No category-wise goal or three-seed success is established. All 43 shops remain unassessed strict failures. Original category supports and regression guards remain unchanged. Altar and teleport each have only two development examples.

The immutable P01/P02 reports retain category PRF, joint counts, confusion matrices, top-k destinations, destination errors, history/unseen-value strata and legality coverage. Historical partial flags remain 0 successful-move mask rejections, 92 blocked-forecast rejections and 17 other flags; full engine legality is unknown.

The paired uncertainty, absolute-error summaries, exact hashes and source snapshot are preserved alongside this report. The original reports remain unchanged. Both reserved 75-game partitions remain sealed.
