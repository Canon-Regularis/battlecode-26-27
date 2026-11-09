# V43: automatic behavior segments and causal code prediction

Automatic segmentation and an experimental streaming predictor are implemented. No objective names, hand-labelled goal positions or hand-labelled boundaries are supplied. The algorithm discovers persistent behavior phases, but the first neural comparison **fails its movement/goal allocation test**. It does not establish useful strategic-objective discovery or justify deployment.

## What was built

A minimum-duration switching centroid model alternates exact dynamic-program sequence assignment with masked centroid updates. Its eight possible codes, two-turn minimum duration, change penalty of two and twelve hard-EM iterations are fixed design choices. The method is a small semi-Markov clustering model, not a reproduction of CompILE. There is no forced cut at an attack, ward, cast or recall, and the retrospective descriptors contain neither absolute positions nor signed movement directions.

Descriptors summarize complete own-turn action counts, walking amount and available changes in health, carried gems, gold and distances to known camps, enemies and altars. They describe behavior/outcomes without assigning strategic names. Nearest-entity changes can alter distances without movement, and some observations are unavailable. These are masked descriptive features, not verified rewards or intent.

The causal network uses the current full-resolution public map, current own/known entity fields, round number, explicit missing masks and the **completed previous turn's** descriptor. A GRU predicts a distribution over codes. Its expected code embedding conditions a categorical map-goal head and a conditional movement head. The inferred map goal can also feed A*. Offline code labels, current-turn action summaries and future endpoints never enter the forward interface.

## Data and discovery

The existing V42 split remains fixed: 32 fitting and eight evaluation groups, all previously exposed research data. There are eight selected nonoverlapping windows per group, each containing 32 actual consecutive own turns. Windows are selected by fixed identity hashes using cached-PRE availability, without consulting outcomes or code assignments. There are 8,192 fitting turns and 2,048 evaluation turns; only 2,945 and 699 have an observed query PRE. Missing turns remain rows, not stitched gaps. The query is the first nonadministrative decision in an own turn. This is a different population from prior root-action studies.

The first data attempt stopped when one group had no window with 16 available query PREs. R2 lowers only that availability threshold to eight while preserving groups, block lengths, hash ordering and explicit masks. The failed attempt remains preserved. An initial neural preflight then exposed observed shop/dead states without positions; it stopped before model/optimizer construction. The corrected encoder preserves their state and map without inventing coordinates. Its original empty attempt and protocol/discovery bindings remain preserved. There was no completed-fit repeat.

Discovery uses fitting groups only. Six codes are used on fitting data, forming 690 segments and 434 internal boundaries; median duration is nine own turns. Evaluation has 178 segments and 114 internal boundaries, again with a nine-turn median. One previously unused initialized prototype is selected on two evaluation turns, so seven evaluation codes occur; this is not a newly learned seventh objective. Administrative window edges are not discovered boundaries.

The fitted profiles include a movement/recall/cancel-heavy code, an attack-heavy code, two blocked-action-heavy codes, a travel/priority-heavy code and a low-activity code. These are posthoc descriptions, not training labels. They do not distinguish goals such as which camp to farm or which altar to approach. In fitting data, 262 of 277 ward turns, 456 of 477 cast-0 turns, and 494 of 540 cast-1 turns have no following code change. Thus incidental events are not automatic cuts.

An endpoint target is the observed PRE position at the beginning of the following learned segment. The final segment is right-censored; unavailable/unreachable endpoints remain masked. This yields only **369 fitting and 98 evaluation endpoint queries**. Many discovered boundaries have no cached observation. A segment endpoint is still an inferred behavioral transition, not verified goal completion.

## Matched neural comparison

S00 and S01 have identical 45,762-parameter architectures, initial tensors, data, six sampler schedules, goal/movement objectives and checkpoint opportunities. Both use the same learned endpoint labels and both predict soft codes for their decoder. Only S01 receives the additional code-classification loss (weight 0.2). This tests teaching the discovered code against an otherwise identical model; it does not compare learned boundaries against fixed boundaries.

Each arm completes 1,536 updates and 49,152 turn presentations. Only final pass six is evaluated. S00 takes 92.542 seconds and S01 95.854 seconds, below their frozen 1,200-second caps. All 31 parameter tensors change and neither run clips a gradient. Fit-only numeric field dictionaries omit 24 evaluation field occurrences; none are omitted on fitting rows.

