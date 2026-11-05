# Crossed-scope output index repair

Parent: `113090ec407067c28d18268d216700f60658288e`, base
`bots/pi_phase-profile-recovery-01/`. Candidate:
`bots/pi_phase-profile-recovery-02/`. All changes are confined to this
candidate and left uncommitted.

## Hypothesis and exact production diff

The output cursor reaches the first crossing at 41: nine scopes, 27 context
metrics plus entry fuel, then four status rows. Subtracting 40 selected
example 1 first and example `used` last. Subtracting 41 should emit the accepted
examples in order, from zero through `used-1`, without an out-of-bounds read
when all 16 slots are used.

The sole production change is in `src/phase_profile.h`, in `drain()`:

```diff
-                auto& e=store.examples[i-phases-context_count-4];
+                auto& e=store.examples[i-phases-context_count-5];
```

Every other production byte matches the exact parent, checked by the source
fixture and a directory diff. Default OFF declarations/hooks, phase mask,
capacity, collection/admission semantics, guards, output budget, gameplay and
pathfinding are preserved. No sampling or recovery optimization was added.

Read the inherited implementation report, current leader-party overview,
state machine and navigation/fuel strategy, and the actual profiler hooks and
C++ SDK round/fuel/actor interfaces. The repair does not change their contract.

## Exact test changes

- `tests/phase_profile.cpp`: extend the existing fake host with scripted fuel;
  add actual-header drain regressions for 0, 1, 16 and 21 crossings. Construct
  records through real `Scope` entry/close, vary the scope over all nine valid
  IDs, and give each record distinct start/end rounds and fuel. (Sixteen unique
  scope IDs are impossible with nine scopes; the full record identities are
  unique.) Parse each emitted crossing and compare all five fields with the
  independently constructed expectations, in order. Require exactly 42 plus
  accepted-crossing records: scopes, named contexts including entry fuel,
  status rows 0..3, crossings, exactly one final completion trailer. Require
  exact trailer counters, including five dropped records for overflow. Require
  exact actor/source/profile/mask/window tags and one newline per record.
  Require at most two records per drain and no later output, actor lookup or
  sampling after completion. Add fuel/round changes between the two output
  slots to verify guards on each record. Retain all previous early-window,
  active-scope, fuel-threshold, exception, invalid-sample, storage, histogram,
  admission and mask assertions.
- `tests/run_profile.py`: retain existing full/zero/subset-mask native cases,
  OFF preprocessing/token/empty-object checks, SDK syntax and real adapter
  checks. Add an undefined/bounds sanitizer build with fatal diagnostics.
  Compile the same fixture against the unchanged actual parent header from
  Git and require failure at the exact emitted-crossing-fields assertion.
  There is no duplicate formatter or expected-failure relaxation of the
  candidate checks; sanitizer build/runtime failures remain fatal.
- `tests/profile_preservation.py`: explicitly accept candidate name
  `pi_phase-profile-recovery-02` alongside the inherited profiling name, and
  add exact-parent production byte comparison allowing only the single index
  replacement above. Keep all ase01 gameplay-token and fixture-byte comparisons.

All other test files and the README are unchanged.

## Checks on Pi

Command from repository root:

```sh
python3 bots/pi_phase-profile-recovery-02/tests/run_focused.py
```

Environment: aarch64, GCC 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1).

Completed successfully (exit 0):

- All 292 recovery assertions and inherited protocol/state scenarios.
- Exact production-byte repair gate, inherited source/routing/scalar contracts,
  ase01 gameplay-token equality, and byte-preserved gameplay/revision fixtures.
- Actual current-SDK adapter: fresh epochs, stale scenes, revision rollover,
  coordinate conversion, move/dash/cancel/recall/attack transitions, planner,
  defense and host-error cases, both OFF and ON.
- Actual-header native profiler fixture with masks `0x1ffu`, `0u`, `0x155u`,
  including the new exact emitted-record regressions and all inherited cases.
- GCC `-fsanitize=undefined,bounds -fno-sanitize-recover=all`: available,
  compiled and ran successfully against the actual candidate header, including
  full capacity and overflow. No sanitizer diagnostics or skipped failure.
- Negative control: the unchanged actual parent header compiled successfully
  and failed the new exact crossing-fields assertion in the one-crossing case.
- OFF macros eliminate invalid arguments, OFF profiler object has no defined
  symbols, and compiler-preprocessed gameplay tokens equal exact ase01.
- All production translation units passed current-SDK syntax checks OFF and
  ON full mask, using inherited `-fpermissive` for SDK `team team()` declarations.
- `git diff --no-index --check` between base and candidate passed. Production
  directory diff contains exactly the single line shown above; repository
  status lists only this new candidate directory. No changes were committed.

## Gaps and PC handoff

No games, tournaments, uploads, challenges, ranked operations, SDK changes,
infrastructure changes, other-bot edits or policy changes were performed.
Native fixtures provide no fuel or strength evidence.

No WASI/Clang/wasm-ld toolchain was found in the checked system locations, so
an OFF WASM artifact was not built and its hash was not verified on Pi. Native
OFF token equality and an empty profiler object are supporting checks, not
artifact identity. PC must independently inspect the diff/native fixtures,
build OFF and require exact ase01 SHA-256
`b87eb8b98c9f2b70827515a16f7bbca22cbab874c72bb931a1b290d74d4846d6`
before ON. The authorized PC follow-up is exactly two ON Swirl/C02 games,
both sides, mask `0x1ffu`, collection rounds 1..100, stdout after 100,
safe-entry fuel >=40000 and maximum two records per call, reusing cached ase01
controls. No OFF games or standard80 run is requested by this repair.
