# LARPBOT Rapid Upgrade Results

Date: 2026-10-13  
Engine: CAMBC `0.0.1` (`engineVersionPacked: 65536`)  
SDK: `2.1.5`  
Canonical bot: `bots/larpbot`

## Result

The promoted bot won **16/18** side-balanced matches against `starter-python`, compared with **14/18** for the saved Stage 1 baseline. Across the 18 LARPBOT team-results, it submitted 17,707 gems versus 17,150 (+557), collected 18,608 versus 18,324 (+284), and recorded 254 deaths versus 335 (-81). It earned 61,300 gold versus 62,950 (-1,650); this suite mostly ended by reaching 1,000 gems, so gold is not the deciding outcome in these matches. All 18 final matches completed with zero reported bot faults.

The runner does not expose a seed option. These are matched map/side scenarios, not independent randomized samples or a tournament win-rate estimate. Both rosters can vary with map and available draft slots.

## Changes promoted

### Tavi / Varg / Ren draft priority

`src/draft.py` now prefers draft picks in this order: Tavi, Varg, Ren, Ryth, Vendetta, then the remaining released choices. On maps with three picks, this gives Tavi/Varg/Ren; later picks add Ryth and Vendetta. Tavi can buy Strength shards away from spawn, Varg is effective on grouped camps, and Ren adds durability and a dash. The change is supported by a full nine-map, both-sides suite. It changes the roster, so it is not a controlled comparison of individual champion contributions.

### Lethal gem-carrier attack priority

`src/simple_policy.py` first checks enemies already within basic-attack range. It prioritizes a gem-carrying enemy only when one basic attack is enough to kill them; otherwise it retains the previous vision-list target order. This avoids spending an attack on a healthy carrier merely because they have a large bag.

With the previous draft, this gameplay change kept the starter result at 14/18 and raised aggregate submitted gems by 818 in the single matched matrix. In four focused matches against the saved baseline it split 2–2. The final draft-plus-gameplay candidate won 3/4 focused Corners/Interlock matches against the saved baseline.

## Baseline versus final by map and side

Scores are LARPBOT's submitted gems. The baseline values are from the recorded `final6` suite; final values are from `draft_tvr`.

| Map | Side | Baseline | Final | Final round |
|---|---|---:|---:|---:|
| collision | A | W · 1,012 | W · 1,012 | 1,257 |
| collision | B | W · 1,012 | W · 1,012 | 928 |
| corners | A | W · 1,008 | W · 1,010 | 510 |
| corners | B | L · 374 | W · 1,006 | 455 |
| elkring | A | W · 1,026 | W · 1,008 | 846 |
| elkring | B | W · 1,008 | W · 1,008 | 788 |
| expanse | A | W · 1,046 | W · 1,028 | 648 |
| expanse | B | W · 1,026 | W · 1,022 | 731 |
| interlock | A | L · 784 | L · 560 | 701 |
| interlock | B | L · 734 | W · 1,014 | 838 |
| lanes | A | W · 1,014 | W · 1,018 | 630 |
| lanes | B | L · 982 | W · 1,016 | 634 |
| monolith | A | W · 1,018 | L · 856 | 1,016 |
| monolith | B | W · 1,002 | W · 1,032 | 844 |
| packs | A | W · 1,040 | W · 1,016 | 753 |
| packs | B | W · 1,040 | W · 1,010 | 768 |
| rows | A | W · 1,001 | W · 1,023 | 1,051 |
| rows | B | W · 1,023 | W · 1,056 | 897 |

The final losses are Interlock A and Monolith A. Corners B and Lanes B flipped from losses to wins, while Interlock B also flipped to a win. The Monolith A regression is a new weakness to investigate.

## Evidence and rejected experiments

- **Carrier banking threshold (rejected):** Holding bags below 40 gems unless exposed did not improve Corners and reduced Interlock scores in the isolated check. Combined with broad carrier targeting, it finished 13/18. Keep immediate banking behavior.
- **Broad rich-carrier targeting (rejected):** Always preferring the enemy with the largest gem bag reached 15/18 against the starter but lost all four focused head-to-head games against the saved baseline. Replaced by the lethal-only condition.
- **Tavi / Varg / Marcella-first (rejected):** The six-game Corners/Interlock/Expanse screen went 3/6, with both Corners sides and Interlock B lost. It did not beat the original draft on that screen.
- **Tavi / Varg / Ren-first (promoted):** Full 18-game suite reached 16/18; the same three-map screen was 5/6. It beat the saved baseline in 3/4 direct Corners/Interlock matches (both sides represented).
- **Reliability:** Final suite JSON reports zero faults for both teams in every match; build and match execution completed. No out-of-fuel event was reported.
- **Fuel:** Per-turn fuel consumption and peak fuel were not exported by `cambc run --statistics` or exposed in its console summary. Fuel headroom for the final candidate is therefore **unverified**; zero faults is not proof of a safe fuel margin.

Raw final statistics are in `results/draft_tvr_<map>_<side>.json`; the associated replays are under `replays/larpbot/`. The previous full bot snapshot is `bots/archive/retired_bots/larpbot_baseline_20261013`.

## Rollback

To restore the previous source and project settings without touching the new benchmark report:

```powershell
Copy-Item -Path bots/archive/retired_bots/larpbot_baseline_20261013/src/* -Destination bots/larpbot/src -Recurse -Force
Copy-Item -LiteralPath bots/archive/retired_bots/larpbot_baseline_20261013/README.md -Destination bots/larpbot/README.md -Force
Copy-Item -LiteralPath bots/archive/retired_bots/larpbot_baseline_20261013/pyrightconfig.json -Destination bots/larpbot/pyrightconfig.json -Force
cambc build bots/larpbot
```

The complete pre-upgrade snapshot remains at `bots/archive/retired_bots/larpbot_baseline_20261013`, including its project metadata, results, and compiled cache.

## Build and package for manual submission

From the repository root:

```powershell
cambc build bots/larpbot
cambc bundle bots/larpbot --output bots/larpbot_submission_final.zip
```

The source to submit is **`bots/larpbot`**. A local package is available at `bots/larpbot_submission_final.zip`. The ZIP command only packages it locally; do not use an upload or submit command. The team handles official submission manually.
