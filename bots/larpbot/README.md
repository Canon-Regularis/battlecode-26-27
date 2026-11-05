# larpbot

Python competition bot built around a compact camp-clearing, capture, banking and respawn-safe loop. Current local champion is G3 (E51), which no longer recalls empty-handed champions at low health. The active policy uses the SDK's native distance-field navigation, prioritises Tavi/Varg/Ren in the draft, and takes a lethal basic attack against a gem-carrying enemy when available. The earlier persistent objective policy remains in `src/bot.py` for controlled comparisons.

## Build and run

```powershell
cambc build bots/larpbot
cambc run bots/larpbot bots/starter-python --map packs --statistics bots/larpbot/results/packs.json --out-dir replays/larpbot
```

The nine supported maps are `collision`, `corners`, `elkring`, `expanse`, `interlock`, `lanes`, `monolith`, `packs` and `rows`. Reverse the two bot arguments to run larpbot as Team B.

## Structure

- `src/main.py`: keeps the draft path lightweight and loads the gameplay policy after the picks finish.
- `src/simple_policy.py`: active starter-derived policy, shard purchasing, banking and known-respawn-tile evacuation; empty-handed low-health recall was removed in G3.
- `src/combat.py`: champion abilities, attack resets, and Varg splash-aware targeting.
- `src/bot.py` and `src/objectives.py`: previous persistent objective policy retained for comparisons.
- `src/draft.py`: deterministic Tavi, Varg and Ren preference with draft-memory metadata.
- `versions/`: preserved working snapshots; `00_starter` is the untouched starter source.
- `results/`: raw per-match statistics JSON.

See [EVOLUTION_STATE.md](EVOLUTION_STATE.md), [EVOLUTION_LOG.md](EVOLUTION_LOG.md) and [COMPETITIVE_BENCHMARKS.md](COMPETITIVE_BENCHMARKS.md) for current G3 evidence and next steps. [RAPID_UPGRADE_RESULTS.md](RAPID_UPGRADE_RESULTS.md) preserves the Stage 1 report. [STAGE1_RESULTS.md](STAGE1_RESULTS.md) and [STAGE1_RECOVERY.md](STAGE1_RECOVERY.md) retain the original baseline and recovery history.

## Competitive tracking

- [EVOLUTION_STATE.md](EVOLUTION_STATE.md): current objective, protected champion and next research step.
- [EVOLUTION_LOG.md](EVOLUTION_LOG.md): generation and experiment decisions.
- [COMPETITIVE_BENCHMARKS.md](COMPETITIVE_BENCHMARKS.md): summarized local map/side benchmark evidence.
- Rejected challengers are archived under `bots/archive/rejected_experiments/`; their replay bundles remain under `replays/`.

## Current manual package

`bots/larpbot_submission_final.zip` is built from the locally validated G3 source. It has not been uploaded.
