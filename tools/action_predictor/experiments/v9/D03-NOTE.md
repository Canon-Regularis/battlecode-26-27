# D03 context and weighting diagnostic

Direction-change destination exactness is weak in both open and obstructed terrain. On development: 65/394 (16.50%) away from nearby obstacles versus 212/764 (27.75%) near them. On training: 26.73% versus 36.48%. Continuing moves remain much easier. This does not support attributing the direction-change bottleneck solely to missing obstacle geometry; objectives, visible entities, earlier observations and learned continuation bias remain separate hypotheses.

Ward share is 0.759% naturally sampled, 2.504% after augmentation, and 5.030% of nominal class-weighted sample mass. The final figure assumes equal per-row loss and is not a measured gradient contribution or proof of the recall/ward confusion's cause. Preserve rare recall while separately testing sampling and loss correction.

This is analysis of preserved predictions and hash-bound diagnostic arrays, with no fitting or newly evaluated predictor family. All support remains in the benchmark; both reserved partitions remain sealed. The JSON binds inputs and the verbatim analysis source.
