# rp01: fourth-pick Cassi/Issac with consistent routes

Parent: `d7fd040ad890bf9fd794340122ee975c5cb16550`.
Candidate: `bots/pi_roster-pair-01/`, cloned from `pi_roster-map-control-01`.
Changes are uncommitted for the bridge. No upload or ranked version 7 change.

## Hypothesis and scope

An additional independently controlled body may improve productive captures and
banking enough to offset foregone Ren, linked deaths and both lost bags,
congestion, and the cost of planning six bodies. The frozen leader sample motivates
this trial; selection frequency and individual contributions do not establish a
winning policy. This tests the retained executor rather than reconstructing leader
source. Extra bodies do not accelerate capture timers.

The parent's exact CLI5 release WASM was independently verified equal to champion
`a24ef0c56844e506694c48ed34e698c083a18fe7d9d74bf6c12ae355d1b448ac`.
Per the handoff, its initial adapter report omitted the bot field and produced a
`testing_failed` mailbox result; the corrected provenance receipt resolves this
reporting issue, which is not a bot failure. That identity was not reverified on
this Pi. No cd01, dp01, threat filtering, items or profiler changes are inherited.

Read the current leader-party strategy, routing, shopping and Subhan comparison
notes, champion/pair analysis and the checked-in C++ SDK's named draft/physical
enums, draft size/current picks, immutable champion stats and draft memory APIs.
The SDK explicitly describes the one-choice pair and linked death.

## Actual change

- `src/roster.h` retains the original preference list and derives the active list
  by swapping Ren with the final Cassi/Issac fallback. The complete active order
  is Heart, Marcella, Vesper, pair, Vendetta, Varg, Ryth, Stellar, Prism, Willow,
  Tavi, Ren. All choices remain unique.
- A pure `roster::plan(choice_count)` returns spans over static constexpr preference
  and expanded physical-template arrays. The existing named enum expansion remains
  the sole physical mapping; no second physical policy list or runtime expansion
  or allocation was added. Legal counts 3/4/5 produce actual prefixes of 3/5/6
  actors. Three-choice maps retain the original preferences and five-body route
  template (including unused Ren/Vendetta). Four/five-choice maps prepare Heart,
  Marcella, Vesper, Cassi, Issac, Vendetta, including unused Vendetta on four picks.
- `draft.cpp` queries the legal map choice count once per draft invocation and
  passes the same selected plan to route preparation. `route_plan.h/.cpp` accept
  that plan; route preparation makes no additional choice-count query. The SDK's
  existing `current_draft` implementation internally also reads draft rounds;
  it remains necessary to obtain completed picks, and was not replaced.
- Cassi joins Heart/Ren in the existing route caster estimate, matching her
  existing Focus shopping. Marcella and every other original actor keep their
  estimate. No shopping code changed.

The planner algorithm, ordering, knobs, damage formula, remaining-fuel share
formula and packet format are unchanged. Six planned bodies necessarily change
`(remaining fuel - reserve) / remaining bodies`, including each retained actor's
budget. This interaction prevents claiming a pure isolated body-count effect.
Type-owned packets, initial empty submission and progressive partial submissions
are preserved; runtime loading still matches physical type, independently of slot.

Only four production files differ from the parent bot: `draft.cpp`, `roster.h`,
`route_plan.cpp`, `route_plan.h`. Combat, movement/pathfinding, capture occupation,
coordination flag, priorities, healing/escape, banking, equipment, task expiry,
objective admission, planner implementation and telemetry are byte-identical.
No escort, partner observations/health policy, shared fields, map-name exceptions,
new logs or runtime death simulation were added.

## Focused Pi checks

Run from repository root:

```sh
python3 bots/pi_roster-pair-01/tests/run_focused.py
```

Passed on aarch64, GCC 13.3.0, Python 3.12.3:

- Real-SDK compile-time roster contracts: exact original/active picks, uniqueness,
  all named mappings, actual 3/5/6-actor prefixes, five/six-body expanded templates,
  explicit pair and empty expansions.
