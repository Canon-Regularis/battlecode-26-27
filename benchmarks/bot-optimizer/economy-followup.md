# Recovered economy planner investigation

Complete measurements and source fingerprints are preserved in
[`economy-followup-results.json`](economy-followup-results.json) (**15 earlier runs**)
and [`economy-followup-final-results.json`](economy-followup-final-results.json)
(**8 final-stage reports**, including the unchanged specialization suite).
Together they cover 22 distinct completed runs. The earlier guarded/exploratory
archives remain separate and unchanged.

**Final whole-planner reduction versus original: 17.39% collision, 18.76% corners,
18.86–18.87% held-out lanes**, at raised fuel with equal work. Relative to the
compiler at the start of this investigation, collision/corners improve another
0.65–0.97%. This is planner-call fuel, not match fuel or a win-rate claim.

The input was copied without merging from `origin/feat/economy-strategy`, commit
`97f761f04ed3d3e85a6f2217df345629baab58c8`. It remains untracked and must not be
included in an optimiser commit. Production bot source is unchanged. Its folder
fingerprint is `950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c`,
exactly matching the recorded economy-v2 experiment. All 71 original bot tests
passed before this investigation.

## Current pre-investigation baseline

`replays/economy-recovered-current-baseline/results.json` contains two repeats,
both teams, collision/corners, release builds, raised fuel, and identical full
`SQUAD_LOOPS_DATA ` reports. The current guarded optimiser uses:

| Map | Original planner fuel | Current generated planner fuel | Reduction |
| --- | ---: | ---: | ---: |
| collision A | 1,358,254,434 | 1,129,426,818 | 16.8472% |
| collision B | 1,358,270,180 | 1,129,425,687 | 16.8482% |
| corners A | 4,213,032,489 | 3,456,076,452 | 17.9670% |
| corners B | 4,212,574,475 | 3,455,833,568 | 17.9639% |

All repeated samples match exactly. These are `DraftPlanner.build` boundaries,
not match fuel or win rates. Source equality and report equality alone do not
prove semantic equivalence; expansion counts and normal budgets are separate
validation work.

## Evidence provenance correction

The first run named `replays/economy-recovered-v2-baseline` accidentally imported
the current compiler: extracting only `tools/bot_optimizer` omitted the regular
package `tools/__init__.py`, and Python preferred the checkout's regular package
over the extracted namespace directory. Its six native attribute-key rewrites
exposed this error. That run is **not evidence of v2 reproduction** and is retained
only as an excluded exploratory artifact. The corrected driver extracts both
package paths and asserts that `compare.__file__` is inside the isolated snapshot
before benchmarking. Its fresh output is `replays/economy-recovered-verified-v2`.

The pre-investigation compiler is independently preserved in
`replays/economy-recovered-compiler-snapshot`, with source hashes and bot provenance.

## Investigation candidates

- Known exact frozen-record constructor calls: compare allocation plus dict
  replacement, direct stores and update against the current guarded initializer.
  A newly allocated, unexposed instance is different from arbitrary reinitialization;
  public initializer/subclass/finalizer fallbacks must remain intact.
- Generator reductions: native attribute maps, eager comprehensions, fused loops
  and column-layout conversion, including setup at sizes 0/1/8/32/128. These are
  manual hypotheses: descriptor callbacks, mutable aliases, floating-point
  accumulation and `StopIteration` prevent unrestricted compiler substitution.
- Cross-module return-shape inference from implementation rather than annotations:
  use proven SDK-returning wrappers to enable existing native mask operations.

Reproducible drivers:

```sh
uv run python benchmarks/bot-optimizer/economy_experiments.py --output <fresh-directory>
uv run python benchmarks/bot-optimizer/profile.py bots/economy-bot \
  --output <fresh-directory> --root-target draft_planner:DraftPlanner.build \
  --target draft_planner:DraftPlanner._collect_camps \
  --target draft_planner:DraftPlanner._prepare_data \
  --target planner:LoopPlanner.find_loops \
  --target planner:LoopPlanner.evaluate_loop \
  --target planner:LoopPlanner._calculate_loop_risk
```

