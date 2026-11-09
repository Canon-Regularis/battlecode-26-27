# Destination discrimination: no-fit input audit

This audit identifies a concrete restriction in the current movement readout:
information about surrounding terrain is present in other candidate-grid cells,
but cannot change the relative scores of two supported destinations when their
own features and shared context are fixed. This does not establish that terrain
caused the recorded mistakes or that another spatial model would improve them.

The primary analysis uses R00's saved final forecasts for all 2,669 fitting
direction changes. R01 repeats the analysis descriptively. For each row, the
rival is the highest-scored outcome excluding the recorded destination and exact
previous displacement; vocabulary order breaks ties. This target-conditioned
comparison is an audit, not a new decoder, achievable accuracy or an oracle
ceiling. No new forecasts, optimizer updates or held-data evaluations occurred.

All 2,669 current personal PRE inputs reproduce the stored normalized current
features, float16 grid and validity mask exactly across all 40 fitting groups.
The archived 5,338 pairs retain every rival, including one unsupported tile per
arm. That tile ranks below gold in both arms; no special-bucket rival occurs.
Forty examples follow the prospectively fixed hash rule, one per primary error
group. They are descriptive examples, not a random sample or evidence of intent.

R00 has 1,768 rows where the incorrect nonrepeat rival strictly outranks gold.
In this cohort:

- All pairs have distinct offset coordinates, and all rivals are supported.
- 1,764 pairs share the destination's blocked/enemy-spawn features. Of those,
  839 have different surrounding 3x3 obstacle/boundary patterns, entirely inside
  the existing candidate grid.
- 390 pairs have identical nearest-entity distance channels; every pair has
  identical entity occupancy-count and occupancy-health channels.
- 145 pairs match all audited task channels (blocked/spawn, entity distance,
  occupancy/health and altar distance). Only 73 match every channel except x/y.

None of these partial equalities is a full-input collision: coordinates always
differ, while shared current/history context and learned offset biases remain
available. In particular, the audit does not establish observation insufficiency.

For two supported destinations, the original support mixture multiplies both
unnormalized tile masses by the same normalization factor. Their odds therefore
depend on their own pointwise candidate embeddings, shared query and offset
biases. Other candidate cells can affect individual normalized probabilities,
but not these pairwise odds with both endpoints/context fixed. A synthetic test
checks this property, including changes to other cells' movement support. The
policy's context and memory have no grid encoder; position/history can still
carry indirect correlations with map layout. The claim is about this readout
path, not all information the model could infer from correlations.

Entity evidence is more mixed. In the primary error cohort, the following
counts concern identical per-category candidate summaries with different nearest
entity sets. Ties are retained as sets, and current summary membership follows
the original stable nearest-three ordering.

| Category | Same summary, different nearest entities | All nearest entities in current nearest-three summary | Some omitted from that summary |
| --- | ---: | ---: | ---: |
| Enemy | 10 | 10 | 0 |
| Ally | 201 | 178 | 23 |
| Camp | 158 | 91 | 67 |

Thus many entity associations are recoverable from coordinates already present
in shared current features, even when the scalar candidate summary is identical.
No nearest-distance clipping collision occurs. Chebyshev attack-range boundary
differences involve represented entities on 82 enemy, 476 ally and 328 camp
pairs, and entities outside the current nearest-three summary on 5, 50 and 209
pairs respectively. Counts can overlap and are not error attribution. These
geometric boundaries are not legal attacks, danger labels or a preferred move.
Fields omitted from a current summary may also have appeared in history or be
indirectly recoverable elsewhere; this audit does not test whole-history
sufficiency. Entity type/cooldown omission is additionally checked synthetically
as an encoding fact, not as evidence that those fields explain these choices.

R01 shows the same broad pattern: 1,716 outranked-gold pairs, 803 with the same
destination terrain but different in-grid neighborhoods, and 74 matching all
channels except x/y. R01 remains the reviewed negative training result; these
counts do not change its failed allocation gate or select it over R00.

The next specific hypothesis worth designing is whether a movement-only path
for local neighborhood evidence improves alternative ranking while preserving
other commands. V6 already tested candidate-aligned local and global map CNNs:
conditional movement improved, but targeting regressed. Consequently, a new
proposal must distinguish information access and shared-path interference from
that earlier experiment, for example through a tightly controlled movement
residual with the existing backbone fixed. This is a design direction, not fit
approval or evidence that such a residual will work. It needs an explicit matched
control, identical training opportunities and the existing behavioral guards.

Six focused tests pass. Parent checks verified all 77 source and 454 input
bindings, the compressed pair archive, all rival choices/margins, feature
differences and summary arithmetic. Every reported route-neighborhood pattern
also reproduces directly from the stored candidate grid, independently of the
route calculation. Original replay provenance relies on the approved V32
assembly receipts. Independent code/evidence review is pending. Strong-reference,
category-90%, reliability, three-seed and existing data limitations remain; no
strategy, playing-strength, generalization or promotion claim follows.
