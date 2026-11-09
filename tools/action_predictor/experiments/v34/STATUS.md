# Fitting-only movement probability diagnosis

The independently reviewed V33 horizon study is complete and negative. This
diagnostic makes no optimizer updates. It uses only A's initial checkpoint and
its already selected round-12 checkpoint, replaying all 65,465 fitting rows to
measure the 10,400 recorded movements. It does not load tuning or assessment.

The final artifact is `diagnostic-r2.json`. On 5,032 fitting direction changes,
the trained movement conditional gets 410 destinations correct and repeats the
previous movement vector on 3,331 rows. All recorded change destinations lie
inside the current movement support mask. The median gold-destination rank is
four; 2,429 gold destinations rank in the top three.

The probability identity separating an exact repeat from every other outcome
decomposes change coordinate NLL 2.671297 into group NLL 0.786561 and within-group
NLL 1.884735. These are not separately trained heads. The complement includes
other tiles and both special buckets. A diagnostic that forcibly excludes the
previous vector gets 1,079/5,032 change destinations correct; that uses oracle
knowledge and is neither available policy accuracy nor a complete ceiling.

Across 10,381 movement rows with a known previous vector, the probability of
not repeating has fitting AUC 0.731844 and Brier score 0.211121. This demonstrates
some discrimination in this fitting set, not strategic intent or transferable
change detection. Exact command MAP can still choose the previous vector when
the remaining probability is spread among several alternatives. Merely changing
the decoder or forcing a turn would trade errors and needs its own evaluation.

The first attempt preserved its raw forecasts but stopped at an overly strict
1e-6 likelihood comparison between all-row and movement-only float32 batches.
Nine rows exceeded it; the maximum difference was 3.251107e-6. The corrected
diagnostic records the original observed-loss path separately: it reproduces
the archived selected losses exactly, and both attempts' original forecast
arrays are byte-equivalent as arrays. All conditional destinations match.
`diagnostic-attempt-1.json` preserves the failure and bindings. No fit was rerun.

Three focused tests pass. Parent checks independently reproduced AUC using
positive/negative pair counts and verified raw archive hashes and first/second-attempt forecast
equality. Neither the group decomposition nor missing-frame strata establish
causal shortcuts, observation sufficiency or legality. The next intervention
must address execution learning with a concrete hypothesis; no new fit or
promotion is authorized by these diagnostic scores alone.