Profile counters are inclusive and include nested instrumentation overhead. They
rank hotspots; they are not the final before/after measurement boundary.

## Reproduction and competing results

The corrected isolated v2 compiler reproduced **every recorded per-team sample
exactly**, both repeats: 13.6145–13.6179% collision and 14.4945–14.5005% corners.
Original and generated aggregate profiles both perform 6,020 evaluations on
collision and 20,000 on corners. Evaluation accounts for roughly 82% of current
instrumented planner fuel, risk for roughly 24%; map preparation is below 1%.

The completed manual suite has 47 candidates on both maps, including first calls,
five warmed batches, and setup/allocation in each measured call:

| Candidate | Baseline / alternative guest fuel |
| --- | ---: |
| Two/three-field direct-store factory | 1.23 / 1.50x warm; 1.08 / 1.23x first call |
| Four–twenty-field factory versus guarded initializer | 0.975–0.990x warm (rejected) |
| Nonempty column-layout conversion, setup included | 0.93–0.97x (rejected) |
| Native/eager/fused reductions, setup included | profitable in fixtures, insufficient general effect/type proof |
| Signed modulo-to-mask loops, sizes 8/128/4096, divisors 2/8/256 | 1.027–1.046x |

Fresh allocation permits direct stores without the reinitialization guard, but
only resolved, hook-free exact records qualify. Subclasses and public constructors
retain existing semantics. Class lookup and positional/keyword evaluation order
are retained. Imported field names are reserved before generating helper aliases,
including fields of records encountered later in the module.

`economy-small-record-raised` measures the accepted factory pass at the same
whole-planner boundary: **17.30% collision / 18.64% corners** versus original, both
teams and two reversed-order repeats, with matching ranked reports. Return-shape
inference leaves these generated economy modules byte-identical.

The initial seven-case generated wrapper suite measures records at 1.22–1.47x,
wrapped integer reductions/maps at 1.34–1.96x, and wrapped mask operations at
7.45–8.83x. These are kernel gains, not additional economy-planner savings.
The extended nine-case suite adds nested counters and signed modulo, both about
1.09x warm and first-call. Wrapper mask ratios are 7.42–9.09x warm and 4.79–5.49x
first-call in this combined build; snapshot/layout differences make them differ
slightly from the earlier seven-case build. The specialization suite retains the
earlier gains and the known subclass regression (0.9957x warm, 0.947–0.948x cold).

## Combined raised-budget measurements before allocator refinement

`economy-combined-raised` includes the factory and one expansion-counter modulo
rewrite; wrapper inference enables no additional economy rewrites.

| Map/team | Original fuel | Combined fuel | Reduction | Less than pre-investigation compiler |
| --- | ---: | ---: | ---: | ---: |
| collision A | 1,358,254,434 | 1,122,517,548 | 17.3559% | 0.6118% |
| collision B | 1,358,270,180 | 1,122,636,643 | 17.3481% | 0.6011% |
| corners A | 4,213,032,489 | 3,425,643,467 | 18.6894% | 0.8806% |
| corners B | 4,212,574,475 | 3,425,164,967 | 18.6919% | 0.8874% |

Both repeats reproduce their corresponding samples exactly and all full ranked
reports match. The modulo candidate saves only 0.058–0.071% against the
small-record-only build: useful but substantially smaller than its isolated
integer-kernel gain. Absolute costs include snapshot/allocation-layout effects,
so the entire incremental difference should not be attributed to one instruction.

Instrumented original/generated Python source totals are 39,165 / 49,967 bytes;
their Wasm bundles are 42,987,999 / 42,983,631 bytes. The pre-investigation
generated Wasm was 43,013,159 bytes. These sizes are provenance, not an optimisation
objective or an explanation for the measured savings.

