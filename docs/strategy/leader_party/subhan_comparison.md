# Subhan route-planner experiment

Evaluated 2026-11-04 with CAMBC 4.0.0. Experimental bot:
[`bots/leader_party_subhan`](../../../bots/leader_party_subhan/README.md).

This is the original port evaluation. The subsequent [configuration tuning](config_tuning.md) identifies `leader_party_tuned` as the newer preferred profile, while preserving both bots measured here.

**Recommendation at this stage: prefer `leader_party_subhan`.**
The clone wins the direct comparison 93–79 and has a slightly better combined
record against the two control opponents (73–23 versus 72–24). The advantage varies
by map and is a modest, uncertain upgrade rather than a proven general improvement.
Keep the original `leader_party` as the unchanged baseline and fallback. This
experiment did not change the platform submission.

## What was ported

The baseline is `leader_party` at `d8bd432`. Its 26 non-build files match the
pre-experiment SHA-256 snapshot. The clone contains a C++ translation of SubhanAfz's
SDK-independent `LoopPlanner` from `bots/economy-bot/src/planner.py` at
`97f761f04ed3d3e85a6f2217df345629baab58c8` (`feat/economy-strategy`).

This is a bounded beam search for recurring camp-to-altar farming routes. Subhan's
navigation module uses SDK BFS; the port is not a replacement low-level shortest-path
algorithm. Our existing BFS, movement, dash and combat implementation remain intact.
The separate Python optimizer's reported fuel savings do not measure this C++ bot.

The translated scoring function considers gems, gold, travel, camp service time,
tribute time, respawn periods, initial travel and spawn-distance exposure. Search
ranking, ties, deduplication and timing match the Python reference on 240 generated
cases, including unreachable legs and expansion cutoffs.

Integration adapts this planner to our existing strategy:

- Plan independently for Heart, Marcella, Vesper, Ren and Vendetta using approximate
  personal damage after opening equipment, rather than a combined squad DPS.
- Precompute static terrain BFS distances during draft. Shortlist 24 camps and four
  altars; use beam width four, at most five camps, 768 expansions and three candidate
  routes per champion. Gold weight is 0.02, opening weight 0.15 and risk tolerance 0.2.
- Reserve one million draft fuel, allocate remaining search fuel across bodies,
  publish completed plans progressively and provide an empty fallback packet first.
- Preserve original camp selection through the first two equipment phases. Then
  prefer the next eligible planned camp, checking current reachability, cooldown,
  danger and service limits. Skip unavailable camps and fall back to the old selector.
- Advance on completed or abandoned tasks. Keep existing shopping, recovery,
  bag-age, banking and tribute rules. The draft altar helps score routes; actual
  banking still selects the best currently reachable altar.

Only clone draft/objectives/task-completion integration changed, alongside new
`loop_planner.*` and `route_plan.*`. The original bot was not edited.

## Frozen artifacts and validation

All measured matches used frozen release ZIPs; no tuning followed the pool results.
These are SHA-256 hashes of `bot.wasm` inside each artifact:

| Bot | WASM SHA-256 |
| --- | --- |
| Original | `844b9b03bf09d7a0ac286c8a05cbe0ce3e371b309c15f66f1a0cfb6077c98f2a` |
| Clone | `6979aff24f99907ca5838297d18983b34f4e37c4720ed1196be44aa5a7866541` |

Release and normal builds pass, as do inherited state-machine/protocol scenarios,
240 differential planner cases and Python syntax checks. Native test compilation
emits nonfatal indentation and array-bounds warnings; a clean warning-free native
build is not claimed. These checks establish translation fidelity and buildability,
not correctness of the static model in live combat.

## Direct comparison: 172 games, 86 maps

Every published `00*`, `01*`, `02*`, `03*` and `adgato*` map was played once per
side. Nine unprefixed legacy maps were excluded. The engine fixes each map's seed;
replaying the same condition would not supply another independent sample.

| Measure | Clone | Original |
| --- | ---: | ---: |
| Wins | 93 (54.1%) | 79 (45.9%) |
| Submitted gems | 115,583 | 108,694 |
| Maps winning both sides | 25 | 18 |
| Nonfatal `LP_ERROR` entries | 24 | 24 |
| Games containing those errors | 20 | 19 |
| VM faults | 0 | 0 |

The other 43 maps split one win each. Sixteen games finished 0–0 and were awarded
by the engine's side-B tiebreak; those count as official wins but show no scoring
advantage. Each map's two sides have equal weight in the analysis.

The clone's mean gem margin is **+40.05 per game**. A map-cluster bootstrap with
10,000 samples and seed 127 gives an approximate 95% interval of **−5.52 to +87.16**.
This descriptive interval includes zero. It measures variation across these maps,
not future engine seeds, and does not prove a general win-rate advantage.

