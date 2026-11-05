# dg01: admissible dominant gem objective during bootstrap

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, cloned from `leader_party_tuned`.
Candidate: `bots/pi_dominant-gems-01/`. Changes are uncommitted for the bridge.
No item experiment was inherited. No platform upload or ranked change was made.

## Hypothesis and scope

The bootstrap distance policy can ignore an unusually valuable passive gem group after equipment makes its estimated clear time admissible. Prefer a unique, strictly dominant passive gem group when choosing a new bootstrap task, provided the existing selector admits it. This tests later objective valuation under the existing roster and executor.

The supplied engine3 evidence describes 00vault's center as 49 gem clusters, 5880 HP and 343 gems versus 16 gems elsewhere. No initial roster member passes the existing 90-round clear estimate. In ranked loss `01a1a978-6393-7eab-b12e-f7804eff3be2`, Vesper's seven Strength shards at round 209 imply an estimated clear of 66 before the enemy clear/capture at 272/278, while our phase 3 starts at 625/629. That suggests an opportunity; it does not establish availability, safety or travel feasibility. These replay observations were supplied by the task, not independently replayed on the Pi.

Fish diagnostic `01a1a9b5-5820-755b-8197-db4f68af6378` clears at 33 and captures at 39, winning 1142–8 at 262. This treatment retains the initial clear-time exclusion and cannot reproduce that opening; it makes no claim to beat Fish. It also does not address enemies capturing camps we clear, including the economic losses described on 04restricted_area, where no dominant group exists.

## Actual changes

- `src/dominant_gems.h`: a small metadata helper sums every group's gems in signed 64-bit integers, then finds a positive-gem, zero-gold group whose members are all `is_gem_cluster()` and whose reward strictly exceeds the sum of all other groups. All groups contribute to the total regardless of reachability, gold or member type. Only immutable public metadata is read; there are no map names, IDs, coordinates or reward constants in the policy. A constant-time helper checks bootstrap and the existing eligibility bit.
- `src/objectives.h`: cache `World::dominant_gem_camp`, defaulting to `-1`.
- `src/objectives.cpp`: compute the cached index once in the existing guarded initialization, immediately after the unchanged anchor sort and before route loading. After the complete, unchanged eligibility scan, return that index only if bootstrap and eligible. Otherwise execute the exact previous planner/fallback code.
- `tests/dominant_gems.cpp` and `tests/run_native.py`: focused native fixtures using the production helper, the actual extracted `choose_camp` body and the actual canonical-sort/cache statements. Generated headers and executables stay in a temporary directory.

No existing task is preempted: the caller still invokes `choose_camp` only when `memory.task < 0`. Retry, distance field, risk/reachability, respawn, remaining/design HP, max_clear=90 and every scoring expression are unchanged. Later-phase loop precedence is unchanged. World ordering, route packets, pathfinding, roster, shopping, combat, retreat, banking, task_limit=90, loop_phase=3 and value_routing=false are unchanged. No release logging was added. Extra metadata work is confined to initialization; selection adds a bounded constant-time check.

## Checks performed on the Pi

Host: aarch64, GCC 13.3.0. From repository root:

```sh
python3 bots/pi_dominant-gems-01/tests/run_native.py
```

Passed: **40 dominant metadata/production selection checks**, plus the inherited protocol and state scenarios. The native harness compiles with C++20, `-O2 -Wall -Wextra -Werror`.

Coverage includes strict dominance versus equality, zero rewards, gold exclusion, every non-gem member type and mixed groups, all-gem multi-member groups, sum of all other groups including unreachable ones, totals exceeding 32 bits, full uint32 rewards, empty maps, canonical index after the production anchor sort, bootstrap in both scoring modes, later-phase planner precedence and fallback, missing dominant group, retry cooldown and its expiration, unreachable approaches, respawn before/after arrival, clear estimates at 90 and above, fresh/stale remaining HP, reward-available admission, no eligible result and budget/stale-field deferral.

The harness supplies metadata and exported distances; it runs the real eligibility/selection expressions. Its blocked/risk case supplies an unreachable field result: it does not test SDK distance computation, occupancy or engine navigation. It extracts the initialization sort/cache seam, not the entire engine-dependent `World::init`. These are native policy checks, **not SDK runtime integration tests or WASM matches**.

```sh
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_dominant-gems-01/src/*.cpp
```

Passed for all candidate translation units against the checkout SDK, including the actual public metadata API. A first plain GCC syntax attempt failed on existing SDK `team team()` naming diagnostics and missing `std::ceil`; suppressing the naming diagnostic still exposed missing `std::ceil` in objectives/route_plan. The same missing-header errors were reproduced in the unchanged baseline. The successful command supplies `<cmath>` externally and suppresses only the naming diagnostic. No source outside the candidate, and no unrelated candidate source, was changed to accommodate native GCC. This check does not link or validate the release toolchain.

A byte comparison against the base commit audited all **33 inherited files**: only `src/objectives.cpp` and `src/objectives.h` differ. Removing the four added lines from objectives.cpp exactly restores the base source, including all eligibility, distance and planner code. Git reports no tracked modifications outside the candidate. No tournaments were run. CAMBC/uv/release compiler tooling is unavailable on this Pi PATH.

## Required PC diagnostics and uncertainty

First build the exact candidate source in release mode using CLI5/current engine. Record source and artifact identities. Run 00vault on both sides against frozen champion and C02, with matching baseline games. Require zero candidate VM faults. Inspect actual central clear, capture and bank events; wins and scores alone do not establish the mechanism. Measure active-rule exposure, target rewards, banking, deaths, faults and paired outcomes.

Eligibility may remain false until too late; existing task commitment can delay selection even after equipment improves. The unchanged solo clear estimate is neither a safety model nor a guarantee of completing travel, combat and capture within task_limit=90. Capture access, competition, retreat and banking can defeat the opportunity. Record observed task expiration without changing the deadline. If no productive dominant-group capture occurs, retain the failed mechanism evidence and diagnose eligibility, commitment, combat, capture access or banking. Do not broaden treatment or upload on a proxy win.

Only after diagnostic mechanism success, run the same 80-game regression screen. Direct champion >=8/16 and common >=31/64 are minimal regression conditions, not evidence of increased strength; the rare rule may not trigger. Broader testing needs predeclared development maps, diverse opponents and no-dominant negative controls; fresh confirmation maps remain reserved. Release build, engine integration, VM fault rate, actual rule exposure and match outcomes remain unmeasured here. No platform upload or ranked change is authorized by this job.
