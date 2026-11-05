# ppfx02 diagnostic — actor-attributed profiler records

Parent: `6d5546f5817282fcc70b9d5d8a0ad3f80d45413f`; copied from
`pi_phase-profile-01` into `bots/pi_phase-profile-02/`. Research only; never upload.

## Hypothesis and correction

The official local ZIP `team-a.stdout` merges raw team output with NUL separators
and no textual actor label. Independent champion VMs reuse scope IDs, so ppfx01
records cannot establish ownership or safely deduplicate crossed copies. Adding
the actual public champion handle to every record makes actor+scope grouping
possible without inferring ownership from ordering, slots, names or replay data.
This is a data-contract correction, with no optimization or policy change.

Only production source change: enabled output tagging in `src/phase_profile.h`.
Each safe-point drain reads `cambc::self()` once, after the existing no-scopes and
final-sent early returns, casts through `cambc::handle_champion_t` to unsigned,
and passes that local identity to every event, cross copy, summary and trailer.
The SDK exposes this authenticated cached handle without a hidden observation or
new host query per line. Identity is never sampled in scopes. No profiler storage,
event IDs, masks, thresholds, collection window or drain limits changed.

The inherited runner hardcoded the parent bot directory; it now resolves its own
candidate directory so checks actually cover ppfx02. Added a minimal test-only
SDK surface and an output-contract fixture that executes the production drain.
No unexpected production changes were required. All changes are candidate-local.

The following describes the preserved profiler behavior and updated contract.

## Preserved profiler

`src/phase_profile.h` implements a fixed-storage RAII profiler. Only additions to
existing gameplay code are its include, scopes at the eleven requested function
entries, and a drain after the existing main-loop try/catch, before `end_turn`.
Policy, SDK, observation invalidation, action order, stale guards, recovery,
priority, and pathfinding bodies are unchanged. The actor handle read is confined
to the enabled safe point.
Draft has no tags. Recursive movement has distinct scope IDs. Enabled parents
are the nearest enabled enclosing scopes when a mask excludes intermediates.

Default `PPFX_ENABLED=0` preprocesses away all diagnostic expressions, SDK calls,
state, includes, output strings, and allocations. Scope invocation macros include
their own semicolon so OFF leaves no extra empty statements. Native preprocessed
OFF tokens are compared with every frozen champion translation unit by the test
script. This is source evidence, not proof of WASM binary identity: compiler,
source paths, metadata, layout, and build inputs can affect that hash. Pi has no
WASM toolchain or CLI5, so binary identity and trajectories remain PC gates.

ON: each scope samples round/fuel/round on entry and exit. Checking both rounds
brackets fuel sampling against suspension during the instrumentation itself.
Only stable, valid, same-round samples with nonincreasing fuel contribute costs.
Crossed scopes have no numeric cost; their raw fuels are never subtracted.
Fuel increases in a stable round and failed samples are invalid, counted
separately. RAII preserves exceptions and suspended stacks: IDs and parent IDs
live on the original stack, and destructors label exception unwinding. Diagnostic
sampling catches its own SDK exceptions and never replaces a policy exception.

Storage is fixed: 512 FIFO events, 128 separately retained crossed-scope exits,
and 11 aggregates with 18-bin inclusive cost histograms. Queue overflow drops new
events; crossed copies have their own overflow count. Every accepted entry
contributes calls/open; every exit decrements open and updates its aggregate even
when individual records are dropped. No heap, formatting, strings, or output in
the profiler scopes. SDK wrappers may themselves allocate on an exceptional
error path. There is no runtime control.

Collection accepts gameplay rounds 0 through 100 inclusive (draft excluded).
The first observed round above 100 closes admission permanently; admitted scopes
still finish and mark crossings beyond the collection boundary. Later calls
return without sampling. Costs are inclusive, including nested instrumentation;
**do not sum phases as exclusive totals**.

## Output / perturbation / termination

The bounded safe point is after gameplay dispatch and its exception handlers,
before the existing `end_turn`. It emits at most eight numeric JSON-array records
per dispatch, checking round/fuel/round before each and requiring at least 40,000
fuel. This is also used during collection so pre-100 deaths can leave evidence.
It never yields explicitly or changes an action, but can itself suspend, exhaust
fuel, shift later rounds, allocate in libc output buffering, or change engine
chronology. No safe-point cost bound in engine fuel has been measured. Its
40,000 threshold is an admission guard, not a guarantee. ON matches are not
release-performance evidence. Disable tags with the compile-time mask if the
comparison diverges too far. Obtaining identity and draining still have
instrumentation cost, even though the SDK handle is cached. Each VM has independent
storage/IDs; group records using their explicit actor ID.

Each record is `PPFX <actor_id> [existing numeric array unchanged]`, followed by
a newline. `actor_id` is the decimal unsigned public champion handle, not a
champion type or team slot. The prefix applies to **all kinds 0 through 4**.
Example: `PPFX 17 [0,1,0,2,1,1,100000,100000,0]`.
The raw team stream may contain NUL separators: treat those as stream separators,
not ownership information. Group within a match/team stream by explicit actor
and scope ID; missing labels must never acquire invented ownership. Schema:

