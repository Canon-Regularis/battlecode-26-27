# Preserved checkpoint history

M01 and P05 remain unchanged. P05 retains the strongest exact complete-command baseline among these three: 11,472/14,439. No certified replacement exists.

E00: all 14 epoch checkpoints retained locally; epoch 8 selected by the frozen minimum observed joint NLL (0.726085), never by peak accuracy. Selected model and train/development predictions are SHA-bound in E00.json. 23,688 optimizer steps, approximately 555.6 seconds including final scoring. It has 11,461 strict successes, 11 fewer than P05; no promotion and no seed-repeat trigger. Attack joint correctness improves to 894/985 (90.76%) as a single-checkpoint point estimate, without seed certification. Improving direction changes while losing continuing moves motivates measuring specialization, not claiming a movement win.

E00 pre-fit v1: no optimizer steps; batch-shape precision assertion failed. Original plan, verbatim sources and stdout remain under E00-prefit-v1. Corrected execution preserves the original 256-row frozen-priority GEMM before selecting rows; thresholds and data were unchanged.

E01: not fitted. Fresh completed-E00 review is required before the planned matched actual-entity treatment. No future experiment or success is implied.

All raw checkpoints and prepared replay data remain local and ignored by Git. The research PR remains draft and unmerged. Both 75-game reserved partitions remain sealed.
