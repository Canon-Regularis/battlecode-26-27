# Fitting-only optimizer-cadence probe

Astra medium recommended this separate diagnostic after the completed negative
memory experiment and fitting-only destination audit. It asks whether smaller
optimizer batches and more frequent updates improve this execution model at
identical row exposure. It does not isolate gradient noise, Adam moments or
cumulative weight decay from update frequency.

The immutable selection has 256 nonoverlapping 32-root windows, aligned with A's
existing eight-root resets. Hash-based selection and group round-robin used no
targets or losses. All 40 fitting groups are represented: 8,192 rows, 642 changes
and 677 continuations. Every command in those windows is retained. The loader
copies normalized inputs exactly, overriding only reset metadata at isolated
window starts. No tuning, assessment, original DEV or reserved payload is loaded.

Both arms load the same random A-initial weights and start fresh AdamW optimizers.
Both reset and detach recurrent state every eight roots. U00 accumulates four
eight-root segments, divides by 1,024 rows and updates once. U01 divides each
segment by 256 rows, completes backward/detachment/clipping/update, and only then
computes the next segment. Architecture, inputs, row order, learning rate 0.0003,
weight decay 0.01 and clipping threshold 5 are identical.

Each arm gets 16 passes and exactly 131,072 row presentations. U00 has 128 updates;
U01 has 512. Only final pass 16 is evaluated as the result. Initial evaluation is
a reference, and intermediate online loss never selects a checkpoint. The paired
budget is two hours with no extension or restart. Each arm runs separately with
fresh independent reviews before fitting and after each fit.

The fitting-only allocation gate requires at least +5 percentage points complete
changes, at least 0.15 nats lower change-coordinate NLL, lower balanced movement
joint NLL, continuation loss at most one point, full NLL increase at most 0.005,
and complete-command loss at most 0.2 points. Change-coordinate NLL must improve
after removing any one group. All categories, false positives, targeting, group
differences, probability decomposition and clipping frequency remain reported.

Passing only warrants a separately reviewed full-population experiment. It is
not generalization, strategy, playing-strength or promotion evidence. Historical
references, original category/reliability/90-percent/three-seed requirements and
data limitations remain. Prefit review must also cover the corrected V34 audit.
