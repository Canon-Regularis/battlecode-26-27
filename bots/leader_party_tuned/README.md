# Combined tuned leader-party bot

The preferred bot is `leader_party_tuned`, matching frozen **`g07_search`**. It combines the selected settings in one C++ bot using Subhan’s camp-loop planner. Original bots and every tuning generation remain intact.

Bank at **35 gems / 70 rounds**. Use beam width **8**, native field admission **30,000** and fuel reserve **5,000**. All selected settings live together in `src/config.h`.

```powershell
uv run --locked cambc build leader_party_tuned --release
& bots/leader_party_tuned/tests/run.ps1
```

See the [complete strategy and evaluation](../../docs/strategy/leader_party/config_tuning_all_stats.md). Submitted to CAMBC as version 7 after evaluation; see the [publication receipt](../../docs/strategy/leader_party/evaluation/2026-11-04/tuning/publication.json).
