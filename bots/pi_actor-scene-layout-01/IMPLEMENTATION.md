# asl01: recovery scene layout repair

Parent: `21f464db747069b7dc360710e5ddfc1bf2a49bc7`, base bot
`bots/pi_actor-turn-core-01/`. Candidate: `bots/pi_actor-scene-layout-01/`.
Changes are uncommitted and confined to this candidate. No games, tournaments,
uploads, ranked changes, infrastructure changes, commits or pushes were run.
No strength improvement is claimed.

## Hypothesis and SDK contract

The recovery adapter treated packed bitboard bytes as scalar cells. On 45x30,
`bitboard::linear_buffer_size()` computes `(45*30+7)/8 == 169`, and its vector
`export_linear_buffer()` allocates exactly that size. Capture requires 1,350
visibility and occupancy bytes, so the parent rejects this representation before
planning. Static masks and defensive masks also used the wrong representation.
Fixing construction should allow correctly admitted scenes; it does not establish
how many observed deaths this defect caused or predict competitive results.

Inspected the actual current `sdk/cpp/cambc.h`, including contradictory linear
span comments. Production now calls public `bitboard::positions()`: it allocates
an owned `std::vector<vec2>` using `count()` (`sdk_Bitboard_NumSetBits`), calls
checked `sdk_Bitboard_GetSetBits` with that vector's capacity, resizes to the
returned count, and returns the owned coordinates. This is a coordinate list of
set tiles, not packed bytes. Production uses no private imports, raw layout,
packed-bit decoding, or per-tile `is_set()` queries.

The distance-field vector export is a separate API allocating
`width*height*sizeof(uint16_t)` bytes and returning `width*height` uint16 values.
Its full compute and export remain unchanged.

Read the current leader-party state-machine and combat documents, strategy
overview, parent implementation report, and the public SDK's bitboards, fields,
vision, range masks, ability/action flags and checked host boundary.

## Exact changed files

Relative to the cloned parent:

- `src/recovery_sdk.cpp`: one checked `scalar` boundary obtains one public owned
  coordinate export, converts it, then checks reserve and full epoch. All six
  consumers use it: static blocked/spawn, dynamic visible/occupied, heal and basic
  attack masks. Static dimension admission now avoids integer overflow. A home
  field length check precedes cache publication.
- `src/recovery_tiles.h`: small pure test seam for dimension validation and
  coordinate-to-scalar conversion, shared with production.
- `tests/adapter_scene.cpp`: fixture including the actual production adapter and
  real public SDK, with explicit host mocks and the actual recovery planner.
- `tests/run_adapter.py`: compiles/runs that fixture; generates fail-fast stubs
  for host imports that SDK vtables link but the fixture does not exercise.
- `tests/run_focused.py`: includes the adapter fixture in the existing checks.
- `tests/source_contracts.py`: additionally verifies exact parent preservation
  and all six coordinate consumers, retained size guards and field export.
- `README.md`, `IMPLEMENTATION.md`: candidate check instructions and this report.

Every other production source/header, including `recovery.cpp`, `recovery.h`,
`recovery_sdk.h`, caller routing, pathfinding, ranking, prefix rules, recovery
latch, channel comparison, geometry/effects, quotas, defense policy, economy,
draft, service and bookkeeping, remains byte-identical to the specified parent.
Parent recovery scenarios and inherited state/protocol tests are unchanged.

## Admission, ownership and bounds

Dimensions must be positive and satisfy `width <= 16384/height` before export;
this avoids multiplying unsupported dimensions. Returned coordinate count must
be <=cells, and each x/y must be in bounds. Violations throw the existing
`Halt{Status::incomplete}`. No truncation, clamping or partial cache publication
is used. The pure helper creates exactly cells zero bytes and sets index
`y*width+x` to one. Empty/full boards become all-zero/all-one scalar arrays.
Duplicate valid records are idempotent and still count against the record cap.

For N cells and K exported coordinates, conversion costs O(N+K), with N and K
bounded by 16,384 for supported boards. Each mask owns N bytes. The SDK's owned
coordinate vector uses K*sizeof(vec2) bytes (8 bytes per vec2 in this SDK), so
conversion's coordinate/scalar payload is at most 147,456 bytes, excluding
allocator overhead, existing engine bitboards and other scene data. Steady
scalar terrain uses 2N bytes plus 2N bytes for the uint16 field; a dynamic scene
uses another 2N bytes for visibility/occupancy. Native allocation/time bounds
are not WASM fuel measurements. The SDK performs allocation inside positions()
before our returned-count validation; the public host contract bounds genuine
set-tile exports by map cells.

The export remains one checked query batch per mask (internally count/GetSetBits),
under the unchanged query quota. Conversion is outside endpoint, effect, ranking
and BFS loops. Reserve and epoch are checked after conversion, before a dynamic
scene or defensive mask can authorize an action. Existing preflight legality
checks remain. Masks are captured once and reused for scalar lookups; only the
actual self origin is cleared from occupancy afterward. Dynamic scene length
checks remain intact.

