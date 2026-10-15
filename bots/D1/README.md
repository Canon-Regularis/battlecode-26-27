# D1 — Map-and-Side Resource Challenger

D1.15 is the current locally validated Python challenger. It retains G3's compact clear, capture, bank, navigation and combat core, then chooses a measured draft order from public map geometry and the allied spawn region.

## Current evidence

Live leaderboard testing materially changes the assessment below. On 14 October 2026, active D1.15 v4 lost **0–25 maps** across five unranked groups against hello, Mite, Univardisty of Shingtonwash, procless and Nyxius. It averaged 273 submitted gems against 1,023. See [D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md](D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md) for scores, replay evidence and the D1.16 priorities.

The local evidence remains useful for regression testing, but it did not predict performance against current leading submissions.

At `--fuel 100000` (2,500,000 Python fuel per turn), D1.15 completed two identical 18-match matrices against G3:

- **16/18 wins** in each matrix.
- **17,985 submitted vs 15,394**, a **+2,591** differential.
- **19,558 collected**, 328 deaths and zero faults.
- The remaining losses are **Collision Team A** (916–1,026) and **Packs Team A** (816–1,036).

The unchanged repeat reproduced every team and champion statistic. Raw statistics are `results/d1_15-full-*.json` and `results/d1_15-repeat-*.json`; replays are under `replays/D1_15_full/` and `replays/D1_15_repeat/`.

The runner exposes no seed option. Rebuilding after source changes altered deterministic match initialization even on maps whose selected roster was unchanged. The 16/18 repeat is reliable for this frozen artifact, but it does not establish that D1 will win every future match or opponent.

## Draft policy

The active policy in `src/draft.py` uses map dimensions, wall count and the allied spawn bounding box. Depending on the case, it selects among:

- Tavi / Varg / Ren / Ryth / Vendetta.
- Cassi & Issac / Stellar / Tavi / Vendetta / Varg.
- Cassi & Issac / Varg / Vendetta / Tavi / Ryth.
- Cassi & Issac / Vendetta / Varg / Tavi / Ryth.
- Ryth / Cassi & Issac / Tavi / Varg / Stellar.

All inputs are public static map state. G3 remains untouched at `bots/larpbot`; no official upload or submission was performed.

## Build and run

```powershell
cambc build bots/D1
cambc run bots/D1 bots/larpbot --map rows --fuel 100000 --statistics bots/D1/results/manual-rows-A.json --out-dir replays/D1-manual
```

## Files

- `src/main.py`: active lifecycle entry point.
- `src/draft.py`: active map-and-side roster policy.
- `src/simple_policy.py`, `src/combat.py`, `src/randomness.py`: active gameplay core.
- `src/d1.py`: retained inactive source from the earlier independent D1 economy experiments; `main.py` does not import it.
- `versions/02_d1_7_map_roster/`: frozen 10/18 D1.7 source.
- `versions/03_d1_15_side_rosters/`: frozen 16/18 D1.15 source used for the repeated validation.
- [DEVELOPMENT_RESULTS_2026-10-14.md](DEVELOPMENT_RESULTS_2026-10-14.md): full development evidence and limitations.
- [D1_15_OTHER_TEAMS_REPORT_2026-10-14.md](D1_15_OTHER_TEAMS_REPORT_2026-10-14.md): 72-match carrier, altar, economic and starter evaluation.
- [D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md](D1_15_LIVE_LEADERBOARD_REPORT_2026-10-14.md): five live unranked groups and 25-map failure analysis against leading teams.
- [D1_16_HANDOFF_2026-10-14.md](D1_16_HANDOFF_2026-10-14.md): self-contained implementation and validation brief for the next development session, targeting at least a 20% live map win rate.
- [FAILURE_ANALYSIS_2026-10-14.md](FAILURE_ANALYSIS_2026-10-14.md): diagnosis of the original D1.
