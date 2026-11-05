# ppfx01 diagnostic — research only; never upload

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, fresh copy of
`leader_party_tuned`. No preceding candidate inherited. This experiment locates
execution pauses; it does not optimize or claim improved performance/survival.

The supplied Fish evidence associates seven of eight early deaths with a recent
same-actor pause, without establishing causation. Existing local Swirl controls
reproduce pauses without early deaths. Repeated camp queries, retreat ranking,
and ability masks remain hypotheses, not conclusions. Pi cannot inspect the
PC's uncommitted evidence caches.

## Actual change

`src/phase_profile.h` implements a fixed-storage RAII profiler. Only additions to
existing gameplay code are its include, scopes at the eleven requested function
entries, and a drain after the existing main-loop try/catch, before `end_turn`.
Policy, SDK, observation invalidation, action order, stale guards, recovery,
priority, and pathfinding bodies are unchanged. No context queries were added.
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
comparison diverges too far. Each VM has independent storage/IDs; use the engine
log's actor identity, not a shared scope ID, to group records.

Each line starts `PPFX ` followed by a JSON array. Schema:

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

If CLI5 does not expose compiler flags, activate the source default on the PC
with this exact PowerShell command (OFF is the delivered source):

```powershell
$p = 'bots/pi_phase-profile-01/src/phase_profile.h'
$s = [IO.File]::ReadAllText($p).Replace('#define PPFX_ENABLED 0', '#define PPFX_ENABLED 1')
[IO.File]::WriteAllText($p, $s, [Text.UTF8Encoding]::new($false))
cambc --version
cambc build pi_phase-profile-01 --release
```

Use the PC's verified CLI5 executable/environment for both OFF and ON. The
checkout pins CLI4, so do not assume `uv run --locked` supplies CLI5. Revert only
the above literal 1 to 0 for OFF. Capture the actual compiler command and hashes
for each build, including an edited header/mask. `SOURCE_SHA256SUMS` lists the
SHA-256 of all delivered candidate src files (including untouched files); the
report and manifest do not hash themselves.

## Pi checks and remaining PC protocol

Result: `python3 bots/pi_phase-profile-01/tests/run_profile.py` passed on Pi,
including the ON/OFF tests, phase-mask test, SDK syntax checks with the native
workarounds below, OFF token comparison, and existing decision scenarios. A
separate isolation check reproduced every original candidate file byte-for-byte
after removing only the diagnostic includes and invocation lines.

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
The output adapter itself is syntax-checked, not fake-engine tested.

PC must review candidate-only isolation and build OFF under CLI5. Record source,
compiler, WASM, engine, map, and seed identities. Aim for champion OFF WASM identity;
if it differs, compare source and engine trajectories with the frozen champion
before interpreting ON. Build ON separately. Initial fixture: 00swirl, both sides
against frozen C02, normal fuel, identical engine/map/seed. Compare original and
traced first-100 fuel events, collection completeness/drop counts, deaths, and
same-actor chronology. Report divergence and missing evidence. Reduce phase tags
if perturbation is too large; shifted locations alone are not truth. No 80-game
strength screen, uploads, ranked changes, SDK edits, or optimization in this job.