`planner_differential.py` also passed **240 deterministic held-out host scenarios**:
zero through eight camps, zero through three altars, disconnected distances,
different beam/expansion caps, stop-callback cutoffs and risk profiles. Entire
returned records match with floating-point values compared as exact hex strings;
stop-callback counts match and input tables remain unchanged. These checks add
semantic coverage and make no guest-fuel claim.

### Held-out and normal-budget validation

Held-out lanes uses 4,202,084,642 / 4,202,809,623 original fuel and
3,413,222,535 / 3,413,181,296 combined fuel (teams A/B): **18.7731 / 18.7881% less**.
Both reversed-order repeats have identical corresponding samples. All archived
whole-planner engine replay payloads and nonmeasurement stdout match.

Exit-only observations of the existing search counter avoid adding per-expansion
instrumentation. Raised-budget original/combined counts match on both teams:

| Map | Raised original / combined | Normal original / combined |
| --- | ---: | ---: |
| collision | 6,020 / 6,020 | 64 / 88 |
| corners | 20,000 / 20,000 | 1 / 1 |
| lanes | 20,000 / 20,000 | 1 / 1 |

At normal budget the bot's preparation/search are fuel-aware. The extra collision
expansions are **different work**, not an equal-work fuel-saving measurement.
Corners and lanes perform only one expansion in these normal-budget runs, so the
raised-budget planner savings must not be extrapolated into normal-budget search
depth or match strength. Exit-only observed replay payloads match all three maps;
collision stdout differs because it includes the work counter. A separate
**uninstrumented three-round normal-budget** run has identical complete stdout
and replay payloads on every map. These are sampled trajectories, not universal
equivalence or win-rate claims.

### Semantic boundaries and remaining hypotheses

Return-shape facts come from straight-line source bodies across acyclic imports;
mutable list contents and annotation promises remain unknown. Stable module
integers and conservative loop recurrence types enable the mask rewrite without
trusting user-provided types. Signed integer modulo agrees with masking for these
positive powers of two. A function returning a constant divisor must still run;
the rewrite excludes such effectful divisor expressions.

Unrestricted generator fusion remains rejected: descriptors can change values
between accesses, aliases can mutate containers, `sum` has float-specific
accumulation, and generator `StopIteration` differs from native iterator termination.
Stronger whole-program ownership/field proofs might unlock these paths, but the
current planner annotations are not sufficient evidence. Custom native kernels
still lack an established supported mixed Python/native submission route; see the
prior runtime investigation. No custom-native gains are claimed.

## Reproduce combined checks

Each output path must be fresh:

```sh
uv run python -m tools.bot_optimizer.benchmark --suite wrappers --output <fresh-directory>
uv run python -m tools.bot_optimizer.benchmark --suite specialization --output <fresh-directory>
uv run python -m tools.bot_optimizer.compare bots/economy-bot \
  --target draft_planner:DraftPlanner.build --output <fresh-directory> \
  --maps collision,corners --repeats 2 --require-equal-prefix 'SQUAD_LOOPS_DATA '
# Repeat with --maps lanes for held-out fuel measurements.
uv run python benchmarks/bot-optimizer/normal_budget.py bots/economy-bot \
  --output <fresh-directory> --rounds 1 --fuel 1000000000 \
  --observe-local planner:LoopPlanner.find_loops:expansion_count
# Omit --fuel to observe work under the normal engine budget.
uv run python benchmarks/bot-optimizer/normal_budget.py bots/economy-bot \
  --output <fresh-directory> --rounds 3
uv run python benchmarks/bot-optimizer/planner_differential.py bots/economy-bot \
  --output <fresh-directory>
```

Combined-compiler checks: **117 optimiser tests**, **71 generated bot tests**,
240 differential scenarios, and dependency-lock validation pass. All 22 recovered
bot files remain byte-identical to their source commit and untracked; the index is
empty. No merge, stage, commit or push was performed.

## Additional allocator challenge

