# leader_party with Subhan's loop planner

Preferred variant of `bots/leader_party` at commit `d8bd432`, following a 93–79
direct comparison across 86 maps. The advantage is modest and varies by map; the
original bot remains unchanged as a fallback. The draft picks, combat, movement/dash execution, shopping, banking thresholds,
recovery, shared protocol settings and optional wards retain the original policy.

The strategic route search is a C++ translation of SubhanAfz's `LoopPlanner` in
`bots/economy-bot/src/planner.py` at commit
`97f761f04ed3d3e85a6f2217df345629baab58c8` (`origin/feat/economy-strategy`).
Its SDK-independent search and score formula are in `src/loop_planner.*`.
The native BFS preparation and game integration are in `src/route_plan.*`.
This ports the route algorithm; it does not port the separate Python optimizer.

Adaptations to our current strategy:

- Plan for the existing Heart/Marcella/Vesper/Ren/Vendetta draft, independently
  acting champions and approximate post-opening damage, rather than one squad DPS.
- Use native terrain BFS for camp/altar distances and home-side exposure. Shortlist
  up to 24 camps and four altars under the first draft turn's actual fuel budget.
- Search with beam width four, at most five camps, 768 expansions and three routes
  per body, keeping the original score, respawn floor, opening cost and risk model.
- Store only bounded route IDs in draft memory. Fall back to the original selector
  if preparation runs out of budget or no valid route is available.
- Preserve original distance routing through the first two equipment phases. Then
  follow an independently staggered candidate loop, skipping unavailable,
  unreachable, over-budget or cooled-down camps using current personal observations.
- Advance a route when its task completes or is abandoned; keep existing danger,
  death, stall, bag-age and tribute rules. Banking still chooses the current best
  reachable altar rather than forcing a stale draft altar.

Static terrain distances allow routes through occupied camp spawn tiles; actual
movement continues to exclude current occupancy. Draft routes are guidance, not a
guarantee of survival, synchronized respawns, or a globally optimal farming cycle.

```powershell
uv run --locked cambc build leader_party_subhan --release
uv run --locked cambc run leader_party_subhan leader_party --map 00monolith --release
& bots/leader_party_subhan/tests/run.ps1
.\.venv\Scripts\python.exe bots/leader_party_subhan/tests/verify_translation.py
```

The differential test retrieves Subhan's two original SDK-independent modules from
local Git history and compares 240 fixed generated scenarios, including exact ties,
unreachable legs and expansion cutoffs. It checks ranked routes, scores and timing.

See [head-to-head evaluation](../../docs/strategy/leader_party/subhan_comparison.md)
for the frozen-artifact match results and limitations. This clone has not replaced
or been submitted over the original production bot.
