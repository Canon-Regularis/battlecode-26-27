# P04 matched input ablation: gate not met

P03 uses the39 recovered priority channels; P04 zeroes them. Both retain the same87,528-parameter output head and frozen M01 representation.

Exact values:96 versus71 out of576 (+4.340 percentage points). Joint commands:57 versus49 (+1.389 points). The5-point exact-gain gate required at least29 additional correct values; the observed gain is25. The gate is not met and no matched seed repeats are triggered.

Paired whole-group intervals: exact gain−0.816 to+10.313 points; joint gain−0.811 to+3.534 points. Priority NLL improves4.14836→3.99395; its relative-reduction interval is0.67%–6.20%. These intervals condition on selected checkpoints and five reused development groups.

Mean integer error falls435.851→178.109; errors above1000 fall115→12; wrong-sign predictions fall197→81. This exploratory error improvement does not replace the missed gate or the original accuracy targets.

Both arms remain0/4 on unseen values and0/65 on rare training values. Rare-value NLL is worse with recovered inputs:8.03333 versus7.91319. Their rows remain included. The full-support fallback produces no actual non-vocabulary argmax in either arm.

Epoch-zero scores and the eight shared epoch shuffle RNG states match exactly. Every saved control extra-column weight remains zero. All saved outputs/decoded priorities and the75-target causal inference roundtrip reproduce.

The all-category90% and original benchmarks remain unmet. No replacement, strategy-similarity claim, independent full-GRU seed confirmation or reserved evaluation is established. Fresh review is required before further work.
