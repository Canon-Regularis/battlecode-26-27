# Current research after the movement pair

G00 remains the strongest strict-accuracy development checkpoint:11,510/14,439 (79.7147%). G01 has11,505 (79.6800%), five fewer; it fixes70control errors and introduces75. It selects epoch2 of8 by the unchanged joint-loss rule, while G00 selects epoch1 of7. All epochs and raw predictions remain preserved. This is not a certified replacement or untouched/three-seed result.

G01 fails its prospectively fixed continuation and repeat guards. No identical repeats are triggered. Whole-group G01-minus-G00 strict-gain interval is -0.206 to +0.126percentagepoints, conditional on selected checkpoints/five reused groups.

| Model | Joint moves /2,362 | Exact continuing /1,198 | Exact changing /1,158 | Joint blocked /110 | Full observed NLL |
|---|---:|---:|---:|---:|---:|
| P05 | 1,287 | 1,124 | 277 | 1 | 0.730903 |
| G00 unrestricted control | 1,318 | 1,120 | 311 | 8 | 0.726556 |
| G01 direction-specialized | 1,311 | 1,103 | 325 | 10 | 0.726171 |

The specialized package gains14changing destinations but loses17continuing destinations versus G00. It loses16complete continuing moves and gains9complete changing moves, for7fewer joint moves. Two extra blocked successes reduce the overall deficit to five. All classifier, ability, ward and priority results remain exactly unchanged. This demonstrates a failed tradeoff for this package, not that every specialized model is impossible.

Training change exactness is only37.07% versus development28.07%; continuation is91.93%/92.07%. Gate accuracy is78.78%TRAIN versus74.36%DEV, below control's75.21%DEV despite lower BCE. The gate and destination representation remain limited. Primary training loss falls while development loss worsens after epoch2.

## What was tested

Both arms use the same two warm-started trainable GRU movement experts, fixed classifier/other parameter references, rows, normalization, initial weights, sampler and checkpoint rule. G01 adds disjoint direction supports and0.05gate BCE. On eligible moves the primary likelihood ALREADY decomposes into gateBCE plus within-partition destinationNLL; the extra term raises the gate coefficient1.00to1.05. This is an architecture/support/optimization/weighting package, not an isolated auxiliary-task claim. No next-direction label enters inference, and there is no oracle routing. Startup, blocked and all43unassessed shop rows remain retained.

## Evidence and corrected cost accounting

- [Complete metrics](G01.json), [report](G01-REPORT.md), [per-category PRF](G01-per-category.csv), [confusion](G01-confusion.csv), [guards and uncertainty](G01-analysis.json).
- [Matched effects and initialization/compute accounting](G01-matched-comparison.json), [per-category changes](G01-matched-categories.csv), [gate/destination decomposition](G01-loss-decomposition.json). Reconstructed initial states match; seven shared epochs' saved shuffle RNG states match. Different selected/stopped epochs are disclosed.
- [Saved-array and causal serving proof](G01-causal-roundtrip.json): all8development arrays reproduce;95rawPREcases/25games,26proposedmovementcases; single-row/batched movement probability discrepancy1.43e-6. No old495-game extraction gate repeated.
- [ACTUAL P05 serving](P05-actual-serving.json), [ACTUAL G00](G00-actual-serving.json), [ACTUAL G01](G01-actual-serving.json). These time actual predictor.distributions plus priority decode on prepared inputs. Teacher-coordinate calls are1forP05 and2onmovement forG00/G01. The old G00-serving.json is preserved as a REDUCED-KERNEL measurement that skipped one call; it does not describe the full current implementation. Predictions did not change.

Actual prepared-input mean/median/p95milliseconds: P05 0.694/0.638/0.947; G00 1.098/0.663/2.681; G01 1.116/0.673/2.836. Feature construction is excluded; total process memory includes Torch/prepared data. Similar medians conceal slower movement-tail cost. This is not full production latency.

G00's completed fit/scoring review is approved; G01's fresh completed-fit review is pending. See [G00](INDEX-G00.md) and [historical entity pair](INDEX.md); those indices are historical snapshots, with current E01 checkpoint/command addenda linked from G00.

## Next evidence-based work

Wrong action types account for1,627/2,934failures. Perfect parameters under this frozen classifier still cap strict accuracy at88.44%; another prolonged frozen-classifier sequence cannot achieve the objective. Next is a bounded, controlled classifier sampling/loss comparison, preserving G00 parameter predictions and exposing recall/ward false positives, rare successes, priority action selection and calibration. Candidate-conditioned geometry/entity representations and matched full-observation GRU-versus-transformer studies remain distinct hypotheses. Do not retune the failed gate weights or thresholds to claim success.

All original90%-per-category,macroF1>=0.65,movement+10points,loss-10%,targeting and three-seed requirements remain binding. Shops remain unassessed; altar/teleport each have2examples and are uncertified. Both75-game reserved partitions remain sealed. No matches, downloads, playing-bot changes or deployment. PR11 stays draft/unmerged, auto-merge and merge queues disabled.
