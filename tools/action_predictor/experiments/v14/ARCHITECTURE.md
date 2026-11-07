# Ward failure mechanisms and controlled specialist experiment

The G00 action classifier is M01's shared128-dimensional current-observation/GRU
encoder and15-way classifier. G00 changes movement parameters and retains P05
priority; ward typing and coordinates are unchanged M01 components. The ward
coordinate head is the shared20-channel tile encoder, a context query plus
family embedding and family-specific offset bias. It scores289 local encoding
cells plus outside/missing buckets. Its constraints explicitly handle movement,
attacks and casts, not ward range. Nevertheless, **all112 DEV conditional ward
forecasts already lie within the historical ward radius**:4atdistance1 and108at2.
Thus an absent hard radius restriction does not explain these DEV mistakes.

G00 trueward failures partition into77 wrong action types and28 wrong locations
after the correct type;7/112 commands are correct. The all-true-family head
gets24/112 locations right. Perfect typing alone would still be capped at24/112;
perfect placement alone at35/112 with its current action choices. Of317ward
forecasts,282are false positives and257of those are recalls.

This is not solely a DEV phenomenon. Natural TRAIN has2,192wards,782correctly
typed,449correct conditional coordinates and142correct joint commands. Its5,430
ward false positives include5,014recalls. Full augmented TRAIN has10,842 distinct
ward rows,3,888correct types,2,274correct conditional locations and754joint.
These are separate sampling distributions; the latter is not an easier DEV
comparison. See architecture-diagnosis.json for exact counts.

Ward charges and recharge were ALREADY encoded in legacy PRE features. Newly
recovered inputs are personally available placed-ward positions, owner association
to self, timers, radius, disabled state and allied/enemy/control occupancy.
The historical engines2/3 return these through owned-champion personal APIs.
Every entity is authorized with its personal Ward_Get/ControlWard_Get before
using its personal snapshot fields. No hidden owner champion state enters inputs.
Geometric coverage indicators do not establish actual line-of-sight visibility.

Existing own history carries earlier ward actions; richer features expose the
last recorded ward available within32actual own roots with an availability flag.
Placed wards absent from that short history can still be known through current
personal APIs. Currently visible allies/enemies/camps and public terrain are
available; the frozen128context compresses them and legacy summaries omit some
entity detail. This motivates a representation control, not a claim that omitted
information definitively causes a particular number of errors.

The four-fit protocol compares matched placement heads P00/P01 and matched binary
heads T00/T01. The former contrast adds direct PRE/ward features; the latter adds
ward-specific state to the existing context/PRE/history inputs. Each is a small
independent expert with frozen upstream models. This tests useful specialization
against retained G00, and richer information against matched specialist capacity;
it is not a perfectly isolated specialization-versus-joint-training causal test.

No additional B01/B02 goal/memory fit is run. Their partial preparation is
preserved. B00's repaired likelihood/decoder and negative category results remain.
The protocol's shorthand "zero wardtypes" means zero correctly typed wards:
B00 actually emits one false ward forecast. It is not a zero-forecast claim.

The earlier R02 capacity probe fitted110/128 ward locations with perfect fitted
typing, but generalized poorly. That rules out a universal inability to fit ward
labels in that probe, not an information or generalization ceiling. The new
specialists' TRAIN curves and fixed-group DEV results remain necessary evidence.
Typed bush terrain and exact line-of-sight coverage are not recovered in this
initial representation; public blocked geometry is present. A negative result
cannot establish that every ward-specific observable representation is exhausted.

Primary A/B/C use the original G00 action-first decision order so A's action
choices are exactly unchanged, as requested. The type and conditional factors
are normalized and their actual probabilities are used for likelihood and
confidence. Primary is explicitly not claimed global jointMAP. A separately
prespecified jointMAP evaluation uses the same distributions in all treatments
and its Q00control; it can change type in the head-only intervention and is
labeled accordingly. Neither decoder is selected after seeing DEV results.

Physical domain is the historical SDK's in-map Chebyshev radius2 and currently
known allied ordinary-ward exclusion. Remaining full engine legality is not
certified by a range board. Every unsupported recorded parameter stays in the
denominator and receives the explicit1e-4 original-head likelihood tail.
No proposed actions, matches, downloads or playing-bot changes are permitted.
