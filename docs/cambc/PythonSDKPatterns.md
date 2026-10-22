# More Python patterns discovered through the SDK

Follow-up to [PythonPerformance.md](PythonPerformance.md), investigated on
2026-10-22 with **cambc 3.0.4**. This adds **72 paired workloads** tested on
`collision` (41x41) and `corners` (71x71), including actual champion gameplay
queries. Ratios below mean **baseline fuel / alternative fuel**: larger is better.

The reproducible probe is in [`benchmarks/python-fuel`](../../benchmarks/python-fuel/README.md).
Its [results.json](../../benchmarks/python-fuel/results.json) records both maps.
Production bot code and the installed SDK were not modified.

## Why inspecting the SDK matters

The SDK is not merely a collection of small Python wrappers. Its ABI declares
engine host imports for mask operations, geometry drawing, reachability and
distance fields. A supported bulk SDK call can replace an entire Python loop or
search. Some convenience functions, conversely, perform several queries and
allocate wrappers internally.

These are **guest-fuel comparisons, not CPU speedups**. Host-backed work can have
a different charging model from interpreted Python. The large ratios do not
mean LLVM optimized the equivalent Python algorithm into faster machine code.
All experiments use public SDK methods, not private fuel-control imports.

## 1. Keep spatial work in masks for longer

| Baseline | Alternative | Measured fuel ratio |
| --- | --- | ---: |
| Enumerate a dense mask and count positions also in another mask | `(a & b).count()` | roughly 340–720x |
| `[p for p in a.positions() if b.is_set(p)]` | `(a & b).positions()` | about 5–6x |
| Set precomputed tiles individually for a Chebyshev radius 3 | `draw_chebyshev(center, 3)` | 10–12x |
| Same, radius 8 | `draw_chebyshev(center, 8)` | 54–62x |
| Rebuild the static terrain union on every evaluation | Cache that union once | about 2.4–2.6x |
| Enumerate visible camps, check state, build an awake-camp mask | `vision.awake_camp_tiles()` | about 9–20x |
| Enumerate both teams' visible champions, then filter by team | `vision.champions(Team.ENEMY)` | about 4.5–6.5x in the tested positions |

The dense intersection workload used synthetic patterned masks; its huge ratio
is not a promise for checking two or three tiles. Camp/team query ratios depend
on the number and state of visible units.

The useful pipeline is **filter masks first, create Python objects last**:

```python
candidate_tiles = vision.champion_tiles(Team.ENEMY) & range_mask
for position in candidate_tiles.positions():
    ...
```

This is a prefilter, not a replacement for action legality checks. For example,
`Ability.valid_tiles()` describes casting range, not all visibility/occupancy
conditions.

For navigation, compute a static obstacle union once at match time, then add
current dynamic blockers to a new working mask:

```python
static_blocked = (
    game_map.walls() | game_map.holes() | game_map.altars()
    | game_map.spawn_region(Team.ENEMY)
)
```

The SDK already caches terrain masks, but repeatedly recomputing their union
still spends fuel. Never mutate those SDK-owned masks. Different unit/actions
may need different obstacle semantics, so cache the appropriate union rather
than assuming one universal mask.

## 2. Use the search primitive matching the question

| Question / baseline | Alternative | Measured fuel ratio |
| --- | --- | ---: |
| Python deque BFS for tiles reachable within 4 steps | `blocked.reachable_tiles(origin, 4)` | about 290–300x |
| Same, within 12 steps | `blocked.reachable_tiles(origin, 12)` | about 1,400–1,600x |
| Compute the entire distance field to read one tile two steps away | `compute_to` with that destination | about 1.9–2.8x |
| Compute the entire field when only distances within 3 matter | `compute(..., max_distance=3)` | about 1.8–2.6x |
| Four searches to find distance to the nearest of four goals | One multi-source search | about 6–7x |
| Build every optimal direction, then use the first | `next_move_from(position)` | about 1.86x |

The BFS baseline used eight-neighbour movement, a deque, flat byte storage and
predecoded obstacles. Complete reachable masks were checked for equality outside
the timed section. The SDK returned a bitboard; the Python version returned a
flat reachability array. Representation normalization was outside timing.

For distance to the **nearest** goal, combine goal tiles into one roots mask:

```python
goals = Bitboard()
for target in legal_goal_tiles:
    goals.set(target)
field.compute(blocked, goals, visited)
```

