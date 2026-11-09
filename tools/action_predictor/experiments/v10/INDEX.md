# V10 learned algorithmic command prediction

Latest non-fitting work: [C01/C02 TRAIN support report](C01-C02-REPORT.md) and [ranked plan r2](ranked-plan-r2.json). C02covers41.49%blocked attempts and81.00%move commands on TRAIN; its full category gate still fails. No further fit or DEVcandidateevaluation is allocated. These are oracle support measurements, not achieved predictions; all initial pilots/results remain below.

Post-A01 review corrections are authoritative in [A01-review-corrections.json](A01-review-corrections.json) and [response](A01-review-response.md). They replace the original unused-field priority errors, D00 change count and A01 reproduction commands without overwriting historical reports. D00 changes1052semantic commands; its probability/confidence describes the modeled observed representation including a marginalized shop bucket, not complete purchase-command probability. The posthoc matched G00probability control gets11950strict successes; D00's additional gain is89. Direct paired A01–A00 strict differences are negative; macro differences remain uncertain. The review reproduced all TRAIN/DEV descriptors, weights and commands; no promotion or repeats.

This phase asks whether executable algorithm hypotheses explain recorded Fish commands and whether a causal learner can select them. No Fish source or internal intent has been recovered. These are replay command predictions, not playing strength or strategy similarity.

Both reserved partitions (75new-validation games/15groups and75final-test games/15groups) remain sealed. Every original DEV row is retained, including43shop strict failures with unavailable arguments. Altar/teleport support2each and submit22cannot certify reliability. Historical V4–V9 and unfinished frequency preparation are preserved.

## Frozen coverage before selection

C00 has31slots:5movement objectives x3planners/ties,9combat target ranks,2ward placements,1submit target,4utility commands. Candidate construction consumes personal PRE/public geometry, emits commands, and abstains when unavailable. No destination enumeration, hidden entities, IDs or duplicated move/blocked outcomes. Engine-derived historical movement masks constrain emitted move steps; terrain fields are unverified route hypotheses, not engine simulations. C00 has no latent goal persistence.

| Oracle coverage | TRAIN movement | DEV movement | DEV overall |
|---|---:|---:|---:|
| Terrain-field family |58.30%|55.88%|83.37%|
| Geometric control |68.42%|67.44%|85.26%|

The geometric library was selected using TRAIN before inspecting DEV coverage. Equal nominal slot counts do not isolate a pathfinding effect because output diversity/ties differ. Distinct output distributions, abstentions, slot match counts and unexplained families are in C00-train.json/C00-validation.json. These are oracle diagnostics, never achieved predictor accuracy. Blocked destination-only matches are separately reported and do not count as strict coverage.

## Learned predictions, all14439 DEV rows

| Predictor | Complete commands | Accuracy | Macro F1 | Observed joint NLL | Move joint |
|---|---:|---:|---:|---:|---:|
| G00 retained baseline |11510|79.7147%|.632394|.726556|1318/2362|
| A00 global slot selector |11622|80.4903%|.640715|.681311|1330/2362|
| A01 shared candidate scorer |11568|80.1164%|.638344|.690391|1337/2362|
| D00 no-fit bounded decoder diagnostic |12039|83.3784%|.613920|.681311|1360/2362|

A00 marginalizes all exact matching candidate explanations plus stochastic G00 fallback likelihood; it does not manufacture intent labels. Action selection/fallback routing are trained. The original hard decoder compares equivalent point-command weight with opaque fallback weight and is explicitly not mixture command MAP. A00 round17of23 is selected by the original minimum full-DEV observed NLL rule (.0001improvement,patience6,max35).

A00 fixes135G00errors and introduces23. Recall contributes98/112net; excluding recall, NLL worsens. Paired2000whole-group resamples (seed20261106) give an accuracy-gain interval of+.609to+.912percentagepoints, conditional on selected checkpoint and5reusedgroups. This is not selection-adjusted, untouched or3seed confirmation. Ward and both casts regress. Only135of1628library-covered G00errors are fixed.

