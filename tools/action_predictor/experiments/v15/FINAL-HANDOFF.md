# Completed movement specialization study

Neither new model improves the G00 movement control. No predictor is promoted.

| DEV complete commands | G00 | Single S00 | Mixture X00 |
| --- | ---: | ---: | ---: |
| Movement /2,362 | 1,318 | 1,283 | 1,276 |
| Blocked attempts /110 | 8 | 2 | 3 |
| Overall /14,439 | 11,510 | 11,469 | 11,463 |
| Observed joint NLL | .726556 | .735961 | .736393 |

The two allocated fits are complete, each with a fresh independent GPT-6.1 Sol
xhigh review. Results, all checkpoints and predictions, negative findings and
reproduction records are preserved. No repeat seeds or additional fit is justified.
Other original success targets remain unmet; one seed/five reused DEV groups do
not establish robustness. Historical B00 is retained, not relabeled untouched.

The sharper diagnosis is unsuccessful use of supported destinations, already
visible on natural TRAIN. X00's 1,086 movement errors consist of 235 wrong action
types and 851 wrong destinations after correct typing. Of those 851,595 have
neither current head mode correct and256 have a correct mode available. Among
these256,184 place it in the lower-weight head;72 favor the correct-mode head by
weight but still choose another destination. The complete probability shapes
matter. This is a correctly decoded normalized mixture, not A00's fallback veto.

The same problem exists on TRAIN:1,537 of4,261 available-mode direction-change
misses give the correct-mode head larger weight. Models fit continuation better
while losing changes. No specific capacity, optimization, compression, hidden
intent or information-insufficiency cause is established. Full coordinate support
and current head-mode union are distinct; union is neither achieved accuracy nor
an architecture ceiling. Exact scalar-gate MAP reachability is proposed, not run.
No new persistent observation-memory experiment was performed.

This addendum CORRECTS the broad command-preservation wording in the frozen
X00 report: action types, nonmovement conditional parameter paths, commands whose
PREDICTED families are nonmovement, and recorded-nonmovement category scores and
losses are unchanged. Already-wrong move/blocked forecasts change destinations on
77 recorded-nonmovement DEV rows and2,712 augmented-TRAIN rows. Saved scores and
negative conclusions are unaffected. See X00-final-review-addendum.json.

The original X00 raw log-probability tolerance check remains failed at one
unemitted blocked branch. The preserved diagnostic attributes it to frozen
encoder batch rounding; identical raw context gives bit-identical head outputs.
All179sampledtypes/74changed-family arguments match. This is not all-row raw
parity or production certification. No tolerance, checkpoint or model was changed.

Ward experimentation was explicitly discontinued by the user after three of
four fits. T01 remains absent and unrun; the old four-fit protocol is NOT claimed
complete. T00's outstanding reporting findings remain recorded at discontinuation.
Both reserved75-game partitions stayed sealed. No matches, simulations, replay
downloads, playing-bot changes or deployment. Shops43 remain unassessed strict
failures with absent purchase-argument likelihood; sparse categories/target-ID
ambiguity remain uncertified. Successful-move mask rejection is separate from
blocked-attempt rejection; full legality is unassessed.

PR11 is updated as DRAFT only, open and unmerged, without auto-merge or queue.
This is a reproducible negative-result research handoff, not a model release.
