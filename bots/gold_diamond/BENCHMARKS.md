# Local benchmarks

All figures use the installed CAMBC 2.1.5 engine and its default fuel setting. Match statistics JSON files are in `benchmarks/`. A suffix `_a` means this bot was team A; `_b` means it was team B. `summarize_benchmarks.py` counts the `outcome` field rather than inferring wins from gems. The CLI offers no seed option, so map/side results are deterministic samples and should not be read as a confidence interval or a ladder rating.

| Candidate or opponent | Matches | Wins | Gems tributed by candidate | Opponent gems | Engine bot faults |
| --- | ---: | ---: | ---: | ---: | ---: |
| Final bot vs D1, 9 maps × 2 sides | 18 | 8 | 16,073 | 16,313 | 0 |
| Compact prototype vs D1 | 18 | 9 | 16,231 | 16,549 | 0 |
| Shared single-target claim prototype vs D1 | 18 | 1 | 9,482 | 17,843 | 0 |
| Monster Strength shard prototype vs D1 | 18 | 5 | 16,164 | 17,461 | 0 |
| Tavi/Cassi & Issac/Vendetta draft prototype vs D1 | 18 | 8 | 15,921 | 16,963 | 0 |
| Final bot vs economic farmer proxy, 3 maps × 2 sides | 6 | 4 | 5,899 | 4,394 | 0 |
| Final bot vs carrier hunter proxy, 3 maps × 2 sides | 6 | 5 | 5,425 | 5,456 | 0 |
| Final bot vs altar denial proxy, 3 maps × 2 sides | 6 | 5 | 4,507 | 3,822 | 0 |

The final D1 run used the actual bundled source, with the production policy selected. The compact prototype used the same draft and economic loop in a temporary probe bot; the small win difference came from a Corners side result. The larger experimental policy previously won only 2 of 18 in an early matrix and acted for the first time around round 71 on Expanse, versus round 29 for the compact loop. That early matrix was run while the candidate was still changing, so it is diagnostic rather than a final comparison.

The final bot's 8/18 D1 result and its Corners side sensitivity are the clearest evidence that this is a working candidate rather than a demonstrated Gold-level bot. The three proxy styles add coverage, but they are local programs and may not reflect ladder opponents.
