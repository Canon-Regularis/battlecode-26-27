# larpbot

Python competition bot built around a compact camp-clearing, capture, banking and respawn-safe loop. The active policy uses the SDK's native distance-field navigation, prioritises Tavi/Varg/Ren in the draft, and takes a lethal basic attack against a gem-carrying enemy when available. The earlier persistent objective policy remains in `src/bot.py` for controlled comparisons.

## Build and run

```powershell
cambc build bots/larpbot
cambc run bots/larpbot bots/starter-python --map packs --statistics bots/larpbot/results/packs.json --out-dir replays/larpbot
```

The nine supported maps are `collision`, `corners`, `elkring`, `expanse`, `interlock`, `lanes`, `monolith`, `packs` and `rows`. Reverse the two bot arguments to run larpbot as Team B.

## Structure

- `src/main.py`: keeps the draft path lightweight and loads the gameplay policy after the picks finish.
- `src/simple_policy.py`: active starter-derived policy, shard purchasing, banking, retreat and known-respawn-tile evacuation.
- `src/combat.py`: champion abilities, attack resets, and Varg splash-aware targeting.
- `src/bot.py` and `src/objectives.py`: previous persistent objective policy retained for comparisons.
- `src/draft.py`: deterministic Tavi, Varg and Ren preference with draft-memory metadata.
- `versions/`: preserved working snapshots; `00_starter` is the untouched starter source.
- `results/`: raw per-match statistics JSON.

See [RAPID_UPGRADE_RESULTS.md](RAPID_UPGRADE_RESULTS.md) for the validated current build, full baseline comparison, rollback steps and local packaging command. [STAGE1_RESULTS.md](STAGE1_RESULTS.md) and [STAGE1_RECOVERY.md](STAGE1_RECOVERY.md) retain the original baseline and recovery history.

## Competitive tracking

- [EVOLUTION_STATE.md](EVOLUTION_STATE.md): current objective, protected champion and next research step.
- [EVOLUTION_LOG.md](EVOLUTION_LOG.md): generation and experiment decisions.
- [COMPETITIVE_BENCHMARKS.md](COMPETITIVE_BENCHMARKS.md): summarized local map/side benchmark evidence.
- Rejected challengers are archived under `bots/archive/rejected_experiments/`; their replay bundles remain under `replays/`.

## E39 evaluation

The only gameplay change is a lethal-carrier check before a loaded champion banks. The full nine-map/two-side matrix against G2, carrier hunter, altar denial and starter-python completed at `--fuel 100000` with zero faults. A separate 8-match E05A pilot brings the evidence set to 80 matches. E39 is retained as an unpromoted G2 matchup challenger: 11/18 vs G2, 7/18 vs hunter, 8/18 vs altar denial, 16/18 vs starter. It improves the G2 mirror and starter result, but does not improve hunter score differential; overall net secured gems trail E05A by 115. See the LARPBOT benchmark record for complete figures.
