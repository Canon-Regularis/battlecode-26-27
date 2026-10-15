# D1 local evaluation

## 2026-10-14 D1.7 update

D1.7 supersedes the original result below. It uses G3's compact gameplay core with a map-adaptive choice between the standard Tavi/Varg/Ren roster and the Cassi & Issac/Stellar/Tavi economy roster.

The frozen candidate completed two identical full-cap matrices against G3 at **10/18 wins**, **16,341 submitted vs 15,596**, **+745 net**, 311 deaths and zero faults. It then scored 13/18 against the carrier hunter and 13/18 against altar denial. See [DEVELOPMENT_RESULTS_2026-10-14.md](DEVELOPMENT_RESULTS_2026-10-14.md) for the map table, proxy comparison, rejected experiments and limitations.

The sections below preserve the original independent D1's 5/18 evidence for audit.

## Summary

The final D1 policy built successfully and ran at the official Python limit (`--fuel 100000`, or 2,500,000 Python fuel). The 18-match G3 comparison covered all nine maps with D1 on each side once. D1 won 5/18; G3 won 13/18. The runner exposed no seed option, so this is a fixed map/side matrix, not a randomized confidence estimate.

| Map | D1 Team A | D1 Team B | D1 wins |
|---|---|---|---:|
| Collision | G3 | G3 | 0/2 |
| Corners | G3 | G3 | 0/2 |
| Elkring | G3 | D1 | 1/2 |
| Expanse | G3 | G3 | 0/2 |
| Interlock | G3 | G3 | 0/2 |
| Lanes | G3 | G3 | 0/2 |
| Monolith | G3 | G3 | 0/2 |
| Packs | D1 | D1 | 2/2 |
| Rows | D1 | D1 | 2/2 |
| **Total** |  |  | **5/18** |

The final run-batch report recorded 18 replay bundles and zero failed matches. Individual `cambc run` checks also reported zero bot crashes. Replays are in `replays/D1-G3-matrix/`; the manifest used is [G3_matrix_manifest.txt](G3_matrix_manifest.txt).

## Iteration evidence

- The initial cycle-ranking version had a documented API-field error, then scored poorly. That invalid run is retained in `results/` for audit and is not a valid performance sample.
- A separate adaptive bank-versus-farm pilot scored 188 gems on Packs; immediate banking in the following pilot scored 48. These single, unpaired runs were exploratory.
- The simpler path-aware clear/capture/deposit loop scored 632 on Packs before targeted combat changes.
- Adding visible carrier attacks, Varg's low-health shield, and attack-reset ordering produced a full Packs win: D1 1,000–944 G3, with 6–7 kills/deaths versus G3's 3–9. The full map/side matrix still shows the gain is map-dependent.
- On a separate Collision stats run, D1 submitted 0 and G3 1,012; on Interlock with D1 as Team B, D1 submitted 144 and G3 1,026. These are clear failures to investigate before any promotion.

## Decision

Keep D1 as a separate research challenger and G3 as canonical. D1's Packs/Rows results justify retaining the combat-aware resource loop as a map specialist, but the 5/18 broad result is not a general upgrade. The next useful experiment is diagnosing why D1 stalls or fails to bank on Collision, Corners, Expanse, Interlock, Lanes and Monolith, then testing any fix on both sides with full-cap replays.

See [FAILURE_ANALYSIS_2026-10-14.md](FAILURE_ANALYSIS_2026-10-14.md) for the code-level diagnosis, confirmed statistics, evidence gaps, and recommended next experiments.
