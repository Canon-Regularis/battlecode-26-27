# V72 - ranking-sensitive readout weight refit

The targeted64-weight update failed fitting-game validation. Both the likelihood-only control and ranking treatment select **epoch0**, retaining V70's exact original full-model weights. Both therefore remain311/513 evaluation movements; direct V59 remains318/513. There is no new improvement or promotion.

## Weight intervention

The complete V70 feature extractor and goal inputs stay frozen. Only its64 final output weights can train. The common scalar output bias stays fixed because it cancels in softmax. The control minimizes mean movement cross-entropy plus0.1 times the squared distance from its starting readout. The treatment adds mean positive margin loss `relu(0.25 + highest_supported_wrong_score - gold_score)`. Singleton supports contribute zero margin loss. No new parameters or runtime branch is introduced.

Both arms use matching V70 goal checkpoints, identical initial readouts, all12,318fitting movement examples, sampler seed72001, Adam lr0.003 with no weight decay, batch128, clip5, eight passes and checkpoints0/4/8. Four whole-game fitting folds choose on the original1,997held movements. Full refits at the selected epoch0 perform no updates. Evaluation never selects a candidate.

| Held fitting movement correctness | Initial | Pass4 | Pass8 |
| --- | ---: | ---: | ---: |
| Likelihood-only |1246|1242|1243|
| Ranking-sensitive |1246|1222|1215|

The ranking treatment changes the readout but worsens held decisions and NLL. This rejects this loss, regularization and update budget; it does not establish that every ranking loss fails or that more training would help. Completed fold weights remain archived rather than substituted after seeing evaluation.

## Verification and limitations

Parent verification reconstructs24fold measurements, sample schedules/RNG, optimizer accounting, frozen-weight preservation, selected weights, forecast summaries and streaming behavior. Both runtime arms preserve V70 exactly at their selected endpoint. Focused tests check64trainable parameters, finite derivatives, the positive-margin arithmetic and singleton support. No subagents were used.

Two small accounting details are explicit. Cached readout evaluation adds the common bias in a different floating-point order than the full network; initial NLL sums differ by about2.5e-6 while predictions and selected full-model weights match. The reused selector additionally imposes NLL<=epoch0+0.01, stricter than the declared direct-reference guard. Recomputing selection with only the declared guards still selects epoch0 in both arms; see `selection-clarification.json`. No training, results or frozen sources were altered.

Opt-in runtime: `ReadoutSharedPlanner(arm='ranking')` or `arm='likelihood'`. Existing stronger direct weights remain the reference. Reused research games, one seed, inherited fitting exposure, observed past commands and in-sample training-goal predictions remain material limits. These tests do not demonstrate autonomous strategy or playing strength.
