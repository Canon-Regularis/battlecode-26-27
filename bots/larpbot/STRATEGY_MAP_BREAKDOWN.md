# Pressure map breakdown — E05A and G2

Correct-cap results (`--fuel 100000`, the 2,500,000 Python fuel budget). Each row sums Team A and Team B on one map. Cells show wins / 2; our submitted gems – opponent submitted gems; our deaths. These are fixed map/side runs without independent seed variation.

## Carrier hunter

| Map | E05A | G2 baseline |
|---|---:|---:|
| Collision | 1/2; 1,290–1,114; 34 | 1/2; 1,232–1,400; 26 |
| Corners | 1/2; 1,864–1,910; 59 | 0/2; 972–2,040; 36 |
| Elkring | 0/2; 1,098–2,034; 88 | 1/2; 1,566–1,854; 62 |
| Expanse | 0/2; 1,752–2,050; 22 | 1/2; 1,830–1,830; 13 |
| Interlock | 2/2; 2,050–1,618; 40 | 0/2; 1,658–2,038; 34 |
| Lanes | 1/2; 2,000–1,904; 31 | 1/2; 2,010–1,986; 21 |
| Monolith | 1/2; 1,750–1,544; 54 | 1/2; 1,434–1,596; 37 |
| Packs | 1/2; 1,812–1,852; 38 | 1/2; 1,964–1,670; 20 |
| Rows | 1/2; 1,947–1,782; 30 | 1/2; 1,881–1,881; 16 |

## Altar denial

| Map | E05A | G2 baseline |
|---|---:|---:|
| Collision | 2/2; 242–176; 6 | 2/2; 418–308; 10 |
| Corners | 1/2; 818–886; 43 | 1/2; 580–556; 20 |
| Elkring | 1/2; 1,134–1,638; 61 | 0/2; 414–2,016; 29 |
| Expanse | 0/2; 1,682–2,054; 22 | 1/2; 1,830–1,900; 13 |
| Interlock | 0/2; 746–942; 35 | 0/2; 1,094–1,228; 22 |
| Lanes | 1/2; 1,808–1,902; 32 | 1/2; 2,010–1,986; 21 |
| Monolith | 1/2; 1,400–1,596; 50 | 1/2; 1,668–1,582; 35 |
| Packs | 1/2; 1,526–1,734; 36 | 0/2; 1,882–2,080; 24 |
| Rows | 1/2; 1,991–1,683; 34 | 1/2; 1,947–1,815; 16 |

## What the map results say

- **Elkring and Expanse are the broadest pressure problems.** E05A lost both sides against the carrier hunter on both maps. On Expanse it also lost both sides and trailed altar denial by 372 gems. E05A's Elkring carrier-hunter games were especially poor: 1,098 submissions to the proxy's 2,034, with 88 team deaths. Its linked pair contributed 32 deaths and collected 360 gems (252 submitted).
- **The matchup changes with the map.** E05A swept Interlock against the hunter (2/2, +432 gems) but lost both games to altar denial there. Elkring shows the reverse pattern: E05A's altar result (1/2, 1,134 gems) was better than G2's 0/2 and 414 gems, while it fell behind the hunter more sharply than G2.
- **One universal escort or retreat threshold is unlikely to fix both.** Correct-cap E06's earlier no-bag pair retreat improved the full altar-denial suite but reduced G2 mirror wins and did not improve the hunter score. It also increased linked-pair deaths. E33's threat-gated version did not improve the pressure pilot.

Source statistics: E05A's `results/python_2p5m/carrier_hunter_proxy` and `altar_denial_proxy`; G2's `bots/benchmark_runs/2026-10-14_python_2p5m/g2_vs_carrier_hunter_proxy` and `g2_vs_altar_denial_proxy`. Replays remain under `replays/fuel_corrected_20261014/`.
