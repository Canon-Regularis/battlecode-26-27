# Q01: variable waypoint projection has little measured influence

This frozen-checkpoint study separates geometry, predicted log scale, availability and constant offsets. It trains no model. All original14,439 DEV rows are retained, with predicted action choices for complete commands. Fixed-state shadow readouts and separately causal-refiltered variants are distinct diagnostics, not autonomous playing-strength evaluations.

**Numerical qualification:** the original2e-6 conditional-normalization criterion FAILED for both models. It remains failed. The first producer asserted before saving arrays, so its in-memory forecasts were lost; source/protocol/references/failure traces were preserved. Versioned recovery retained every primary forecast before checks and used independent float64 arithmetic to diagnose the issue. No primary probabilities, decoder, models, inputs, rows or benchmark success targets were changed.

References come only from all288,801 identity-verified natural TRAIN rows under original augmented traversal. Means are per model/component. Geometry stays zero without current position; log-scale references are stratified by current-position availability; the availability mean alters only its projection contribution, not real flags/masks. Learned bias remains in mean contrasts. These contrasts retain mean offsets and availability-dependent reference structure; they do not remove all goal information or every goal pathway.

## L01

Reference mean-projection discrepancy: 2.48e-09. Baseline integer arrays match the original archive exactly. All weights remain unchanged.

| Readout | Complete | Mode changes | Rescues/regressions | NLL difference | Move conditional/joint | Change joint | Common-wrong moves |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 12079 | 0 | 0/0 | +0.00000000 | 1437/1372 | 282 | 828 |
| fixed/geometry_mean | 12078 | 3 | 0/1 | +0.00003886 | 1437/1372 | 282 | 826 |
| fixed/uncertainty_mean | 12079 | 9 | 3/3 | +0.00005287 | 1436/1372 | 282 | 827 |
| fixed/availability_mean | 12078 | 1 | 0/1 | +0.00002816 | 1437/1372 | 282 | 828 |
| fixed/all_means | 12078 | 12 | 3/4 | +0.00011819 | 1436/1371 | 282 | 826 |
| fixed/bias_off | 12073 | 38 | 7/13 | +0.00156515 | 1436/1366 | 280 | 829 |
| fixed/projection_off | 12049 | 228 | 51/81 | +0.01420601 | 1443/1355 | 272 | 831 |
| refilter/geometry_mean | 12078 | 3 | 0/1 | +0.00003880 | 1437/1372 | 282 | 826 |
| refilter/uncertainty_mean | 12079 | 9 | 3/3 | +0.00005250 | 1436/1372 | 282 | 827 |
| refilter/availability_mean | 12078 | 1 | 0/1 | +0.00002816 | 1437/1372 | 282 | 828 |
| refilter/all_means | 12078 | 12 | 3/4 | +0.00011774 | 1436/1371 | 282 | 826 |
| refilter/bias_off | 12073 | 38 | 7/13 | +0.00156509 | 1436/1366 | 280 | 829 |
| refilter/projection_off | 12049 | 228 | 51/81 | +0.01419246 | 1443/1355 | 272 | 831 |

Fixed versus refiltered observed-mode differences: `{'geometry_mean': 0, 'uncertainty_mean': 0, 'availability_mean': 0, 'all_means': 0, 'bias_off': 0, 'projection_off': 0}`.

Independent float64 worst-case batches: 26 (duplicates across scopes possible), 0 semantic MAP mismatches; maximum observed-NLL discrepancy 6.74e-07. This is a bounded arithmetic check, not a full independent causal filter.

## L02

Reference mean-projection discrepancy: 5.23e-10. Baseline integer arrays match the original archive exactly. All weights remain unchanged.

| Readout | Complete | Mode changes | Rescues/regressions | NLL difference | Move conditional/joint | Change joint | Common-wrong moves |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 12064 | 0 | 0/0 | +0.00000000 | 1428/1365 | 273 | 867 |
| fixed/geometry_mean | 12065 | 6 | 2/1 | +0.00001821 | 1428/1365 | 273 | 865 |
| fixed/uncertainty_mean | 12068 | 18 | 8/4 | -0.00022145 | 1428/1365 | 272 | 867 |
| fixed/availability_mean | 12064 | 0 | 0/0 | +0.00000950 | 1428/1365 | 273 | 867 |
| fixed/all_means | 12067 | 21 | 7/4 | -0.00019005 | 1428/1364 | 272 | 866 |
| fixed/bias_off | 12062 | 33 | 9/11 | +0.00098751 | 1427/1361 | 269 | 868 |
| fixed/projection_off | 12054 | 223 | 53/63 | +0.01066141 | 1427/1350 | 263 | 871 |
| refilter/geometry_mean | 12065 | 6 | 2/1 | +0.00001854 | 1428/1365 | 273 | 865 |
| refilter/uncertainty_mean | 12068 | 18 | 8/4 | -0.00022015 | 1428/1365 | 272 | 867 |
| refilter/availability_mean | 12064 | 0 | 0/0 | +0.00000952 | 1428/1365 | 273 | 867 |
| refilter/all_means | 12067 | 21 | 7/4 | -0.00018855 | 1428/1364 | 272 | 866 |
| refilter/bias_off | 12062 | 33 | 9/11 | +0.00098823 | 1427/1361 | 269 | 868 |
| refilter/projection_off | 12053 | 222 | 52/63 | +0.01064775 | 1426/1350 | 263 | 871 |