Static data is assembled locally and published only after both conversions and
full field/export complete, with the field length verified. A conversion that
fails or rolls over does not publish terrain. A completed static field/export
that spans a round is still published before the inherited epoch check, survives
that stale dispatch, and is reusable next round. Field admission uses the same
shared TurnBudget and full `compute`, with no `compute_to` change.

## Executed Pi checks

Host: aarch64, GCC 13.3.0. From repository root:

```sh
python3 bots/pi_actor-scene-layout-01/tests/run_focused.py
```

Passed: unchanged 292 recovery assertions; inherited protocol/state scenarios;
all production `.cpp` syntax against the actual checkout SDK; original
integration contracts; exact parent source preservation; new production adapter
fixture. SDK syntax uses C++20 and the existing GCC `-fpermissive` workaround for
SDK `team team()` declarations, without modifying the SDK.

The adapter fixture invokes actual production `LiveBackend::scalar`, `prepare`,
`capture`, `defend`, the real `recover` executor and pure planner. Its host mocks
store coordinate lists behind opaque board identifiers; they implement no
assumed engine bit packing. The SDK wrappers themselves are the checkout's real
code. Unimplemented host calls throw rather than silently succeed. Specifically:

- 45x30 and odd 5x3: actual positions() exports through the production boundary,
  plus exhaustive scalar comparison for empty/full/sparse lists with indices
  0,7,8,9, row boundaries and final cell. Pure production conversion is also
  checked directly against every scalar index.
- Negative x/y, x==width, y==height, too many coordinates, zero/negative/over-cap
  dimensions and multiplication-overflow-shaped dimensions reject. The exact cap
  is accepted. Unsupported dimensions are rejected before export.
- A real SDK vector `bitboard::export_linear_buffer()` allocates 169 bytes; an
  explicit parent-style length admission fixture returns incomplete. Host export
  fills only those 169 bytes; it never pretends the API returns scalar cells.
  Production coordinate capture returns 1,350 bytes per mask and reaches a valid
  actual planner selection, without removing scene size guards.
- Static blocked/spawn and dynamic visibility/occupancy are distinct. An occupied
  tile does not set its seven following neighbors; self alone is cleared.
  Recapturing changed mocked visibility/occupancy leaves the earlier scene and
  static terrain intact.
- Actual heal/basic range mask construction and conversion at distant row/end
  indices: ally (44,29) outside range while foe (43,29) is inside; moving the mock
  origin admits final-cell healing. Exact action flags still prevent issuance
  even when geometrical masks include a target. Post-conversion reserve failure
  in either defensive mask prevents action.
- Malformed coordinates, rollover during export, reserve exhaustion at export,
  and reserve exhaustion specifically at the post-conversion check reject both
  static masks and both dynamic masks, without later actions. Failed static
  conversion never publishes terrain. Exhausted shared field admission defers.
- Rollover during full static compute and during full field export both retain
  completed terrain and return stale. Next-round prepare reuses it with no new
  field or admission. Dynamic failures against that completed cache do not act.

The unchanged parent recovery scenarios use a scripted Backend and scalar
scenes: they exercise controller behavior, not SDK representation. The new
fixture closes that test seam using actual adapter and SDK wrapper code, while
still mocking engine data, native permissions, field values, fuel and rollover.
The field mock verifies full-compute invocation/default distance and counts;
it is not a second pathfinding implementation or an engine correctness proof.

Also executed the adapter fixture with AddressSanitizer and UBSan:

```sh
ADAPTER_CXXFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer' \
ASAN_OPTIONS=detect_leaks=0 \
python3 bots/pi_actor-scene-layout-01/tests/run_adapter.py
```

Result: passed, with no AddressSanitizer/UBSan finding. Leak detection is
disabled for this managed environment; this is not a leak check.

## Remaining limitations and frozen PC follow-through

No engine-linked/WASM build, match, replay, fuel measurement or strength test
was performed. Native checks cannot validate actual engine suspension, timings,
action legality or resource usage. The static-home greedy-detour limitation,
bookkeeping issues, economic owner, hidden threats, unsupported geometry/effects
and inherited policy limitations remain separate work. No economic core or
policy tuning is bundled. Excess deaths are not quantitatively attributed to
this single defect.

PC must review the exact diff and rerun the corrected actual-adapter fixture
before release, then the same eight development conditions: Swirl/Lanes/Elkring/
Guardians, both sides versus exact C02 WASM
`605207958ed3f3dc778f03b0b122dfa9c7469f09e19dd7b48c979a47532e73d7`,
CLI 5/current engine 3 build
`96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`.
No automatic 80-game expansion. Retain original construction gates: zero VM
faults, SDK error classification, real recovery activation, and same-turn motion
followed by health recall. Missing coverage remains incomplete. Compare outcomes,
resources, deaths and fuel with cached original and defective parent; reused
conditions are not fresh validation and there is no standalone win threshold.
The combined redesign and subsequent economic stage still require their own
frozen diverse strength evaluation. No upload/ranked authority is requested.
