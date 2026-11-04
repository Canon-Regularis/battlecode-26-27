# Initial configuration tuning: historical G2 result

> Historical first pass. The [complete tuning report](config_tuning_all_stats.md) supersedes this recommendation.

Use [`leader_party_tuned`](../../../bots/leader_party_tuned/README.md), matching
**`g02_bank35`**. It is the practical recommendation from 25 frozen configurations
over three generations. Original bots and every generation remain intact.

Completed **5,818 replay jobs**, representing **5,602 distinct WASM/map/seed/side
conditions** after removing control mirrors and artifact aliases. No conflicting
scores were found for repeated deterministic conditions. All completed matches had
zero VM faults; nonfatal action errors are recorded rather than discarded.

| Setting | Untuned Subhan bot | Recommended profile |
| --- | ---: | ---: |
| Banking bag threshold | 20 gems | **35 gems** |
| Maximum bag age | 40 rounds | **70 rounds** |
| Low-Health danger/recovery threshold | 35% | 35% |
| Recovery-clear and optional ward HP threshold | 55% | 55% |
| Empty-bag equipment recall | 300 gold | 300 gold |

All other final values stay at their original defaults, including draft, combat,
movement, fuel admission, task limits, wards, coordination settings and Subhan's
search bounds/weights. This changes banking cadence, not the pathfinding algorithm.

## Full published pool: identical 516-condition comparison

Each profile plays both sides of all 86 published maps against the untuned Subhan
bot, D1 and `gold_diamond`, at CAMBC 4.0.0 default fuel and round limits.

| Profile | Total W–L | Versus untuned Subhan | Versus D1 | Versus gold_diamond |
| --- | ---: | ---: | ---: | ---: |
| Untuned control | 359–157 | 86–86 calibration | 137–35 | 136–36 |
| G1: recovery 25%/45% | 373–143 | 89–83 | 143–29 | 141–31 |
| **G2: banking 35/70** | **381–135** | **96–76** | **147–25** | **138–34** |
| G3: banking 30/60, recovery 20%/40% | 380–136 | 100–72 | 141–31 | 139–33 |
| G3: banking 30/60, recovery 25%/45%, recall 450 | 373–143 | 98–74 | 139–33 | 136–36 |

The recommended profile gains **22 wins**, from 69.6% to 73.8%, on this matrix.
Its mean gem margin is +258.67, versus the control's +235.16. Logged `LP_ERROR`
entries are 29 versus 32, with zero VM faults for either. The control faces a
frozen identical copy in the Subhan column; its balanced 86–86 is a calibration,
not independent evidence of an improvement. Mirrored duplicates are excluded from
the unique-condition coverage count.

## Why keep the older generation

The last 51 maps were excluded from parameter creation. Their results are:

| Profile | Combined W–L | Versus untuned Subhan | Versus D1 | Versus gold_diamond |
| --- | ---: | ---: | ---: | ---: |
| Untuned control | 212–94 | 51–51 calibration | 81–21 | 80–22 |
| G1 recovery | 221–85 | 50–52 | 88–14 | 83–19 |
| **G2 banking** | **227–79** | **59–43** | **87–15** | **81–21** |
| G3 recovery 20%/40% | 228–78 | 60–42 | 87–15 | 81–21 |
| G3 recall 450 | 222–84 | 56–46 | 84–18 | 82–20 |

G3 wins one more game on those 306 conditions; G2 wins one more over the full
published pool. These profiles are effectively near-tied. Prefer G2 as the practical
default because it also wins **72–66 directly against G3** across 69 maps, wins six
more D1 games over the full pool, and changes only the two banking settings. Keep
`lp_tune_g03_recover20` as the near-tied, more aggressive alternative: it has the
better direct record against the untuned bot.

There is no universal head-to-head winner. G2 lost **16–20** to G1 on the 18-map
validation tournament, despite its better overall opponent-matrix results.
Winning a training screen or being the newest generation does not make a profile
the best general choice.

## Wider opponent check

All five fully evaluated profiles also face all 15 pre-existing bot artifacts on
ambush, expanse, interlock, lanes, monolith and packs, with both sides:

| Profile | Wins | Losses | Logged LP_ERROR entries |
| --- | ---: | ---: | ---: |
| Untuned control | 180 | 0 | 0 |
| G1 recovery | 179 | 1 | 4 |
| **G2 banking** | **180** | **0** | **4** |
| G3 recovery 20%/40% | 178 | 2 | 1 |
| G3 recall 450 | 178 | 2 | 2 |

Every opponent is beaten 12–0 by the recommended profile, including D1,
gold_diamond, larpbot, the starter, three proxy policies and archived bots.
These are 900 games across the five profiles. This smaller, largely weaker
opponent suite is reported separately from the broad-map common-opponent matrix;
it is not pooled to overweight archived opponents. Its results do not establish
performance on all 86 maps against all 15 bots.