Fixed versus refiltered observed-mode differences: `{'geometry_mean': 0, 'uncertainty_mean': 0, 'availability_mean': 0, 'all_means': 0, 'bias_off': 0, 'projection_off': 1}`.

Independent float64 worst-case batches: 26 (duplicates across scopes possible), 0 semantic MAP mismatches; maximum observed-NLL discrepancy 9.93e-07. This is a bounded arithmetic check, not a full independent causal filter.

## What this establishes

Geometry mean replacement changes only3/6 observed command modes in L01/L02; their correct movement counts remain1,372/1,365 and conditional destinations1,437/1,428. Mean conditional-movement TV is about.000371/.001366. This is weak current dependence, not literally zero probability influence or proof that better goal information could not help. Geometry may also be represented redundantly in other pathways.

Replacing all tested projection variations with their defined TRAIN references changes12/21 modes, net complete commands-1/+3. Removing learned bias alone changes38/33 modes, net-6/-2; removing the entire projection changes228/223 fixed-state modes, net-30/-10. These nonlinear contrasts are not additive causal fractions: do not attribute a percentage of the effect to bias, calibration or geometry. They support the importance of mean/pathway contributions while providing little evidence that variable waypoint geometry currently steers execution successfully.

Component distributions remain the dominant demonstrated movement limitation. Geometry neutralization leaves current mode unions and common-wrong counts nearly unchanged. Current reweighting bounds freeze each branch distributions and past state; they are oracle diagnostics, not achieved accuracy or architecture/data ceilings. Conditional movement supplies the recorded family only after forecasting for diagnosis. All primary complete-command predictions use predicted families and their actual required parameters.

The original normalization failures were not caused solely by padding: maxima also occur on valid decisions. Worst rows are recorded/predicted end actions, with hypothetical movement type log probability around-36.39/-34.44. Float32 subtraction in the derived conditional representation exhibits cancellation. Independent normalized float64 conditional mixtures have sum errors below1.6e-15, zero conditional-mode discrepancies across checked real move/blocked distributions, and maximum observed-family NLL discrepancy below1.2e-6. Worst full-batch complete-MAP checks also agree. This supports the primary counts within the older meaningful-NLL numerical contract, while the original tighter normalization criterion still fails. It is not evidence that this small numerical discrepancy explains the large imitation errors.

Every correctly typed spatial diagnostic coordinate matches the actual selected argument across all26 branches. No dominated/common-wrong component row is simultaneously marked primary-correct. The artifact-contract and numerical-case receipts retain the checks and qualifications.

Per-category PRF/confusion/false positives, all-true-family and correctly-typed parameters, category losses, unknown-position contexts, continuation/change metrics, target probability/rank, partial readiness and paired2,000 whole-group intervals are in the evaluation JSONs. All five DEV groups have been repeatedly reused after checkpoint selection; intervals are not untouched, multiplicity/selection adjusted or three-seed evidence. No contrast is selected as a replacement policy. Full counterfactual TRAIN scores were not computed, so this does not isolate a TRAIN/DEV generalization effect.

## Next question

A justified training hypothesis is whether dynamic learned-goal geometry becomes useful when supplied directly to candidate-conditioned execution, compared with an identical-capacity/head/initialization control receiving TRAIN-mean geometry. That would test the demonstrated weak injection path rather than another retention or auxiliary-weight variation. It must preserve causal goal inference, learn scores from demonstrations, avoid hand-designed strategies, retain probability-consistent decoding and original regression guards, and be registered/reviewed independently. It is proposed, not implemented or fitted; the fresh review should challenge it against target-quality and representation alternatives.

This study does not identify Fish intent, show observation sufficiency or certify learned strategic persistence. Future-position supervision may be an imperfect objective proxy; no contradiction or irreducibility is proven. Original category/macro/movement/NLL/targeting/three-seed goals remain unmet. All43DEV shops remain unavailable strict failures with absent argument likelihood. Sparse altar/teleport/submit, entity identity and full legality/calibration remain uncertified. Successful-move mask rejection and blocked-attempt diagnostics are separate.

Research continues automatically after fresh Sol6.1xhigh review and justified corrections. No optimizer, matches, replay downloads, reserved-partition access, playing-bot/runtime work or deployment occurred. Both75-game reservations remain sealed; PR11 staysDRAFT/open/unmerged/no-auto-merge/queue.