A01 changes the inductive bias to shared candidate-conditioned scoring with44PRE geometry/action/objective/tie descriptors. It also uses a32-dimensional shared context instead of A00's64-dimensional global hidden layer, so this is a shared scorer architecture hypothesis, not a pure descriptor ablation. Loss, support, sampling, seed, history, optimizer, fallback and hard decoder remain fixed. Round10of16 is selected. It loses54DEVcommands versus A00, with lower TRAIN accuracy and worse TRAIN/DEVNLL. No repeat seeds allocated.

D00 holds A00 fixed and ranks actual mixture probabilities over C00 point commands plus the original G00hard forecast. This is bounded command-set MAP, not global MAP, particularly priority support. Its accuracy gain coincides with macro regression, reduced cast/priority success and zero correct wards; it is not promoted and did not change A01's decoder prospectively.

All original targets remain binding and unmet:>=90%completecommand in every supportedcategory,macroF1>=.65,movement>=.6520745131,>=10%lower observedjointNLL against relevant strongest baselines,attack/cast regressionguard. Missing shop argument likelihood is absent, not secretly correct. True-family argument accuracy is unavailable for this joint-only decoder; correctly typed parameter performance and type/joint false positives remain separate. Ambiguous entity-coordinate matches do not certify exact entity identity.

## Evidence and reproducibility

- A00-review.md contains the fresh requested GPT-6.1Solxhigh review; A00-review-response.md maps findings to evidence/deferred work.
- A00/A01.json retain full TRAIN/DEV categories, confusion, context results and every epoch trace. All checkpoints/predictions local under .cambc/action-predictor/v10/runs/{A00,A01}.
- A00/A01-analysis.json add paired context/category comparisons, matched overrides, support ceilings, unique rescues, partial legality and priority diagnostics. Full engine legality remains unassessed. Blocked forecast mask rejection is not an illegal successful move.
- A00/A01-causal-roundtrip.json rebuild382/386cases respectively across25games, both engines, missing position/history and both routes. Raw PRE/history/features/candidates/G00fallback/selector/final command parity passes; maxweight discrepancies7.75e-7/4.18e-7. A01also verifies candidate descriptors. No replay archives decoded or game actions simulated.
- New serving uses an explicit PRE-only supplement allowlist. Frozen C00 originally passed a broader row containing unused transaction labels; its stronger receipt wording is qualified in the review response. No such field was read by the frozen emitter.
- Completion addenda hash predictions/checkpoints and commands. Actual serving costs exclude initialization/history replay and do not establish production latency.

Run from repository root with .venv-action-predictor/Scripts/python.exe -m tools.action_predictor.<module>. Modules:algorithmic.study train,algorithmic.study validation,algorithmic_fit,algorithmic_verify,algorithmic_roundtrip,algorithmic_analysis A00,algorithmic_decoder,algorithmic_conditioned,algorithmic_conditioned_roundtrip,algorithmic_analysis A01. Completed fit/cache commands intentionally refuse overwrite; inspect immutable receipts before reuse. Initial failed C00schema assumption and its old plan are retained.

## Ranked next work

1. Fresh A01postfitSolxhighreview, address concrete findings; no repeat seeds under failed trigger. Update existing DRAFT PR11 only.
2. TRAIN-only C01 support development: ground-target casts, meaningful causal integer priority proposals, ward placement/availability, position-independent utility commands, and attempted blocked movement with explicit outcome forecast. Verify pinned historical semantics; no all-cell/all-outcomes enumeration. Before DEV or a new fit, freeze revised library/source, comparable-size control, per-category support criteria and a new justified budget separately from original success targets.
3. Candidate-conditioned objective/state inputs and exact bounded decoder can be revisited as separate hypotheses; A01failure does not establish all such scorers fail. Full action distribution learning must address recall/ward, priority and wrong types.
4. Persistent goals through a forward causal filter over actual personal evidence, preserving gaps/unavailable memory. No retrospective smoothing or sampled-turn stitching. Separate goal choice, route cost, ties, replanning and persistence where practical.

The original two V10pilots are spent. Frozen negative results remain useful evidence; no general algorithmic exhaustion claim. No matches, downloads, playing-bot edits, deployment, default-branch push or merge.