- Kind 0 entry / 1 exit / 2 retained crossed-exit duplicate:
  `[kind,id,parent,phase,startRound,endRound,startFuel,endFuel,flags]`.
  For entries, endRound is the second entry round sample and both fuels are the
  entry fuel. For exits, endRound is the second exit round sample.
- Flags: bit 1 crossed round; bit 2 exception unwinding; bit 4 invalid sample
  or same-round fuel increase; bit 8 scope was still open beyond round 100.
  Invalid clocks cannot establish a crossing. Raw zeros may mean failed sampling.
- Kind 3 final phase aggregate:
  `[3,phase,calls,same,cross,invalid,open,sumCost,maxCost,h0,...,h17]`.
  Histogram h0 covers costs 0–1; hi covers `[2^i,2^(i+1)-1]` for i=1..16;
  h17 covers everything >=131072. Costs are unsigned 64-bit values.
- Kind 4 final trailer:
  `[4,acceptedScopes,droppedEvents,droppedCrossCopies,clockErrors,parent]`.
  The trailer is emitted once, only after the FIFO, crossed copies, and all phase
  summaries have drained. Retained kind 2 copies duplicate kind 1 when both survive;
  deduplicate by actor and scope ID. Summary counts never double-count copies.

Phase IDs: 0 play_turn, 1 World::init, 2 observe (including cache hits),
3 World::refresh, 4 shop, 5 choose_camp, 6 camp_action, 7 fight,
8 defend_cast, 9 move_to, 10 retreat.

An entry without a matching exit is **unfinished at available trace termination**,
not a zero-cost call or proof of exhaustion in that phase. Children can indicate
where a suspended parent was executing. Dropped records can also cause unmatched
entries; without a complete trailer, loss is unknown. A trace without kind 4 is
incomplete. Death/game termination can prevent draining the queue, including an
exit already recorded in memory. A scope that never returns cannot emit its exit,
and a VM that never reaches another safe point may emit nothing. These limits
are explicit; absence of trace is not absence of pauses. Final aggregates and
cross copies are unavailable if termination prevents post-window draining.

## Activation and hashes

One switch: source default `#define PPFX_ENABLED 0` in `src/phase_profile.h`.
Compiler flags `-DPPFX_ENABLED=1` and optional `-DPPFX_PHASE_MASK=0x7ffu` override
it. Bit i enables phase i. Example narrow mask `0x401u` enables play_turn+retreat.
Masked-out phases perform no clock calls. All tags default enabled when ON.

On PC, keep the source default OFF and build ON using CMake compiler flags
`-DPPFX_ENABLED=1` (and optional mask). Use separate build outputs and capture
the actual compiler command and hashes. Use the verified CLI5 environment for
both builds; the checkout pins CLI4. `SOURCE_SHA256SUMS` lists all candidate src
files, including untouched ones; the report and manifest do not hash themselves.

## Pi checks and remaining PC protocol

Result: `python3 bots/pi_phase-profile-02/tests/run_profile.py` passed on Pi,
including the ON/OFF tests, phase-mask test, SDK syntax checks with the native
workarounds below, OFF token comparison, actor output contract, and existing
decision scenarios. Candidate source isolation was checked against ppfx01: only
`src/phase_profile.h` differs; all other inherited source files are byte-identical.

The script exercises the
actual profiler template with a fake clock, not a rewritten model: bounded FIFO,
full capacity/drop counts, cross-copy overflow, same-round arithmetic/histogram,
nested parents, unwinding, round reset, unstable sample, failed sampling, open
count, cutoff, phase mask, and OFF macros with undefined argument tokens.
It also compares all OFF preprocessed translation units to champion tokens,
syntax-checks all translation units OFF and ON with the real SDK, and runs the
existing protocol/state decision scenarios. Native GCC needs `-fpermissive` for
existing SDK `team()` declarations and forced `-include cmath` for existing
`std::ceil` uses; neither source nor SDK was changed to address those portability
issues. No WASM build, engine execution, or output-fuel calibration on Pi.
The added output-contract test runs the actual enabled adapter against a minimal
public SDK stub, using two simulated VMs with handles 17 and 4294967295 and reused
scope ID 1. It checks every exact numeric array for entry, crossed exit, retained
copy, all eleven summaries and trailer, plus every actor prefix. C++ assertions
verify no identity reads in scopes or early returns, one per drain, the unchanged
40,000 guard and eight-record limit. This does not emulate engine suspension,
libc interleaving or the official merged ZIP stream.

PC must review candidate-only isolation and build OFF under CLI5. Record source,
compiler, WASM, engine, map, and seed identities. Require original frozen OFF
WASM identity; investigate any differences before interpreting ON. Build ON
separately. Initial fixture: 00swirl, both sides
against frozen C02, normal fuel, identical engine/map/seed. Compare original and
traced first-100 fuel events, collection completeness/drop counts, deaths, and
same-actor chronology. Parse by actor+scope ID and require complete trailers per
actor, or explicitly mark missing/overflow evidence. Report divergence and missing
evidence. Reduce phase tags if perturbation is too large; shifted locations alone are not truth. No 80-game
strength screen, uploads, ranked changes, SDK edits, or optimization in this job.