Before concluding, six further alternatives challenged the remaining fixed
`object.__new__` lookup in the accepted factory. Both maps agree:

| Alternative versus current generated code | Warm ratio | First-call ratio |
| --- | ---: | ---: |
| One-field direct factory versus ordinary constructor | 0.9250x | 0.9375x |
| One-field prebound allocator factory versus ordinary constructor | 1.0145x | 0.9858x |
| Two-field prebound allocator versus accepted factory | 1.0830x | 0.9916x |
| Three-field prebound allocator versus accepted factory | 1.0766x | 0.9904x |

Uncached manually spelled controls are 1.008x warm relative to the generated
factory, showing a small code/layout effect even without the proposed change.
The prebound two/three-field path is integrated as `record-allocator-cache`,
independently disableable. The one-field boundary remains unchanged because its
tiny warm gain is paired with a first-call loss. Larger-record factory and column
layout regressions remain rejected. The specialization fixture generates
byte-identical source after this refinement, so its completed measurements remain
applicable. The first 15-run archive preserves the pre-refinement compiler;
the second archive contains fresh whole-bot and wrapper measurements for the
cached candidate.

```sh
uv run python benchmarks/bot-optimizer/economy_experiments.py \
  --focus allocator --output <fresh-directory>
```

## Final accepted compiler

All three maps were rerun twice with reversed variant order after allocator
caching. Corresponding fuel samples repeat exactly; full ranked reports and
nonmeasurement stdout agree, and replay payloads match.

| Map/team | Original fuel | Final generated fuel | Reduction |
| --- | ---: | ---: | ---: |
| collision A | 1,358,254,434 | 1,122,035,640 | 17.3914% |
| collision B | 1,358,270,180 | 1,122,064,697 | 17.3902% |
| corners A | 4,213,032,489 | 3,422,587,769 | 18.7619% |
| corners B | 4,212,574,475 | 3,422,250,417 | 18.7611% |
| lanes A | 4,202,084,642 | 3,409,679,676 | 18.8574% |
| lanes B | 4,202,809,623 | 3,409,946,539 | 18.8651% |

Allocator caching improves the preceding combined planner build another
0.043–0.104%, depending on map/team. The final instrumented source is 50,057 bytes
and its Wasm bundle 42,988,823 bytes. Module helper binding happens during normal
snapshot initialization; call measurements include allocation but not preloading.

The final wrapper suite saves factors of 1.30x/1.55x for pair/triple construction,
1.51x with effectful keyword arguments, 1.35x for wrapped integer reduction, 1.96x
for wrapped native maps, 7.42–8.83x for wrapped mask operations, and about 1.09x
for signed modulo and nested counters. Cold samples are retained in the archive;
they are single first calls, not cold-start distributions. The dedicated allocator
comparison's ~1% first-call penalty remains documented rather than inferred away
from other fixture layouts.

Final raised/normal counter observations repeat the preceding table exactly.
Final uninstrumented three-round default-budget replay payloads and stdout match
on all three maps. All 71 final generated-bot tests pass; the 240-case differential
suite produces the identical observation hash from before caching. The 117-test
optimiser suite includes cached/uncached semantics and helper-name collision checks.

### Measured boundary and remaining opportunities

This investigation tested **53 manual alternatives** across allocation, reductions,
layouts and integer operations, then challenged its accepted allocator again.
The measured boundary is now narrow: extending factories to larger records loses
warm fuel; one-field caching has marginal warm benefit and a cold loss; column
conversion loses once setup is included. Removing further helper calls or fusing
the dominant planner reductions needs stronger ownership, field-type and effect
proofs than the current compiler establishes. These are future analysis work,
not gains justified by the current measurements. Custom native linking remains
unsupported by the investigated public build/submission path.

The remaining hypotheses do not justify broadening the default transformations.
This is a measured local boundary for the tested approaches, **not proof of a
global optimum**. The accepted passes remain generic and independently ablatable;
no bot names, strategy rules, expected outputs or map names enter the compiler.