- Actual production draft/route function bodies compiled with deterministic host
  SDK substitutes. All twelve draft prefixes through exhaustion run on each legal
  map size, with one explicit size query per draft invocation and none in route
  preparation. The fixture now supplies six distinct camp IDs, allowing Cassi and
  Issac to own observably different routes without invalid mock camp indices.
- All original route actors' service estimates remain correct; Cassi is caster
  (66 fixture service turns), Issac and Marcella remain Strength (49). Fuel-share
  callback boundaries and integer remainder allocation are checked for five and
  six bodies. These service numbers use synthetic equal stats, not engine balance.
- Exact progressive production packet bytes: original template 210 bytes; active
  maximum `5 + 6*(2 + 3*(3 + 2*5)) = 251 < 1024`. Loader ownership is checked for
  all thirteen physical types at slots 0–5, including different Cassi/Issac routes.
  Missing Marcella/Cassi routes, interrupted output before Issac, existing partial
  prefix recovery, empty fallback, malformed bounds and truncation behavior pass.
- Inherited protocol/state scenarios pass. Geometry/protocol/state contracts pass
  55,294,203 assertions over 5,041 dimensions, 21,298,225 tiles, 116,964 centers
  and 1,176,588 requests.
- All 240 inherited differential planner cases match the exact Python reference
  at `97f761f`: rankings, route order, ties, scores and timing. Only compiler and
  generated-output paths are adapted in a temporary runner copy.
- Every production `.cpp` passes real checked-in SDK syntax checks using
  `-std=c++20 -O2 -Wall -Wextra -fpermissive -include cmath -fsyntax-only`.
  The inherited SDK needs permissive GCC handling for `team()` declarations and
  inherited sources need the build environment's cmath include. Existing SDK,
  indentation and optimizer warnings remain; warning-free compilation is not
  claimed. Generated files stay in temporary directories.

The former control-only comparison against the unchanged original producer was
removed from the runner because active policy intentionally differs. Three-choice
original policy/template expectations remain explicit in the production fixtures.
Host geometry, engine metadata, fuel and planner outputs are substitutes, not an
engine simulator. The separate differential check runs the real planner. No
mocked check establishes linked deaths, live timing, engine counterfactuals or
strength. No runtime death logic was changed to pretend to test linkage.

## PC release screen and unverified coverage

No cambc CLI is installed on this Pi. Exact-source CLI5 release build/current
engine3, release WASM hash and actual gameplay exposure remain for the PC. Native
correctness passed; release acceptance is pending. Keep normal fuel and require
zero candidate VM faults. Run the frozen standard 80 games: eight maps, five
frozen controls, both sides. The original champion's 64 common baseline remains
valid because the parent control WASM is identical.

- Reject if direct <8/16 OR common <31/64.
- Expand only if direct >=9/16 AND common >=35/64 AND active-map common >=25/40
  (baseline 23/40) AND active-map direct >=6/10.
- Otherwise inconclusive. Active maps: Ambush, Lanes, Swirl, Guardians, Colosseum.
  Inactive three-choice maps: Breadcrumbs, Packs, Broken Curve.

Release summaries/replays must confirm actual pair roster on active maps and no
pair on three-choice maps, both actors' economic and action participation, and
linked death/recovery where observed. Separate linked episodes by causal input,
not just shared round. Partner death while the other holds gems, and loss of both
bags, remain unverified here; report absent coverage explicitly if not observed.

Report paired team banking/captures/score; combined duo versus foregone Ren;
other retained actors; both bags lost in linked episodes; actor-round exposure;
first-100 and whole-game fuel; actual route entries where available; caught SDK
errors. Include every episode without conditioning on successful survival or
banking. Report inactive-map trajectory changes separately: compilation/query
cost effects cannot be attributed to pair benefits. Zero-bank tiebreaks do not
show delivery improvement. No economic, capture, death or fuel gameplay results
are available from this implementation session.

All 16 original confirmation maps were consumed by rejected cd01. Freeze any
later broad/confirmation design before results using genuinely new opponent/map
conditions and explicitly recording historical exposure; do not relabel those
16 conditions as fresh. No upload from this screen. Ranked version 7 stays
unchanged; interactions with rejected cd01/dp01 require their own experiment.
