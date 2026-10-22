# Python performance in cambc

Investigated on 2026-10-22 using the project's pinned **cambc 3.0.4**. These are
general Python/runtime findings, not an analysis of any particular bot.

Follow-up: [PythonSDKPatterns.md](PythonSDKPatterns.md) adds 72 paired SDK-driven
workloads across two maps, a reproducible probe, buffer-format findings and more
examples of optimizations that did not pay off.

## What actually gets compiled

The bundled runtime identifies itself as **CPython 3.13.7**, built for WASI with
**Clang 22.1.0-wasi-sdk**. Its reported `PY_CFLAGS` include `-O3`.

There are two separate compilation processes:

1. The interpreter and native bindings are built into Wasm using Clang/LLVM.
2. Bot `.py` sources are compiled to **Python bytecode**, then packaged with a
   preinitialized interpreter snapshot. Wasmtime executes that Wasm module.

Your Python loops are not translated directly into LLVM integer loops. Python
function calls, object allocation, attribute access and generator resumption
still have interpreter costs. CPython's adaptive specialization is active: a
warmed arithmetic loop showed `FOR_ITER_TUPLE`, `BINARY_OP_MULTIPLY_INT` and
`BINARY_OP_ADD_INT` instructions.

Consequently, optimize **Wasmtime fuel**, not desktop Python timing or an assumed
number of native CPU instructions.

The follow-up also confirmed that many bulk SDK operations delegate to engine
host imports. Their fuel savings are not simply guest C versus guest Python
instruction savings; measure the supported operation in the actual runner.

## Measured general patterns

The following are approximate **baseline fuel / alternative fuel** ratios, not
wall-clock speedups or guaranteed improvements for every input.

| Baseline | Alternative | Fuel ratio |
| --- | --- | ---: |
| Python accumulation loop over existing integers | `sum(values)` | 5.3–6.0x |
| `sum(abs(x) for x in values)` | `sum(map(abs, values))` | 2.4x |
| `sum(x*x for x in values)` | `sum([x*x for x in values])` | 1.2–1.35x |
| Build a list using a loop and `.append()` | List comprehension | 1.2x |
| Counting `while` loop with increment | `for i in range(n)` | 1.5x |
| Call a tiny Python squaring helper per element | Inline `x*x` in the hot loop | 1.55–1.6x |
| `min(values, key=lambda x: x*x)` | Manual minimum loop with inline score | 1.6x |
| `x**2` in an integer comprehension | `x*x` | 1.3x |
| Repeated `math.sqrt(x)` lookup in a loop | Bind `sqrt = math.sqrt` outside the loop | 1.16x |
| Repeated membership in a 1,024-element list | Membership in a prebuilt set | 224x on this input |
| `max(abs(p.x-q.x), abs(p.y-q.y))` | `p.chebyshev_distance(q)` | 2.6x |
| `board.shift_right(1)` allocating a result | `board.shift_right_into(1, scratch)` | 1.25–1.3x |

Interpretation:

- **Move iteration into native implementations when possible.** Built-ins such
  as `sum` and the SDK's native vector/board operations can avoid many Python
  interpreter steps. Not every standard-library function is native.
- **A native callback matters.** `map(abs, values)` was efficient;
  `map(lambda x: x*x, values)` was slower than the square comprehension because
  it still calls Python once per element.
- **Generators trade memory for execution overhead.** A comprehension can be
  preferable when the entire, reasonably small result must be consumed. Keep
  generators for large streams or useful short-circuiting; do not replace them
  indiscriminately in `any`, `all`, or searches.
- **Inline selectively.** Removing a tiny per-element helper can help a hot
  kernel; that does not justify removing useful abstractions everywhere.
- **Use the right data structure.** The large membership improvement is an
  algorithmic effect. It excludes set construction, and tiny collections need
  their own measurements. A deque also beat `list.pop(0)` in a queue test.

For board work, use masks, `count()`, `is_empty()`, `DistanceField`, and reusable
`*_into` buffers rather than expanding everything to Python objects. On a full
41x41 board, `len(board.positions())` cost hundreds of times as much fuel as
`board.count()`: it unnecessarily constructs 1,681 positions. This is a specific
dense-board comparison, not a universal multiplier.

Do not mutate SDK-owned cached masks to save allocations. For example,
`game_map.walls()` documents that callers should copy before mutation. Reuse
your own scratch objects instead.

## A particularly useful cambc feature: build-time tables

The bundled `cambc/_precompile.py` compiles sources, imports ordinary bot modules,
and leaves `main.py` unexecuted until the match starts. Wizer snapshots the
initialized state.

