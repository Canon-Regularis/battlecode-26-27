# P00: existing-representation placement specialist — negative first fit

One of the four planned fits is complete. P01, T00 and T01 have not run. The
required fresh Sol xhigh review follows this checkpoint; no model is promoted
or repeated. This is not the completed four-arm experiment.

P00 trains an independent21,882-parameter ward-only tile scorer using the frozen
128-dimensional M01 context and original20 tile features. Richer feature blocks
are zeroed; P01 will enable them in the same architecture. Every10,842 TRAIN
ward destination and all112 DEV ward destinations are in the historical-range
candidate mask. No example was dropped. The selected checkpoint is18of24rounds,
using the original .0001 full-DEV-NLL improvement/patience6 rule. Round23's smaller
absolute NLL does not clear that minimum improvement; it is not substituted.

| Conditional placement diagnostic | Existing head | P00 |
|---|---:|---:|
| Augmented TRAIN | 2,274 / 10,842 | 2,247 / 10,842 |
| Natural TRAIN | 449 / 2,192 | 445 / 2,192 |
| Original DEV | 24 / 112 | 25 / 112 |

DEV has4rescues/3regressions; paired whole-group95% accuracy-difference interval
is **-5.49 to +4.73 percentage points**. The uniform valid-tile tie control and
the masked existing head also get24/112; TRAIN-frequency offset prior gets10/112.
These are given-ward diagnostics, not deployable joint accuracy.

With action choices exactly unchanged, complete primary ward predictions remain
**7/112**, ward typeTP35, typeFP282, recall-to-ward257. Overall strict accuracy
remains11,510/14,439 and macro F1 .6323935. Observed joint NLL changes from
.7265557 to .7261831; only true-ward argument likelihood changes. No nonward action
or argument is modified. The separate jointMAP comparison changes overall
11,953→11,956, while ward joint remains1/112; it is not selected as a replacement
for the prespecified primary comparison.

This is not primarily a TRAIN-versus-DEV failure: fitted TRAIN exact placement
does not improve. A bounded no-fit TRAIN probe shuffling only the frozen128context
reduces correct placements2,247→2,141 and increases conditional NLL2.574→2.680.
The fitted model therefore uses context, but this does not prove that it uses
all useful information or that the current architecture can fit the full task.
Representation compression, optimization/capacity and missing ward-specific
observations remain separable hypotheses. This result does not exhaust neural
specialization. P01 tests the already-prespecified richer representation.

Raw serving reproduces **408cases/25games/both engines**: raw PRE/tile features,
candidate masks and both decoders' commands exact. Frozen neural context differs
at most5.73e-6 (batch1 versus cached batch); command log probability at most4.53e-6.
Only neural context gets a1e-5 tolerance; raw features/commands remain exact.
Initial stricter-tolerance failure and reporting-only calibration bug are retained
as preflight receipts. No checkpoint or archived prediction was changed.

See P00.json, P00-placement-diagnosis.json, P00-head-evaluation.json,
P00-head-causal-roundtrip.json and P00-completion.json. All43 shops remain strict
unassessed failures; sparse categories and ambiguous entity identities remain
uncertified. Both reserved partitions remain sealed; no matches, proposed-action
simulations, downloads or playing-bot edits occurred.