This computes nearest-goal distances, not a separate distance to every goal.
Likewise, a bounded or early-stopped search is only a substitute when the rest
of the field is not needed. `next_move_from` returns one direction; it is not a
drop-in replacement for every multi-tile movement planner.

Source-audit opportunity, not a separately measured whole-bot improvement:
`Champion.move_towards()` rebuilds blocker masks, constructs a field, searches,
materializes reachable positions and chooses a minimum on each call. Reusing
appropriate masks/fields can avoid work when their inputs really are unchanged;
calling a convenience method does not automatically reuse your previous plan.

## 3. Snapshot state once per decision

| Baseline | Alternative | Measured fuel ratio |
| --- | --- | ---: |
| Five `can_move` / `can_attack` / other state checks | One `me.state()`, then test its flags | 3.49x |
| `me.position().x`, then `me.position().y` | Fetch position once | 1.48x |
| Three separate `me.buffs()` calls | Capture one `BuffCollection` | 1.82x |
| Two `ability.is_ready()` calls | Share one `can_cast` query, retain per-ability property/cooldown checks | 1.99x |
| Five `ability.can_target_*()` calls | One `valid_targets()` snapshot | about 1.85–1.95x |
| Reacquire a champion and its abilities repeatedly | Retain the champion so its ability cache survives | about 3.3x |

For example:

```python
state = me.state()
can_move = ChampionState.CAN_MOVE in state
can_attack = ChampionState.CAN_ATTACK in state
can_cast = ChampionState.CAN_CAST in state
```

The SDK convenience predicates call `state()` themselves. `Ability.is_ready()`
also constructs a champion wrapper to check whether it can cast. The alternative
readiness check retained all three conditions: properties exist, cooldown is
zero, and the owner can cast.

**Lifetime matters:** refresh dynamic snapshots after actions or turns that can
change them. Do not cache live positions, health, vision or readiness forever.
Retained wrappers still provide live queries, but ability metadata/errors are
cached per wrapper: an ability captured while its enemy owner is hidden may
retain a visibility error. The safe wrapper-retention probe used self.

### Prefer flag APIs over constructing temporary flag sets

With a fixed mask prepared outside the hot loop:

| Baseline | Alternative | Measured fuel ratio |
| --- | --- | ---: |
| `bool(state & flags)` | `state.intersects(flags)` | about 2.1x |
| `(state & flags) == flags` | `flags in state` | about 2.7x |

`intersects` means **any** selected flag; membership means **all** selected
flags. These meanings were checked against empty, single-flag and combined
states. Avoid substituting one meaning for the other.

## 4. Match scalar versus batch access to the workload

- **One visibility check:** `vision.in_vision(p)` used about 1.5–1.9x less fuel
  than fetching a new visible mask and testing one tile.
- **Many visibility checks:** fetch one visible mask and reuse `is_set`. At 32
  checks this saved about 2.8–3.0x; at 128 checks about 3.4–3.5x. Fetching a mask
  for only one check was a losing alternative. Refresh it when vision changes.
- **Only need existence:** `vision.has_champion(p)` beat retrieving a wrapper by
  about 3.4x on an occupied tile and exception-based lookup by about 5.8x on an
  empty tile. If the object itself is needed, consider the cost of doing both a
  presence query and a successful retrieval; the boolean API is not universally
  a prerequisite to the object API.
- **Shared memory:** one eight-byte `read` saved about 3.25x versus indexing each
  byte; one `write` saved about 4x. Reuse a writable buffer for reads. The tested
  configuration exposed only **eight bytes total**: always check the actual
  size, rather than assuming a large communication buffer.
- **Known grid coordinates:** retain `Vec2` objects for repeatedly queried tiles.
  Avoiding per-query `Vec2(x, y)` construction saved about 3.1x in the distance
  lookup workload. Build map-sized tables after dimensions become available.

## 5. Distance-field bulk operations are useful, but exports need care

- `destination.copy_from(source)` beat a Python get/set loop over the entire
  field by about **120–180x**.
- `destination.copy_from(source, mask)` beat a per-selected-tile loop by about
  **43–63x** in the tested combined copy-and-patch operation. Unselected values
  are preserved; this is not the same as creating a zeroed field outside `mask`.
- `import_linear_buffer(array.array("H", values))` beat per-tile `set` calls by
  about **160–190x** when the typed data was already prepared.

However, **reusing storage is not automatically cheaper**. A fresh `source.copy()`
was about 2.5–2.8x cheaper than full-field `destination.copy_from(source)` in these
tests. Both beat copying tile by tile. Select according to the measured operation
and ownership needs, not a universal "never allocate" rule.

