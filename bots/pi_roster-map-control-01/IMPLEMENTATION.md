# rm01: shared draft-to-physical roster control

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, `leader_party_tuned`.
Candidate: `bots/pi_roster-map-control-01/`. Changes left uncommitted.

## Hypothesis and implementation

A single ordered draft policy with explicit physical expansion removes the risk
of selecting an actor without preparing its route when a later experiment changes
the roster. This control hypothesizes unchanged behavior; it makes no claim of
roster strength or causal gain from the sampled Cassi/Issac teams.

`src/roster.h` owns the original twelve-choice preference order. Named enum cases
map all twelve draft choices to all thirteen physical types; Cassi/Issac expands
in that order. No enum casts connect these distinct SDK enums. `choice_prefix<N>`
and `expand<Choices>` produce exactly sized constexpr arrays. The route template
is the expansion of the first five choices, with no runtime expansion, allocation,
SDK queries, registry, role system, variant or flag.

`draft.cpp` iterates those preferences. `route_plan.cpp` obtains its existing
five-element type array from the module. Its loop body is untouched, including
the five-body denominator in each remaining-fuel share, Heart/Ren-only caster
estimate, damage formula, planner inputs, type-keyed serialization, initial empty
packet, incremental submissions and existing diagnostic output. All five routes
are still attempted on three/four-choice maps. The pair remains the twelfth
fallback draft preference; it has not been moved into the five-choice template.
No new logs or live ally/partner reads were added.

Of the 33 inherited files, 31 are byte-identical to `leader_party_tuned`; only
`src/draft.cpp` and `src/route_plan.cpp` changed. Shopping, team-size handling,
combat, navigation/pathfinding, runtime priorities, protocol and bank thresholds
are unchanged. No cd01, dp01, profiler or shopping experiment was inherited.

Read the current leader-party strategy, routing/shopping notes, Subhan planner
comparison, SDK compatibility notes and authoritative C++ enum/draft/memory APIs.

## Focused checks on Pi

Run from the repository root:

```sh
python3 bots/pi_roster-map-control-01/tests/run_focused.py
```

Environment: aarch64, Ubuntu GCC 13.3.0, Python 3.12. All generated sources,
executables and Python reference files are placed in a temporary directory.

- Real-SDK compile-time contracts: all named mappings, explicit pair expansion,
  unchanged twelve-choice ordering, five-body template, uniqueness, three/four/five
  prefixes, empty expansion, and explicit pair fixtures yielding 3/5/6 actors.
- Production-consumer fixtures: compile the actual draft and route source bodies
  with only includes replaced by deterministic host substitutes. Check all draft
  prefixes through exhaustion; five route actors and per-body damage/service
  estimates; remaining-fuel share callback boundaries; exact maximum-size control
  packet bytes (210); unchanged trailing preparation for three/four/five-choice
  inputs; initial empty fallback, skipped actor, and interrupted partial writes.
  Execute the production loader for all thirteen physical types and slots 0–5,
  verifying type ownership, missing routes, route count/length/camp bounds,
  invalid headers, and the existing truncation exception. Six-body maximum is
  `5 + 6*(2 + 3*(3 + 2*5)) = 251 < 1024` bytes.
- Compile and run the identical producer assertions against `git show` sources
  from the exact base commit; fixture output matches the candidate.
- Inherited protocol/state scenarios pass.
- Inherited geometry/protocol/state contracts pass: 55,294,203 assertions,
  5,041 dimensions, 21,298,225 tiles, 116,964 centers, 1,176,588 requests. Geometry
  bodies are extracted verbatim from production, as expected by that test.
- Existing 240-case planner differential passes against Python at `97f761f`:
  rankings, route order, ties, scores and timing. The runner changes only the
  Windows compiler/output/reference paths in a temporary copy of the test.
- All production `.cpp` files pass real checked-in SDK syntax checks with
  `-std=c++20 -O2 -Wall -Wextra -fpermissive -include cmath -fsyntax-only`.

The initial strict GCC syntax attempt failed on inherited SDK `team()` return
name declarations and the inherited route source's transitive `std::ceil`
include dependency. The successful native check uses `-fpermissive` and forced
`cmath`; no SDK or unrelated bot source was changed. Existing SDK name,
indentation and optimizer warnings remain; a warning-free build is not claimed.
The host fixtures substitute geometry/engine metadata and planner results, so
these checks do not establish live engine timing or WASM identity. The separate
planner differential executes the real search implementation.

## Frozen PC gate still required

No CLI/WASM compiler or frozen champion artifact is available here. No WASM
release build, identity claim, tournament, upload, promotion or ranked change was
performed. The source/host checks do not complete the following PC acceptance gate:

1. Review this exact source and release-build with CLI 5/current engine 3.
2. Compare resulting WASM SHA-256 with original champion
   `a24ef0c56844e506694c48ed34e698c083a18fe7d9d74bf6c12ae355d1b448ac`.
   If identical, identity plus focused checks suffice; do not run an 80-game screen.
3. If different, run only the eight existing screen maps against C02 on both
   sides (16 matched games), normal fuel and zero VM faults: `00ambush`,
   `00breadcrumbs`, `00lanes`, `00packs`, `00swirl`, `01broken-curve`,
   `02guardians`, `03colosseum`.
4. Compare the original exact fixtures' rosters, scores, final round/input and
   non-fuel event fingerprints. Report fuel separately. Any changed trajectory
   requires diagnosis/revision before attributing a subsequent difference solely
   to roster changes; a win-count gate cannot substitute for this check.

A later pair variant must start from this exact reviewed control commit and use
its own frozen strength/mechanism gates. Current cd01 confirmation and dp01
rejection remain separate. Live linked-body behavior and fixture equivalence on
CLI 5/engine 3 remain unverified until PC review.
