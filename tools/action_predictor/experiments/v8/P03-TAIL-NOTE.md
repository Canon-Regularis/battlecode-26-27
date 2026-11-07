# P03 tail and coverage amendment

Aggregate priority gains coexist with a worse maximum error and zero exact rare/unseen values. Full-support likelihood alone does not establish unseen-value predictive quality. No replacement or restored-input attribution.

Priority joint correctness is57/576 (9.90%); at least519 is required, a gap of462. Frozen action decisions cap this branch at343/576.

Maximum absolute priority error rises from P02's827 to P03's1489. Errors over1000: P020, P0312. These are post-hoc diagnostic summaries, not new success criteria.

All four unseen-value rows remain wrong; their mean NLL worsens from8.14918 (P02) to11.80325 (P03). All65 rows whose targets appear1–19 times in augmented training remain in evaluation and get zero exact predictions; their NLL is8.03333 versus7.63282 for the frequency baseline. Of96 exact predictions,88 concern values seen at least100 times in training.

The learned fallback has full probability support, but none of the576 priority argmax forecasts is outside the training vocabulary. The supporting normalization/unseen-decoder tests establish capability, not actual unseen-value accuracy.

Per-group counts and20 largest errors with personal-PRE current/scheduled/earlier values are in the JSON. Recorded targets and error signs appear only in diagnostics, never inference inputs. No reserved games were opened.
