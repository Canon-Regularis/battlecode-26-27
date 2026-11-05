# sdw01 implementation — 5 November 2026

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, original `leader_party_tuned`.
Candidate: `bots/pi_safe-dash-wake-01/`. Changes are uncommitted. No match,
upload, challenge, selection, SDK, tooling, settings or other bot changes.

## Hypothesis and implementation

An otherwise safe chosen landing can damage a camp and wake a visible sleeping
sibling outside the landing stun radius but within that sibling's attack reach.
Rejecting that dash in favor of the already ranked ordinary step may preserve HP
or shield. This does not establish prevalence, survival, or net score benefit.

The only movement policy addition is at the selected safe, unconstrained dash.
`camp_topology.h` provides a pointer-sized, borrowed immutable World view. Its
optional membership result exposes identity containment and group identity only;
the private span refers to existing objective-group storage. The accessor in
`camp_topology_access.h` reads cached SDK `group.camps()` spans, with no host group
loader or second persistent cache. Missing membership is explicitly incomplete
and uses ordinary fallback. A visible witness takes precedence over incompleteness.
World initialization/sorting precedes all call sites. No World/group copying,
reallocation, deferred storage, or callbacks occur during movement. All camp,
guard, escape, carrier-protection, banking and exploration callers pass their
existing World, and retreat and constrained recursion forward the same view.

`dash_witness.h` captures one `vision::camps()` collection per safe mask, including
a single value-state read per camp. Living positions are recorded for witness
use; awake mask Strength/range are reused. Sleeping combat getters run lazily
only for visible out-of-radius members of deduplicated hit groups. Static hidden
identities are never used as live query handles. Awake or passive hit members
can trigger a sibling witness. Directly stunned, dead, passive, already awake,
and out-of-reach members are not witnesses. Positive modifier/current Focus and
positive stun duration define scope; zero modifier, zero current damage and zero
stun preserve the old dash decision (subject to epoch/action reserve).

Current Focus is queried to establish scope before witness admission, with epoch
and reserve checks around that query. Admission for the actual scan is the fixed
**15,000** fuel bound. As a conservative continuation rule, the scan also stops
if remaining fuel drops below that same bound after admission. This is an
implementation choice for the requested "runs short" ordinary fallback, not
fuel tuning or a measured cost estimate. Same-epoch fuel of 5,000–14,999 produces
`resource`; a visible threat produces `witness`; missing topology produces
`incomplete`. Each skips the dash and uses the existing ordinary best. Below
5,000 or changed epoch produces `deferred`, suppressing both dash and ordinary
action. New capture/query work checks epoch/reserve after each SDK getter and
before continuing; pre-field capture aborts before field construction. Retreat
checks epoch/reserve before its emergency fallback and again before action.

No alternate endpoint/field search was added. Field admission (30,000), quota,
mask geometry, goals, ranking/ties, improvement threshold, ready checks, action
priority and Memory transitions remain those of the parent. A veto changes no
Memory until the actual ordinary attempt. Existing retry uses constrained
movement and the same view. The existing blocked-yield action also receives an
immediate epoch/reserve check. No release diagnostic logs were added.

Read references: the supplied self-contained appendix; candidate README;
`docs/strategy/leader_party/{README,combat,config_tuning_all_stats}.md` and
`strategies/pathfinding.md`; relevant SDK camp state/getters, camp membership,
dash metadata, fuel and round wrappers. The older pathfinding prose has stale
55,000/10,000 constants; actual parent source and frozen tuned configuration
(30,000/5,000) were preserved. Linked PC research/protocol/replay inputs are
absent as stated by the task and were neither required nor fetched.

## Native fixture and results

`tests/run_native.sh` compiles the **actual production** `navigation.cpp`, full
`move_to` and `retreat`, and actual helper/topology accessor against
`tests/host/cambc.h`. It does not copy the predicate. The host facade has no group
loader API and throws on any hidden live camp query. Membership storage is
World-owned and view identity is checked against its actual backing address.

`tests/make_fixtures.py` transcribes all 22 topology groups and every supplied
visible camp's identity, group, position, alive/awake, Strength and attack range.
It includes recorded actor positions, Focus, HP and visible champion coordinates,
and selects one supplied zero-incoming legal ordinary option per case.
It writes reviewable JSON plus the native input stream. Camp HP is projected to
alive (every supplied HP is positive); exact unused HP, champion combat metadata,
request tokens, flags and cooldown arrays are omitted. For 985 the test gives the
actor 108 shield to demonstrate shield independence; the evidence says 108 shield
was consumed, rather than specifying an exact pre-action shield getter value.
The facade stores HP/shield but the production predicate never reads either.

