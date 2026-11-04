# leader_party versus every current bot

Benchmark on 2026-11-04: all 15 other bot artifacts recursively present under `bots/`, including proxies and archived implementations. Twelve complete release games per opponent: ambush, expanse, interlock, lanes, monolith and packs, each with swapped sides. One fixed recorded seed per map; no duplicate repetitions. Source and opponent artifacts were not changed.

**Total: 166 wins, 14 losses, 0 draws (92.2% wins), across 180 games.**

| Opponent (relative to bots/) | leader_party wins | Losses | Draws |
| --- | ---: | ---: | ---: |
| `D1` | 10 | 2 | 0 |
| `gold_diamond` | 11 | 1 | 0 |
| `larpbot` | 11 | 1 | 0 |
| `starter-python` | 12 | 0 | 0 |
| `opponents/altar_denial_proxy` | 11 | 1 | 0 |
| `opponents/carrier_hunter_proxy` | 11 | 1 | 0 |
| `opponents/economic_farmer_proxy` | 11 | 1 | 0 |
| `archive/retired_bots/E05A_meta_cassi_stellar_tavi` | 11 | 1 | 0 |
| `archive/retired_bots/E36_pair_jungle_emblem` | 11 | 1 | 0 |
| `archive/retired_bots/E37_elkring_jungle_build` | 11 | 1 | 0 |
| `archive/retired_bots/E39_loaded_lethal_intercept` | 11 | 1 | 0 |
| `archive/retired_bots/E41_occupied_camp_yield` | 11 | 1 | 0 |
| `archive/retired_bots/E51_no_empty_retreat` | 11 | 1 | 0 |
| `archive/retired_bots/larpbot_baseline_20261013` | 11 | 1 | 0 |
| `archive/state-machine-2026-11-04/starter-cpp` | 12 | 0 | 0 |

Zero VM faults for either side across all 180 games. One nonfatal unexpected SDK error was logged by leader_party against archived E39 on ambush as A (engine error 5: invalid metadata/alignment/overlap/argument); leader_party still won 1,010-413. Its cause has not been diagnosed in this statistics run.

The old archived C++ bot scored zero gems in all twelve games, so its 12-0 result is a weak baseline. D1 is the strongest opponent in this six-map direct comparison, with two wins against leader_party; this does not establish a global tournament ranking.

The leader_party WASM SHA-256 was `844b9b03bf09d7a0ac286c8a05cbe0ce3e371b309c15f66f1a0cfb6077c98f2a`, matching the previously submitted/tested build. All 15 opponent artifacts were hash-verified unchanged after the suite.

[Full scores, artifact hashes, seeds, faults and replay paths](evaluation/2026-11-04/all-bots-results.json). Replays are saved locally in `replays/leader-party/all-bots-20261104/`.

This suite is comparable with the earlier main-map results: gold_diamond is 11-1 over twelve distinct map/side conditions, rather than the earlier 22-2 figure that counted two identical repetitions.
