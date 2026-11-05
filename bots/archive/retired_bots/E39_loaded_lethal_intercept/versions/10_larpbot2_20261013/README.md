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