| Evaluation metric | S00 without code supervision | S01 with code supervision |
| --- | ---: | ---: |
| Conditional first-movement correctness / 513 | 109 (21.25%) | 112 (21.83%) |
| Movement NLL | 1.788070 | 1.782698 |
| Endpoint within two tiles / 98 | 52 (53.06%) | 51 (52.04%) |
| Exact endpoint / 98 | 15 (15.31%) | 17 (17.35%) |
| Mean endpoint Chebyshev error | 3.2143 | 3.3061 |
| Predicted endpoint + A* next-step matches / 513 | 6 (1.17%) | 10 (1.95%) |

The required three-point movement gain, three-point endpoint-proximity gain and lower endpoint error all fail. Only the movement-NLL guard passes. A slightly higher exact-endpoint count does not override the conjunction. Predicting the current position already achieves 53.06% endpoint-within-two accuracy and 3.1837 mean error. Nearest-altar A* matches 31.58% of these movement queries. The new neural endpoints therefore do not provide useful movement guidance.

The causal neural classifier selects **code 0 on all 699 evaluation queries**. Its 64.81% code accuracy equals the fitting-majority baseline; balanced recall over the seven observed evaluation codes is only 14.29%. On fitting queries it selects code 0 on 2,943 rows and code 4 on two. The reported overall accuracy must not be presented as successful objective prediction. Permuting only the code embeddings leaves evaluation goal choices unchanged and slightly changes movement results; this diagnostic does not rescue the failed comparison or prove a unique failure mechanism.

## Causal persistence diagnostic

A fitting-only check found that matching the completed previous-turn descriptor to a frozen prototype can recover multiple codes. A separate rule was then frozen before its evaluation calculation: forecast that the nearest previous-turn code persists; use the fitting-majority code when history is unavailable. It uses no new optimization and does not change S00/S01, their checkpoints or their gates.

On all 699 evaluation queries this postfit diagnostic matches the frozen hindsight code on **510 rows (72.96%)**, with **43.55% balanced recall**, versus the majority baseline's 64.81%/14.29%. Rare codes remain poorly predicted. The rule retains all eight frozen prototypes, including two unused fitting prototypes; spurious assignments to those codes remain possible.

This provides evidence that the available causal history contains some information about the discovered phases. It is a postfit diagnostic on preexposed groups, not an independently confirmed improvement, verified objective accuracy or measured goal/movement benefit. No replacement was selected from this diagnostic.

## Verification, interface and limits

Twelve distinct focused tests pass: dynamic programming against exhaustive enumeration, minimum duration, incidental-event robustness, recovery of a sustained synthetic change, nonincreasing hard-EM objective, missing-outcome handling, future/target perturbation invariance, streaming/batch agreement, endpoint censoring, supported normalized losses with finite gradients, position-unavailable handling, actor reset and past-only prototype inference (some tests cover multiple contracts).

Parent verification reproduces the complete discovery fit, every saved code and endpoint, both initial states, all schedules and optimizer step counts, and all **3,644 observed-query forecasts per arm** with exact saved losses and summaries. Streaming inference reproduces one full evaluation window. Source/input/checkpoint hashes are checked. Verification performs no optimizer updates. No subagents or delegated reviews were launched, as requested.

A separate bounded source probe reconstructs all 512 turns in 16 selected windows from two games, covering both engine versions. It checks hash-based window selection, actual actor chronology, current PRE parity, command counts, descriptors and past-only history boundaries. Full-corpus source integrity relies on the bound hashes and assembly checks; this probe is not a full replay revalidation.

`behavior_segments/predictor.py` exposes the neural streaming interface; `persistence.forecast` exposes the separate past-only diagnostic. Neither is enabled in the playing bot. This first implementation demonstrates automatic behavior grouping and a causal prototype forecast, but it does not demonstrate a useful learned strategic-goal model. The immediate empirical problems are the neural classifier's majority-code collapse, sparse endpoint observations, and endpoints that often provide no advantage over staying at the current position.

One seed, availability-selected windows, observed prior commands, administrative resets, overlapping endpoint targets, previously exposed groups and unverified intent/outcomes limit interpretation. Historical G00/L02/JP02, category-90%, reliability and three-seed requirements remain unmet. No reserved partitions, engine runs, replay downloads or bot/runtime changes were used.