Examples illustrate how much the map matters:

| Map | Clone A: gems, opponent gems | Clone B: gems, opponent gems |
| --- | ---: | ---: |
| `00expanse` | 1010, 624 | 1017, 601 |
| `01hooks` | 1012, 627 | 1001, 242 |
| `01elk-arena` | 1008, 144 | 1008, 72 |
| `00monolith` | 772, 1000 | 774, 1053 |
| `02treasure-box` | 18, 251 | 381, 902 |

Draft logs confirm all five bodies received plans on these examples. Monolith
preparation used about 9.2 million draft fuel and a 120-byte packet. On treasure-box
the clone logged 13/21 deaths and 408/109 deferred fuel pauses by side: generating
a route does not remove live execution constraints. These observations do not
isolate a causal explanation for individual wins or losses.

## Opponent controls: 192 games

A fixed stratified sample contains five randomly selected maps from each numbered
prefix and all four adgato maps (sampling seed 20261104). On each of these 24 maps,
both variants played D1 and `gold_diamond` from both sides. All variants used the
same map/opponent/side conditions, at default engine fuel and round limits.

| Opponent | Original W–L | Clone W–L |
| --- | ---: | ---: |
| D1 | 37–11 | 37–11 |
| `gold_diamond` | 35–13 | 36–12 |
| Combined | 72–24 | 73–23 |

Against D1 the clone changed three losses into wins and three wins into losses.
Its mean own score fell by 37.67 gems, and its score margin fell by 89.08 gems
relative to the original under matched conditions. A map-cluster bootstrap gives
an approximate margin-change interval of −183.44 to −3.04 gems. This is evidence
against treating the direct lead as a universal upgrade; it is a descriptive
control result, not a preregistered significance claim.

Against `gold_diamond`, five losses became wins and four wins became losses.
Own score increased by 15.27 gems per game; margin increased by 7.31, with a
map-cluster interval of −116.63 to +109.48. Across both opponents, mean margin
change is −40.89 gems, interval −125.60 to +34.67, clustering all four conditions
together by map.

Controls had zero VM faults on either side, nine 0–0 games, three original
`LP_ERROR` entries and two clone entries. All 96 clone draft logs report five
planned bodies. Action errors are retained in the evidence rather than discarded;
unchanged combat code can still encounter different invalid-action situations
after route changes.

## Limits and conclusion

There are **364 distinct comparison matches**: 172 direct plus 192 controls.
Another 24 development matches used maps already included in the full pool, so
they are excluded from this total and the reported comparison statistics.
Repeated deterministic seeds would inflate the sample without resolving uncertainty;
the full published pool plus two opponent controls is a reasonable stopping point.
There is no demonstrated decisive overall winner. The clone has the better observed
direct and combined control records, so it is the preferred variant; retain the
original as a fallback. The gem-margin intervals above measure score differences,
not win-rate uncertainty, and do not negate the clone's observed winning record.

The route model uses static spawn-distance risk, approximate combat service times
and terrain paths that can cross occupied camp tiles. It does not simulate enemy
pressure, exact future health, cooldowns, champion congestion or respawn contention.
Selecting actual banking altars dynamically also departs from the scored loop.
These are plausible reasons for inconsistent benefits, not experimentally isolated
causes. Future work should compare congestion-aware and dynamically rescored routes
on a fresh evaluation set, rather than tune to the winning maps listed above.

## Evidence and reproduction

- [Direct per-game results](evaluation/2026-11-04/subhan/head-to-head.json)
- [Control per-game results, map list and artifact ZIP hashes](evaluation/2026-11-04/subhan/controls.json)
- [Original source hashes](evaluation/2026-11-04/subhan/original-source-sha256.json)
- Runner: [`tools/compare_leader_party_routes.py`](../../../tools/compare_leader_party_routes.py)

Local frozen artifacts are `.cambc/leader-party-validated.zip` and
`.cambc/leader-party-subhan-v1.zip`; controls also use `D1-compiled.zip` and
`gold_diamond-compiled.zip` in that directory. Replays referenced by the JSON files
are retained under `replays/leader-party/` locally and are Git-ignored.
The runner accepts `--maps` using names without `.map26a`, swaps sides automatically,
and takes `--controls` for both opponent comparisons. Its `--summarize` option reads
existing replays without repeating matches. Artifacts must be packed before running.

```powershell
.venv/Scripts/cambc.exe build leader_party_subhan --release
& bots/leader_party_subhan/tests/run.ps1
.venv/Scripts/python.exe bots/leader_party_subhan/tests/verify_translation.py
.venv/Scripts/python.exe tools/compare_leader_party_routes.py trial --maps 00monolith 00expanse
.venv/Scripts/python.exe tools/compare_leader_party_routes.py controls --controls --maps 00monolith 00expanse
```