The controlled route field presents the recorded chosen endpoint and legal
ordinary option; it does not execute a replay or reconstruct route distances.
The native fixture preserves 599's dash and uses an ordinary step for
864/985/1637/1646, with one field each. Geometry is the supplied Chebyshev geometry,
not injected witness flags. In 599 both living hit elk are inside radius 1; the
other two cases' elk and the carrier cases' damaging siblings provide actual
out-of-radius, in-range witnesses. The passive hit in 1637 is covered without
requiring the hit member itself to deal damage.

Controls cover all awake (the original safe mask blocks that synthetic goal),
pure passive, just beyond reach, exact reach and radius boundaries, no hit,
zero modifier, zero current Focus even below scan admission, zero stun, unsafe,
constrained, awake/passive hit members with sleeping siblings, hidden-only and
mixed hidden/visible members, duplicate hit members, multiple hit groups, and
explicit missing membership. Constrained/unsafe tests preserve their original
walking/dash behavior. Ordinary failure retries exercise two and three fields
under the original quota; ordinary success and no-route failure are checked.
Successful public movement also checks blocked reset and last-distance values.

There are 48 injected epoch/below-reserve failures: each of 12 new data-query
boundaries in an awake+sleeping mixed fixture, for both public movement and
retreat, with rollover or fuel 4,999. Each issues zero actions, stops querying at
the injected boundary, and early capture failures construct no field. Another
18 injections at witness query boundaries retain current epoch and 5,000,
10,000 or 14,999 fuel, and take ordinary fallback. Diagnostics explicitly assert
`resource`, `witness`, `incomplete`, and `deferred`; 15,000 admits the witness.
No temporary instrumented release binary substitutes for production evidence.

Native query diagnostics follow below. `mock_data_queries` counts facade calls,
not exact SDK host imports: vision collection is one aggregate operation in this
facade, while the actual SDK internally performs multiple host queries. The
printed round/fuel calls are separate bookkeeping overhead and are not included
in that data counter. Real camp state, position, Strength/range and champion
Focus getters each map to a host-backed wrapper query. Membership lookup itself
adds zero host calls. Relative to source-counted parent safe-mask getters, the
five cases add +1/+3/+2/0/-1 data getter calls respectively, excluding the common
vision collection, ready/action/field work and added round/fuel checks. Thus
reduced duplicate getters do not imply identical inactive trajectories or zero
incremental cost. No actual VM fuel consumption is measured.

## Commands, build limits and gaps

