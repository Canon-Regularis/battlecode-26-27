# Concrete ranking arithmetic for selected B

5 November 2026. Construction choices for the combined core, to incorporate in
the eventual self-contained Pi job. These are deterministic engineering
hypotheses, not a measured optimizer or a new admission gate. They implement
the [selected policy](economic-core-selection.md) and its
[cycle comparison](economic-core-policy-options.md). No production edits,
matches or uploads accompany this specification.

## Quantities and arithmetic

Store resource forecasts, path hops, work turns and time sums as checked
`uint64_t`; current SDK bag/rewards enter through validated integer values.
Time uses game-round units, not machine milliseconds. Adjacent diagonal steps
count one hop, consistent with the walking graph. Do not estimate saved turns
from a currently ready dash in a long-route rank: its real action use remains
an executor decision. Both options use the same conservative walking estimate.
This simplifies ranking; it does not remove dash from execution.

Use scale1024 for positive HP/damage quantities in the nominal basic-work prior:
`HPq=ceil(1024*observed_or_prior_HP)`,
`Dq=max(1024,floor(1024*nominal_basic_damage))`, and
`work_i=HPq/Dq + (HPq%Dq != 0)`. Validate finite/nonnegative inputs and checked
conversion first. Accumulate only positively alive or explicitly estimated
members; missing visibility is not zero HP or death. Remembered HP is evidence
with an age/cycle, not a guaranteed lower or upper bound after an unseen gap.

`work=sum(work_i)` remains a ranking heuristic. It omits movement within the
group, spells/reset/AoE throughput, growth, future HP and teammate assistance.
It is neither a fixed service schedule nor a feasibility bound. Rounding is
deliberately conservative for the nominal model, not a claim about actual
engine fractional-damage rounding.

An out-of-range/unknown work prior is `UnpricedEstimate`, **not** impossible,
unsupported service or exhausted contact. A supported untried information/
contact option still exists and must receive a finite canonical fallback
consideration if priced opportunities do not produce a supported useful task.
No huge-HP/large-member group is removed merely because the estimate cannot
be represented or exceeds90. Actual service readiness and its finite effort
remain the separate [lifecycle](economic-task-lifecycle-contract.md) contract.

For each rate store numerator and strictly positive denominator separately;
never round the rate to an integer quotient before ranking. Use checked
`uint64_t` cross multiplication when both products fit. If either product
would overflow, compare the two nonnegative rational numbers exactly using
quotient/remainder continued-fraction comparison (reversing ordering on each
reciprocal step), at most128iterations for64bit inputs. No floating fallback,
silent wrap, host call or unbounded loop. Test equality, zero numerators,
adjacent fractions, maximal operands and comparison symmetry/transitivity.
Arithmetic capacity errors remain explicit; they cannot award progress or
erase an obligation.

## Initial nominal basic damage

Start from freshly observed `self.strength()`, which already contains current
stat bonuses. Do not add inventory Strength a second time. Support the
following verified outgoing multipliers in the prior:

- Heart's actual `missing_health_damage` passive: multiply by
  `1 + constants::passive_abilities::heart_of_ruin_missing_health_damage_max_bonus
  * clamp(1-HP/maxHP,0,1)`. The public SDK constant is0.5
  (`sdk/cpp/cambc.h`, passive constants near177); the rules describe the same
  missing-health effect. Use current owned HP/maxHP, not a design value.
- An actually owned completed Monster emblem: use its immutable engine-provided
  passive magnitude once for the family (`item_type::info()` and
  `item_passive::monster`, SDK near2424). Rules' Monster family is15% more damage
  to camps. Shards do not grant this passive; duplicate variants do not stack.

The [actual-native metadata probe](native-item-metadata-contract.md) confirms
Monster magnitude approximately0.15: use`1+magnitude`, once. Its84item records
also distinguish percentage effects from the Capture family's timer cap3;
do not apply one generic magnitude formula to every passive.

All other unmodeled damage effects remain omitted and labeled in the prior;
there is no invented `0.2*Focus`, spell-equivalent basic DPS or upgrade payback.
The actual service executor retains legal supported reset, spell, dash and
enhanced-basic actions regardless of these omissions. An unsupported modifier
model is not a ban on the real action. Current camp-specific mitigation or
shielding is not silently fabricated from target kind.

Sources: public unit/champion Strength getters in `sdk/cpp/cambc.h` near3195/
3718, item metadata near2424, [rules emblem families](../../../cambc/GameRules.md),
and [service contract](economic-service-execution-contract.md). The service
damage selection and actual observed work remain distinct from this nominal
camp-ranking prior.

## Crowding and forecast recipients

For an unoccupied living group, start with one prospective recipient=self.
Count each other currently visible, living, nonchanneling ally at most once
if at least one **currently visible living** group member lies within that
ally's observed basic attack range (Chebyshev tile distance). Copy ally
position/range/channel flags once into the owned scene, never query them per
member/candidate. Count only public evidence; no ally gold, task assignment,
future damage or future occupancy is inferred.

Forecast own base reward as integer `floor(group_base_reward/count)`, separately
for gems and gold. Ignore uncertain remainder and positive reward bonuses.
This is a crowding heuristic, not a promise that those allies will capture or
that an attacking ally is a recipient. It can underprice a group when helpers
leave, or overprice it when another ally arrives. Record actual role/lifecycle
changes and receipts separately. If group reward is already available, use
fresh holder/takeover logic instead of applying this living-work crowd formula
to justify joining an adequately secured allied holder.

## Complete-cycle terms and commitment

`T=approach_hops+nominal_work+capture_wait+delivery_hops+tribute_ticks`.
Use `max(1,T)` only to keep a completed/zero-distance estimate well-defined;
unknown/deferred time is not zero. Capture wait follows actual status and
start-plus-countdown timing; tribute duration follows current settings,
forecast bag and supported observed Tribute passive. The later
[native duration contract](tribute-duration-native-contract.md) supplies the
tested default-setting, zero/one-completed-Tribute model: round ordinary
duration up before reducing and rounding again. A bag of 11 still needs 2 turns;
a bag of 31 with Tribute needs 3 rather than 4. This finite native evidence does not
prove every numeric boundary or other settings/passives; keep unsupported
estimates unpriced. Actual channel execution uses its freshly observed timer,
not the raw snapshot `submissionDuration` field or recalculation after a
mid-channel receipt. The completion amount can include later receipts.

Compare `(current_bag+forecast_own_gems)/T` with `current_bag/BankNow_time`.
No known executable access means no certified BankNow rate. Conditional cycle
estimates remain conditional and authorize information/contact, not a future
unsafe action. After finite current bank access exhaustion, gold fallback has
its independent base-gold numerator with neither held bag nor speculative
conversion, as the lifecycle contract requires.

Ties: shorter full conversion time, lower approach hops, canonical target
anchor `(y,x)`, stable group ID. Same actor identity is already fixed for an
actor-local comparison; it cannot break a tie between that actor's own tasks.
At rate equality with immediate BankNow, prefer BankNow before target ties.
Do not rerank a useful committed task each turn; use the selected commitment
boundaries. Exact route sharing, bank preflight and service-risk admission are
separate required contracts, not assumptions silently supplied by this score.
