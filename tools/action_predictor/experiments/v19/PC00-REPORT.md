# PC00: actual P05 can fit128priority examples; fine-tuning harms controls

One conditional value-head capacity diagnostic uses the actual retained P05 architecture, warm weights, normalized frozen M01 contexts,39recovered causal priority channels and exact int64 anchors. No action selector or full-policy model is replaced.

| Cohort | Exact initially | Exact final | NLL initially | NLL final |
| --- | ---: | ---: | ---: | ---: |
| fit | 34/128 | 128/128 | 2.894059 | 0.000878 |
| same_fit_groups | 25/128 | 10/128 | 3.147922 | 7.119178 |
| held_groups | 28/128 | 12/128 | 3.051521 | 7.241176 |

All128fitted integers are correct by update100 and remain correct at the fixed final update2000. This meets the declared small-set capacity gate. It demonstrates fitting these examples with this actual head/input setup, not general recoverability, learning Fish intent or the original category goal.

Controls are disjoint from the new head optimization. Same-fit-group controls draw from groups actually represented by fit rows; held-group controls use disjoint groups. However the frozen M01 encoder, normalization, vocabulary/counts AND warm P05 head previously saw eligible TRAIN including these controls. Their deterioration is not untouched full-policy generalization evidence. Local fine-tuning can forget prior knowledge.

The supplemental post-fit label-coverage strata retain all128rows per cohort and separate targets with absolute/residual explanation labels present versus absent in the new microfit. Coverage shifts and forgetting limit causal attribution of control decline. See analysis; no subset or earlier checkpoint is substituted for the declared final result.

Target rank is among distinct existing point/fallback-mode candidates, not all integers. Absolute/residual/fallback credits marginalize equivalent probability explanations; they are not unique true algorithms or intent labels. Every target is in the existing absolute vocabulary. No new values/library expansion or missing-label deletion.

R02’s3/128 came from a different single-logistic head and representation. This is not a controlled architecture comparison against R02. The optimizer/presentation and warm-start also differ. P05’s original full-data selected modes remain the benchmark comparison.

**Execution provenance:** the fit ran after a source-archive assertion made the intended commit step fail. The parent failed to gate the later tool call on that failure. Therefore recorded execution commit `3d10b9e501e701d1c2149a958a3382b474da8bc0` does not contain PC00 source. The protocol/source hashes were frozen before optimization and match the preserved exact executed-source bundle and subsequent source commit. Checkpoint commit fields are not rewritten, and the fit is not rerun. See PC00-execution-provenance.json. A separate earlier synthetic availability-fixture failure and newline reconstruction failure are preserved.

All207816head parameters are trainable and optimizer membership is checked explicitly. First-update parameter/output gradient norms, all five assessment checkpoints, raw outputs and probabilities are retained. The final2000step checkpoint is fixed, with no DEV lookup, early stopping or retrospective selection. Two focused measurement tests pass. Extraction and causal integer recovery reuse prior immutable evidence; no repeated495game audit.

Only conditional integer diagnostics are reported: action type is supplied as priority. There is no deployable joint accuracy or full-policy improvement claim. Any later policy comparison must re-decode normalized joint probabilities because new integer probabilities can change the winning action family. Original benchmark/success targets remain binding.

Both75game reservations stay sealed. No DEV payload is consumed by this probe. No matches, downloads, bot/runtime work or deployment. No promotion or robustness claim. Fresh Solxhigh review follows, then research continues from evidence.