Environment: aarch64 Pi, `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.
Run from repository root:

```sh
sh bots/pi_safe-dash-wake-01/tests/run_native.sh
```

That script contains the exact commands: regenerate fixtures; compile/link/run
native fixtures with `-std=c++20 -O2 -Wall -Wextra -Werror`; compile/run existing
protocol/state scenarios; syntax-check every production translation unit against
the real SDK; and build SDK-facing navigation/bot/economy/objectives objects in
`/tmp`. SDK checks use `-fpermissive -include cmath -Wall -Wextra`: GCC rejects
three inherited SDK `team()` declarations without `-fpermissive`, and inherited
`ceil` uses rely on libc++ transitive includes. Initial strict GCC syntax checking
exposed these pre-existing portability issues; no SDK or unrelated bot changes
were made. Final syntax/object compilation passes with those accommodations and
existing SDK/parent warnings. Fixture compilation passes with warnings as errors.
Logs are `/tmp/sdw01-checks.log` and `/tmp/sdw01-syntax.log`.

The additional attempted command

```sh
g++ -std=c++20 -O2 -Wall -Wextra -Ibots/pi_safe-dash-wake-01/src bots/pi_safe-dash-wake-01/tests/strategy_contracts.cpp bots/pi_safe-dash-wake-01/src/loop_planner.cpp -o /tmp/sdw01-contracts
```

could not compile because the inherited generated `geometry-under-test.h` is
absent. This unrelated suite is not counted as passing. Existing protocol/state
scenarios pass. No WASI compiler/wasmtime is available here, so a final linked
WASM build remains a PC check; native real-SDK objects are compile evidence only.
Full Bot caller forwarding is SDK-compiled and source-reviewed, while dynamic
native dispatch tests cover movement, retreat and recursive retry, not the full
shop/combat/Bot engine lifecycle.

The facade mocks bitboards/field reachability, observation masks, legal actions,
combat, shields, channels/readiness and fuel. It uses a positive test dash modifier
of 2, radius 1 and stun 1. It does not model mitigation, camp wake timing, actual
kills, cooldown progression, VM suspension inside wrappers, or real incoming
combat damage. Resource injections cover returned data-query boundaries;
round/fuel getters are counted but not individually suspended, and internal
queries of aggregate SDK wrappers are not separately injectable here. Host
query counts and constant synthetic field fuel do not establish game fuel cost.
No full matches were run on Pi. PC must build/test exact returned source.

PC release evidence is outstanding: frozen original-parent screen of 80 games,
zero VMfaults, direct >=9/16, common >=35/64, common banking >=44,512,
losses <=2,352 and deaths <=548; diagnose newly repeated SDK errors. A failed gate
means no expansion. Swirl/C02 both-side earliest witness ordinary exposure must
be reconstructed and deterministically selected by round/actor/input, with
legal/actual ordinary action and subsequent HP/shield/fuel, clear/capture and bank
outcomes bounded. Native success is not release exposure or score gain. Resource
fallback exposure must be labeled separately; replay helper/fuel inference must
be identified. Track deaths, loss, banking, collection, suspensions, action mix
and duration. No expansion, upload or ranked change is authorized here.

## Final native output

```text
599: dash=1 ordinary=0 mock_data_queries=22 round_queries=61 fuel_queries=59 camp.position=10 camp.state=10 self.focus=1 vision.camps=1
864: dash=0 ordinary=1 mock_data_queries=30 round_queries=58 fuel_queries=56 camp.position=13 camp.range=1 camp.state=13 camp.strength=1 self.focus=1 vision.camps=1
985: dash=0 ordinary=1 mock_data_queries=38 round_queries=70 fuel_queries=68 camp.position=16 camp.range=2 camp.state=16 camp.strength=2 self.focus=1 vision.camps=1
1637: dash=0 ordinary=1 mock_data_queries=64 round_queries=114 fuel_queries=112 camp.position=26 camp.range=4 camp.state=26 camp.strength=6 self.focus=1 vision.camps=1
1646: dash=0 ordinary=1 mock_data_queries=66 round_queries=114 fuel_queries=112 camp.position=26 camp.range=5 camp.state=26 camp.strength=7 self.focus=1 vision.camps=1
synthetic query trace: vision.camps camp.state camp.position camp.state camp.position camp.state camp.strength camp.position camp.range self.focus camp.strength camp.range
admission: 14999=resource fallback; 15000=witness; 4999=deferred
PASS: controls, topology, hidden queries, retry and 48 resource/epoch injections, 18 current resource fallbacks
PASS protocol and state scenarios
```

## Source hashes

`SOURCE_SHA256SUMS` records SHA-256 for every production and test source,
including the generated fixtures. Verify from the candidate directory with
`sha256sum -c SOURCE_SHA256SUMS`. It intentionally excludes this report and itself.

Manifest SHA-256: `d83c7cabf66014434707e517ee7aff216aad8a6a2595ece39c3157bb25afc520`.

Real SDK `sdk/cpp/cambc.h` SHA-256: `5d175d6af2ccdb12c693db1dbfceefb0c096c7d482efe4e8683de7ea2d4516bf`.

Changed/new production source SHA-256 values (paths relative to candidate):

```text
53dfd6e7264ffc8459924e82aeb3ccb95996ec8dbb24cd9df65949640e5b3683  src/bot.cpp
61c98722c6acfccbba841a5eb5eafb566862f6a0493d648d0d3888d4dfe70364  src/camp_topology.h
c35f43a4291e301b2508af582973093f38aa40b2c52312a0a9e88139d7ed9ed6  src/camp_topology_access.h
27f223151943063996a7cc5a3c9a696367e9916317657dd8f634e9e50369fe72  src/dash_witness.h
07da7c873a73bc8dc75b97f28c3dd190ac90238b7ae1aaac2d8abe97761aa189  src/economy.cpp
ce6297aaae3df71c87e0423bf965871e1f45e073a678c88314c722eec62b604e  src/navigation.cpp
a538be2ab546011a3275032c1191c8738e17f56db135e983906acc6b8cef1b90  src/navigation.h
3f81be1368b22b8c696416f910b0740b7410bccbcc85be9f9e2255de4f77ee3b  src/objectives.cpp
```
