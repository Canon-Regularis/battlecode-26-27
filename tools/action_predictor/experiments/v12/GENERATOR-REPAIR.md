# C03: repair incomplete command generators

The current proposal API now calls the existing **P05 integer model on every
personal PRE**, regardless of G00's selected action or whether position exists.
There is no constant-zero priority proposal and no substitution of the baseline
GRU priority scalar. P05 may itself legitimately predict zero. Its signed integer
anchors remain exact; they are not reconstructed from normalized floats.

`proposal_predictor.load_proposal_predictor()` loads the unchanged M01, G00 and
P05 checkpoints. Observe every earlier actual own action, then call `propose`
with the matching observation, PRE supplement, public route, round, PRE cursor
and causal personal priority state. The result contains `Proposal` objects;
`proposal.as_dict()` exposes source, action, position, integer priority,
observed target identity and resolution status. Blocked is an outcome forecast
for an API move attempt and retains its destination.

The repaired bundle exposes **all nine existing spatial parameter heads
independently of the chosen action**. It also supplies ground casts in both
ability slots, historical range-two wards, five bounded attempted-movement
rules, personally observed enemy altar-lock attacks, and position-independent
utilities. PRE fields are allowlisted; observable attack/cast/ward/submit
readiness checks apply. Missing personal lock state is unknown, not known empty.
No current recorded family or argument reaches generation.

This is a **57-slot proposal schema, with no fitted selector**. A00's historical
31-slot library and checkpoint remain frozen. Its old weights must not be used
with the repaired bundle. No new training or promotion occurred.

## Measured support, separate from prediction accuracy

On every original DEV row, the oracle union of proposals and G00's unchanged hard
forecast changes as follows. Oracle means *some proposal matches*, not that a
learned selector chooses it.

| Category | Rows | Frozen support | Repaired support |
|---|---:|---:|---:|
| Priority | 576 | 71 | 109 |
| Blocked attempt | 110 | 8 | 55 |
| `cast_1` | 243 | 125 | 165 |
| Ward | 112 | 12 | 35 |
| Move | 2,362 | 1,953 | 2,032 |
| Attack | 985 | 972 | 976 |
| `cast_0` | 213 | 206 | 206 |
| Altar | 2 | 0 | 2 |
| Teleport | 2 | 0 | 0 |
| Shop, unassessed arguments | 43 | 0 | 0 |
| Cancel / end / recall / submit | 9,791 | 9,791 | 9,791 |
| **All original rows** | **14,439** | **13,138** | **13,371** |

The repair recovers **236 of the original 1,301 unsupported commands** and loses
three formerly covered moves: net **233**, leaving **1,068** unsupported. The
three destinations are still proposed but receive a blocked forecast from the
frozen blocked-versus-move logits. This is a measured outcome-forecast limitation,
not a claim that those recorded successful moves were illegal. The per-row
receipt retains the details; its generic explanation on two rows also lists an
unrelated ward at the same coordinate. All three movement failures have the same
outcome-forecast explanation. No destination was duplicated under both outcomes.

The priority-only control holds the original **31-slot budget** fixed and replaces
zero with P05. It recovers all **38** additional DEV priorities above the old
71-command union. On all **433,071 TRAIN rows**, it raises priority support from
2,697 to 3,727, recovering 1,030 commands. Thus this fix does not depend on the
larger candidate pool. P05 still misses 467 DEV priority integers; repairing its
availability does not establish reliable value prediction.

Expanded-library coverage was developed/measured first on a declared **24-game,
22,620-row TRAIN cohort**, not all TRAIN geometry. There it recovers 647 old
support misses and loses one. The priority-only and conditional-head bridge
diagnostics cover the full original TRAIN denominator. The bridge is explicitly
a coordinate-representation diagnostic; it is not certified entity-command
support. The inherited movement slot names include `field` but this library
uses the frozen **simple/geometric** mode, not terrain-field planning.

## Validation and remaining limits

All nine conditional coordinate argmaxes, the P05 integer, the movement outcome
preference and the final proposal arrays reproduce **exactly in 385 raw-PRE
cases across all 25 DEV games and both historical engines**. These include 353
cases where G00 chooses a non-priority action while P05 predicts a nonzero
integer, 20 missing-position cases, and 57 personal-lock-queryable PREs. Actual
earlier own roots supply history; sampled decisions are never stitched together.
Three regression tests check the priority/missing-position contract, provenance
rejection and absence of duplicate movement outcomes.

Personal altar-lock recovery queried only recorded eligible PREs with an alive
actor within its attack range of a public altar, independently of the recorded
action. It recovered the four omitted attack coordinates. Coordinates do not
uniquely certify original entity identity when targets overlap. Full engine
legality remains unassessed. Shops remain 43 strict failures; sparse altar,
teleport and submit categories remain uncertified. Both reserved partitions
remain sealed. There were no fits, games, simulations, downloads or bot changes.

The largest remaining support gaps are priority **467**, movement **330**,
`cast_1` **78**, ward **77**, and blocked **55**. Existing selector failures are
not solved by this patch. Actual A00/G00 prediction accuracy and their saved
results are unchanged.

Reproduce from the repository root with the pinned interpreter:

```powershell
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_proposal_generator
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.proposal_study train
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.proposal_study validation
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.proposal_roundtrip
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.proposal_analysis
```

Study commands create immutable outputs and refuse to replace completed candidate
arrays. Reuse the hash-bound local artifacts rather than rerunning extraction.
The existing all-family preparation tables and their original producer receipt
are required local inputs; their hashes are bound in `C03-arguments.json`.
See `C03-plan.json`, `C03-{train,validation}.json`, `C03-attribution.json`,
`C03-causal-roundtrip.json` and `C03-completion.json` for exact evidence.
