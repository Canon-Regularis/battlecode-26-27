# C++ leader-party replacement

Build from the workspace root:

```powershell
uv run --locked cambc build leader_party --release
uv run --locked cambc run leader_party starter-python --map 00monolith --release
& bots/leader_party/tests/run.ps1
```

See the [strategy](../../docs/strategy/leader_party/README.md),
[measured results and limitations](../../docs/strategy/leader_party/implementation_results.md),
and [benchmark harness](../../tools/benchmark_leader_party.py).

The release uses local distance routing. Experimental shared guidance and ATTACK
rallies are disabled after matched evaluation. Adjust `src/config.h` for experiments;
benchmark a newly built artifact before adopting a configuration.

The prior bot is preserved separately in `bots/archive/`. This bot uses the workspace
SDK without modifying it. Build outputs and replays stay ignored by Git.