### Real runtime representations, not just stub annotations

The Python annotations/comments are misleading in a few places:

1. `DistanceField.export_linear_buffer()` returned a **typed `memoryview` with
   format `H`**, not plain `bytes`. For a 41x41 field, `len(view)` was 1,681
   elements and `view.nbytes` was 3,362 bytes. Index it by `y * width + x`.
2. That exported view was a **snapshot**, not live access to the field. Changing
   the field afterwards did not change the exported view.
3. Bitboard linear buffers were **packed bits, least-significant bit first**,
   not one byte per tile. The 41x41 board needed 211 bytes; the 71x71 board 631.
   For interop, tile index `i` lives in byte `i >> 3`, bit `i & 7`.

For distance queries, simply replacing `.get(p)` with indexing an exported
memoryview was **not faster**, even with many queries. Exporting first also adds
setup cost. For an unchanged field used repeatedly, converting once with
`field.export_linear_buffer().tolist()` produced a faster Python-list cache:
about **1.5–1.9x** for 128 prepared-index lookups, depending on values. The upfront
conversion must be amortized, and the cache must be invalidated after changes.
Rebuilding that list for a few lookups was much worse; even a complete scan of
the open-grid path distances did not justify rebuilding it in the tested workload.

Contract-based opportunity, not separately timed: avoid clearing an output
before an `*_into` method documented to overwrite it. Conversely, drawing
operations such as `draw_chebyshev` **add** tiles and require clearing when the
intention is to replace the old shape. Respect each method's aliasing rules.

## 6. Additional general Python patterns

| Baseline | Alternative | Measured fuel ratio |
| --- | --- | ---: |
| `min(points, key=lambda p: field.get(p))` | `min(points, key=field.get)` | about 3x |
| `min(records, key=lambda row: row[1])` | `min(records, key=operator.itemgetter(1))` | about 3x |
| Sort everything just to take the minimum | `min(..., key=...)` | about 2.3x |
| Repeated linear lower-bound searches in sorted data | `bisect.bisect_left` | about 31x on this input |
| Slice and decode 128 uint16 values individually | One `struct.unpack("<128H", data)` | about 42x |
| Call `unpack_from` for each fixed-size record | `list(struct.iter_unpack(format, data))` | about 2.8x |
| `struct.pack` each integer, then assign a bytearray slice | Cached `Struct.pack_into` | about 2.9x |
| Reconstruct dot/squared-length expressions through `Vec2` properties | `dot` / `length_squared` | about 1.4x |

The callback result refines the earlier finding about `min(..., key=lambda ...)`:
a Python callback can be expensive, but **a native bound method or native key
extractor can keep the entire iteration out of Python frames**. Do not assume a
manual loop beats every use of `min`.

For hot dictionaries keyed by live champions, public integer handles were also
useful. `ids[int(champion)]` saved about 1.4x versus SDK-object keys; retaining the
integer ahead of time saved about 2.9x in the microprobe. The SDK champion hash
builds a tuple internally. Keep entity kinds in separate tables or tag keys:
champion and camp handles need not share a unique namespace, and design objects
are not interchangeable with live handles.

An attempted mask optimization **failed**: converting SDK boards to Python big
integers and using `&`/`bit_count` was slower for the tested scoring workload,
even with conversion excluded; including conversion was much worse. Keep the
SDK representation unless an actual workload proves another representation wins.

## Verification and limitations

Each case had 20 warmups and five measured batches, normally 30 calls per batch.
The median batch fuel per call was recorded. Both teams ran the probe; gameplay
cases repeated across three champion instances per team on `collision` and six
on `corners`. Equality assertions and
representation checks ran outside timing. Raised fuel prevented turn suspension;
`--release` avoided debug-mode fuel exemptions. Both final maps completed all 72
paired workloads with no probe failures.

Ratios depend on data density, map size, allocation state, unit visibility and
whether setup is included. The table describes which setup costs were excluded
when that matters. This is a collection of measured candidates, not blanket
rewriting rules.

Implementation evidence came from the bundled 3.0.4 SDK: Python `vision.py`,
`Champion`, `Ability`, `BuffCollection`, `SharedMemoryBuffer`, and the C++
`cambc.h` / `imports.h` buffer definitions and host ABI. The workspace's SDK
stubs still identify as 2.1.6; newer methods such as `DistanceField.copy_from`
are available in the tested 3.0.4 runtime but absent from those old stubs.