## Search and selection

The unchanged tuning control exposes previously hardcoded bag size/age, recovery,
recall, competition and planner constants through `Config`. Its release WASM
matches the current untuned best **byte-for-byte**, so default parameterization
does not alter the control. All generated gameplay source files are identical
between generations except `config.h`.

- G1 screens 12 variations in banking, recovery, camp limits, risk/opening weights,
  search width, route length/service estimates and wards on eight training maps.
- The top three expand to 17 training maps and five opponents. The screen leader,
  30/60 banking, falls behind the recovery-only profile on this larger set.
- G2 tests nearby banking values, combinations with later recovery/wards and
  equipment recall. G3 varies bag age, recovery and recall independently around
  promising combinations. Each generation keeps its complete config and parent.
- All 25 configurations freeze before candidate validation on 18 separate maps.
  The control wins 134/180; G3 finalists win 133 and 132, G2 wins 129, G1 wins 127.
- Two G3 finalists initially advance to the 51-map final set. Direct checks show
  older generation winners narrowly beating the first finalist, so those already
  frozen profiles also receive the same final matrix and broad opponent check.

This is adaptive selection among four already-frozen tuned profiles. The final
51-map set is held out from **parameter creation**, but is subsequently used for
final selection; it is not an untouched confirmation set for the final chosen
winner. Training-screen and post-selection intervals are exploratory. Map-cluster
bootstrap intervals are descriptive. For G2 versus the control on the final 51
maps, the 10,000-sample map-cluster interval for win-rate change is approximately
**+0.65 to +8.82 percentage points** (seed 127; point estimate +4.90). This is
uncorrected for adaptive selection and multiple candidates. The record supports a
best tested recommendation, not a decisive statistical or global optimum claim.

Final judgement also reconciles the nearly tied G2/G3 results rather than blindly
choosing the newest profile or the one extra final-set win. The full-pool count,
D1 record, direct parent comparison, wider-opponent result and fewer changed
settings favor G2; the preserved G3 profile remains a reasonable alternative.

The CLI fixes seeds per map. Repeating a deterministic condition does not produce
new independent evidence. Cached results are reused across stages. The full-pool
table deliberately includes training maps because the practical objective is
performance on the current published pool; it is not an unbiased future-map estimate.

## Validation and reproduction

Normal/release builds and native decision/protocol tests pass. Banking-boundary
tests cover configured small/large thresholds and age deadlines. The stable
`leader_party_tuned` release must match the selected generation's frozen WASM hash;
source hashes also verify the original bot and all preserved generations. The
underlying loop algorithm retains its earlier 240-case Python/C++ differential
verification. VM faults, bounded `LP_ERROR` log entries, zero-score games, seeds,
deaths, artifact hashes and replay paths are retained in the per-game evidence.

Recommended WASM SHA-256:
`3843fcc70eb2b856934cef525a89f1042205011fcda5320c196cd2b3c8f339d2`.
Untuned control:
`6979aff24f99907ca5838297d18983b34f4e37c4720ed1196be44aa5a7866541`.

The platform submission is unchanged. Native fuel safety limits and shared
coordination remain fixed; this experiment does not establish useful behavior
under custom very low fuel, new seeds, or unseen opponent strategies.

- [Full-pool summary](evaluation/2026-11-04/tuning/full-pool-summary.json)
- [Generation configurations and hashes](evaluation/2026-11-04/tuning/generations.json)
- [Selected champion](evaluation/2026-11-04/tuning/champion.json)
- [Map splits](evaluation/2026-11-04/tuning/experiment.json)
- [Coverage and repeat checks](evaluation/2026-11-04/tuning/coverage.json)
- [G3 final set](evaluation/2026-11-04/tuning/final-holdout.json)
- [Earlier-generation final set](evaluation/2026-11-04/tuning/parents-holdout.json)
- [Direct parent checks](evaluation/2026-11-04/tuning/champion-vs-parents-holdout.json)
- [Wider opponent results](evaluation/2026-11-04/tuning/broad-opponents.json)
- [Earlier-generation wider results](evaluation/2026-11-04/tuning/parents-broad.json)
- [Evidence index](evaluation/2026-11-04/tuning/README.md)
- [Runner](../../../tools/tune_leader_party.py)

```powershell
uv run --locked cambc build leader_party_tuned --release
& bots/leader_party_tuned/tests/run.ps1
.venv/Scripts/python.exe tools/tune_leader_party.py build g02_bank35
.venv/Scripts/python.exe tools/tune_leader_party.py rank parents-holdout
```

The runner requires the preserved opponent ZIPs under `.cambc/`, with hashes
recorded in the receipts. Build logs and replay ZIPs remain ignored locally under
`.cambc/tuning/` and `replays/leader-party/tuning/cache/`; source, configurations
and compact per-game results are retained in the repository.