**Game-independent module-level calculations in ordinary modules can therefore
be performed during the build, without spending match-turn fuel.** A probe
recorded its module-initialization call stack and confirmed that it ran under
`cambc._precompile.prepare`; its precomputed table was available in the match.

For example:

```python
# tables.py -- initialized during the build in cambc 3.0.4
RADIUS_8_OFFSETS = tuple(
    (dx, dy)
    for dx in range(-8, 9)
    for dy in range(-8, 9)
    if dx*dx + dy*dy <= 64
)
```

```python
# main.py -- executed when the match starts
from tables import RADIUS_8_OFFSETS
```

Useful candidates include fixed neighborhoods, combinatorial tables and static
scoring data. Putting the same computation in `main.py` or calling it from a
turn function would spend runtime fuel instead.

Caveats:

- No game-state or map queries during preinitialization: engine imports are not
  usable there. Even seemingly static SDK data may lazily query the engine.
- Map-dependent planning belongs at match time, potentially during the larger
  draft budget.
- Build time and snapshot memory still matter; preparation has a two-minute
  execution limit. This is not permission for unlimited precomputation.
- This behavior is version-specific. Do not assume an older cambc release has
  the same preload behavior.

## Optimizations not to assume

- **Type annotations do not produce native integers.** Annotated and unannotated
  versions of the arithmetic test had identical function bytecode and identical
  fuel consumption. Keep annotations for correctness and tooling.
- **`--release` is not Python `-O`.** The release probe still reported
  `sys.flags.optimize == 0` and `__debug__ == True`. Ordinary assertions remain.
  Use `cambc.debug_block` for diagnostics that should not execute in release;
  put expensive diagnostic calculations inside its callable, not in arguments
  evaluated before the call.
- **Caching a bound method is not always faster.** Saving
  `append = result.append` used about 7% more fuel than direct `.append()` in the
  tested loop. Modern CPython specializes direct method calls.
- **`__slots__` is not a guaranteed fuel optimization.** Attribute reads were
  only about 1% cheaper in the probe, while constructing and discarding the
  tested slotted objects was about 26% more expensive. Slots may still be
  valuable for memory. This runtime reports `WITH_PYMALLOC == 0`, another reason
  not to transfer desktop allocation benchmarks blindly.
- **C-style bit tricks are not automatically wins.** For the tested small
  integers, `x >> 3` used about 11% more fuel than `x // 8`. Python operators
  have their own runtime implementations; LLVM is not optimizing this Python
  expression as if it were C. Only compare semantically equivalent operations
  for the actual input types.
- **Prebuilt `.pyc` files are not an optimization route here.** The preloader
  explicitly reads fresh `.py` sources and compiles them rather than trusting
  existing bytecode files.

## How the measurements were obtained

A temporary standalone bot ran 47 named probe cases, including reverse-order
rechecks. Most collection cases used 128 values. Each case was warmed with 20
calls, then measured across five batches, normally 40 calls per batch. The
reported value was the median batch fuel per call. Equivalent-result assertions
were included where applicable.

Tests used `--release` on the `collision` map. The fuel quantum was raised to
avoid suspension during measurement. Both teams ran the same probe; their
results matched exactly within each run. Rebuilds with different preinitialized
heap contents changed some allocation-heavy costs, hence the approximate ranges.
No production bot source was changed for these experiments.

For your own hot kernels, measure repeated calls with
`cambc.fuel_remaining()` before and after, outside `debug_block`, without printing
inside the measured region. Ensure the benchmark fits within a turn: suspension
and fuel replenishment invalidate a simple before/after subtraction.

## Version and source notes

- The tested executable was `.venv/bin/cambc` version 3.0.4. At investigation
  time, plain `cambc` on the shell PATH resolved to an older global 1.0.1 install.
  Use `uv run cambc` or the explicit virtualenv executable for these results.
- `cambc.toml` records SDK 2.1.6, and the 3.0.4 CLI warned that the project's SDK
  sources were older. They were not refreshed as part of this investigation.
- cambc-specific implementation evidence came from the executable's bundled
  SDK, particularly `sdk/python/cambc/_precompile.py` (`prepare`), the native
  binding declarations, and metadata read inside the actual Wasm guest.
- [CPython 3.13.7 WebAssembly build documentation](https://github.com/python/cpython/blob/v3.13.7/Tools/wasm/README.md)
- [Wasmtime fuel and interruption documentation](https://docs.wasmtime.dev/examples-interrupting-wasm.html)
- [Wizer snapshot implementation and overview](https://github.com/bytecodealliance/wasmtime/blob/v49.0.2/crates/wizer/src/lib.rs)
