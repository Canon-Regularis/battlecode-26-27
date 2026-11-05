# larpbot Stage 1 baseline

## Scope

Built with `cambc build bots/larpbot` and run against `bots/starter-python` on all nine maps. The final matrix used one completed match per map, with larpbot as Team A. Seeds are not controlled or reported by this runner, so this is an initial smoke benchmark, not a reliable win-rate estimate. Replays are in `replays/larpbot/`; raw summary JSON is in `bots/larpbot/results/final_<map>.json`.

## Results

| Map | Result | End round | Larpbot tributed | Starter tributed | Captures observed* | Capture resets* | Stalled markers* | Respawn evacuations | Risk markers | Stuck | Bot errors | Peak fuel / 2.5M | Larpbot roster observed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| collision | Loss | 810 | 418 | 1,018 | 108 | 4 | 7 | 48 | 0 | 0 | 0 | 2,473,477 | Varg, Tavi, Cassi & Issac |
| corners | Loss | 405 | 290 | 1,002 | 30 | 0 | 0 | 13 | 0 | 0 | 0 | 2,489,573 | Cassi & Issac, Ren, Tavi, Ryth, Prism |
| elkring | Loss | 1,064 | 612 | 1,008 | 46 | 5 | 6 | 18 | 0 | 0 | 0 | 2,494,035 | Vendetta, Varg, Tavi, Willow, Ryth |
| expanse | Loss | 991 | 778 | 1,024 | 29 | 0 | 1 | 25 | 0 | 0 | 0 | 2,437,020 | Tavi, Prism, Marcella |
| interlock | Loss | 543 | 330 | 1,010 | 35 | 2 | 6 | 17 | 0 | 0 | 0 | 2,441,790 | Prism, Cassi & Issac, Vesper Vale, Ren |
| lanes | Win | 710 | 1,018 | 718 | 67 | 2 | 5 | 42 | 0 | 1 | 0 | 2,491,810 | Cassi & Issac, Tavi, Ren, Ryth, Stellar |
| monolith | Win | 1,202 | 1,018 | 996 | 67 | 9 | 4 | 43 | 0 | 0 | 0 | 2,495,164 | Ryth, Vesper Vale, Varg, Tavi, Marcella |
| packs | Loss | 686 | 452 | 1,004 | 14 | 1 | 12 | 10 | 0 | 0 | 0 | 2,386,411 | Ren, Prism, Stellar |
| rows | Loss | 1,036 | 66 | 1,012 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 2,456,626 | Willow, Marcella, Tavi, Prism |

**Aggregate:** 2 wins / 9 matches; 4,982 gems tributed by larpbot and 8,792 by the starter opponent across completed games. Results are not champion-controlled and should not be interpreted as a composition comparison.

\* `captures observed` counts distinct round/group transitions into the respawning state visible to a champion. `Capture resets` counts visible reward-to-alive transitions. `Stalled markers` are diagnostic intervals while a champion stays on a capture tile; they are not counts of unique failed capture attempts. Vision and duplicated per-champion observations limit these as match-wide ground truth.

## Correctness and fuel notes

- All nine final runs completed; runner-reported crashes were zero and the bot logged zero turn errors.
- One stuck marker and zero `respawn_block_risk` markers were observed in the final matrix. The bot made 217 logged immediate evacuations from respawning camp tiles across these matches. The forced evacuation now runs before banking and farming.
- Respawn timers observed before vision is lost are remembered conservatively. Near a remembered respawn tile, movement uses a local safe step; elsewhere it delegates navigation to the SDK's `move_towards()`.
- Maximum measured turn use was 2,495,164 of 2,500,000 fuel (Monolith), leaving only 4,836 fuel of headroom. Fuel is reported at periodic checkpoints, so a rare unobserved peak may be higher. Reduce repeated state and navigation work before adding strategy complexity.
- The first all-map diagnostic run revealed two defects that were fixed before this final matrix: a Python runtime missing the Varg splash constant (now uses the GameRules radius of one tile), and stale camp handles from `vision.camps()` (now enumerates static group camp handles and checks visibility individually). Earlier results are retained in `results/` but are superseded by the final files above.
- `draft.py` contains the intended champion preference, but the final match rosters do not consistently match that preference, and draft stdout is absent from the replay. A diagnostic draft-memory submission also appeared as zero bytes during gameplay. Composition control therefore remains unverified and must be resolved before drawing conclusions about Vendetta/Varg/Ryth or other lineups.

## Interpretation and next work

The bot now completes the core loop without observed turn faults and avoids standing on known respawn tiles, but it is not yet competitive: it lost seven of nine single-seed matches to the starter, with particularly weak gem throughput on Rows, Corners and Packs. The result does not show whether this comes from draft fallback, objective selection, camp combat throughput, banking cadence or map geometry.

Next, verify draft selection in an instrumented minimal bot and prove the emitted picks against `teams[].draftPicks`. Then profile high-fuel turns and investigate the low-throughput maps before adding PvP tactics. Benchmark with fixed compositions and multiple seeds/sides so policy changes can be separated from draft and RNG variance.
