# T00: simpler ward-action specialist

T00 is a negative ward-selection result. The selected model predicts no wards
on DEV. It improves aggregate accuracy and likelihood while discarding the ward
category. No promotion or repeat seeds are justified; T01 remains unrun.

The frozen binary network has41345parameters and uses frozen context plus base
personal-PRE/action history; the additional71ward-specific features are zeroed.
All433071eligible TRAIN rows were used, with TRAIN-only class weights matching
natural ward prior2192/288801=.0075900. This corrects class marginals, not unknown
within-class augmentation effects. Conditional heads remain exactly unchanged.
It selected round3/9 under fullDEV jointNLL .0001/patience6:2538selected and
7614completed updates. The31.722-second measured interval starts after loading
and normalization and includes roundDEV inference, saves and final inference;
it is not total preparation time or pure optimization. Every checkpoint retained.

| Primary DEV metric | G00 control | T00 |
| --- | ---: | ---: |
| Complete correct /14439 | 11510 | 11738 |
| Macro F1 | .632394 | .622921 |
| Observed joint NLL | .726556 | .702711 |
| Ward type TP /112 | 35 | 0 |
| Ward type FP | 282 | 0 |
| Recall-to-ward errors | 257 | 0 |
| Complete ward /112 | 7 | 0 |
| Conditional ward placement /112 | 24 | 24 |

Ward precision is undefined with zero forecasts; recall/F1 are zero. Correctly
typed placement is undefined, not zero. The primary complete changes are235rescues
and7regressions: recall+233,end+1,priority+1,ward-7; all other category joint counts
are unchanged. All true-family parameter predictions remain unchanged. Paired
whole-group accuracy gain interval is[+1.401,+1.728] percentage points, macroF1
[-.012651,-.005916], joint NLL[-.029271,-.018631]. These are selected-checkpoint
results on five repeatedly reused groups, not untouched or three-seed evidence.

This cannot be called recovered ward selection. A clearly labeled POSTHOC
constant natural-TRAIN-prior control with identical normalized probability
integration emits exactly the same14439DEV commands. Its NLL is.717335 versus
T00 .702711, so learned probabilities improve this loss even though their hard
forecasts add no benefit over blanket suppression. The diagnostic plan preceded
its calculation; it is not a new fitted treatment or prospectively validated
candidate. T00-prior-control.json retains all denominators and TRAIN comparisons.

Fixed-output ranking diagnostics show some learned discrimination: DEV average
precision .114989 versus G00 .086463; AUROC .946052 versus .941093. NaturalTRAIN
AP .152698 and AUROC .962373 are in-sample, not fresh group folds. Mean DEV ward
probability on true wards is.078365 (median.064345,max.292529), versus.029150 on
recalls. Weak high-confidence separation, low natural prevalence, loss weighting
and limited representation remain plausible contributors; no single one is
causally isolated by this fit. There was no threshold sweep or posterior tuning.
The actual15way decoder differs from the separate fixed.5binary diagnostic.

Natural TRAIN predicts3wards (2TP,1FP,1complete/2192); augmented TRAIN predicts17
(16TP,1FP,4complete/10842). Thus poor hard ward selection is already present on
training examples, not merely a DEV failure. Aggregate falling TRAIN loss does
not establish successful rare-category fitting or observations' sufficiency.
The existing24/112placement ceiling would still prevent B from meeting90% even
with perfect typing. Rich-input T01 remains the final frozen fit, not permission
to add capacity/loss variants or expand beyond the four-fit budget.

Secondary predeclared jointMAP obtains11959complete/14439 versus11953control,
macro.618103 and0complete wards. It is reported separately, never selected as a
replacement for primary after results. All modes use the same normalized
observed distribution. Shops43retain unavailable original arguments and remain
strict failures; sparsealtar/teleport/submit and entity identity uncertified.

Read-only serving parity passed380rawpersonalPRE cases across25games/bothengines,
exact commands for both decoders and rawfeatures/tiles/masks. Frozencontextmax
5.722e-6, commandlogPmax4.278e-6 within existing tolerance. No unchanged full audit,
new extraction, matches, proposed-action simulations or reserved access occurred.

T00-completion-v3-T00-only.json binds model/checkpoints, predictions, comparator
archives, serving and reporting. T00-typing-diagnosis.json independently binds its
source, fixed-output ranking/calibration reports and reproduction command;
T00-prior-control{,-plan}.json binds the posthoc diagnostic. Context all-family
metrics, augmented/naturalTRAIN andDEV support/group concentration are in
T00-only-reporting-addendum.json, with explicit undefinedF1null corrections in
v3manifest. Original receipts remain immutable. Fresh Solxhigh review is next.
