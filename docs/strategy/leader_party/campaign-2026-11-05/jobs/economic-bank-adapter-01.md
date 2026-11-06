# Economic banking adapter: one freshly guarded action

Implement a small inactive banking module in the copied candidate. Root is
concurrently implementing objective candidates and final dispatch on the PC.
Do not change those modules, the existing Bot, recovery, capture, fields,
service, arithmetic, ledger, SDK, or existing tests. No games or uploads.

Allowed changes: add `src/economic_bank_sdk.h`, `src/economic_bank_sdk.cpp`,
`tests/economic_bank.cpp`, and required `IMPLEMENTATION.md` only.
The full bank/route/queue integration remains root's job; this module is the
stationary bank action seam, not a complete independently ready bank bot.

Evidence/specification is in the supplied economic-bank-execution.md. The old
economy::bank unconditionally waits for submitting allies and mixes movement,
combat, lock use and submission without shared action accounting. New owned
Scene and LiveTurn/Ledger are already present. Read their actual interfaces.

Required public interface in namespace lp:

```
enum class BankStop { action, complete, channel, approach, hidden, unsafe,
                      allowance, unsupported, blocked };
struct BankChoice {
    BankStop stop=BankStop::blocked;
    action::Request request;
};
bool bank_position_safe(const economic::Scene&);
BankChoice choose_bank(const economic::Scene&, const economic::Task&,
                       const action::Ledger&);
action::Result perform_bank(const economic::Scene&,const BankChoice&,LiveTurn&);
```

Selection is owned-scalar only, one action returned. Task purpose must be
convert/observe_access, key.object the index in Scene.altars. Preserve active
submission/teleport/recall (return channel). No bag returns complete. No
adjacency returns approach. Require current complete living uncompleted,
unstunned state, actual altar visibility and SDK submit range. Conservative
bank safety requires the actual position seen, no current awake harmful camp
in range and no visible living enemy within basic range+move_range; unknown
harmful member in possible range is unknown/unsafe, never certified zero.
Do not suppress a free safe start because another ally is channeling.

Fresh enemy lock: legal basic first, or supported available attack reset when
basic is spent and shared cast remains (at most two basics/one cast/four total
primitives shared). No damaging spells on locks. No lock: optional already
carried own lock when not consumable-restricted and placement unused; otherwise
submit when shared start unused. Existing allied lock permits submission.
winning_gems affects the caller's priority, not permission in this module.

perform_bank validates request epoch/scene identity and exact requested op,
hands off bank ownership, uses LiveTurn.perform and public SDK only. Recheck
actual position/bag/channel/permissions, target altar visibility and current
one all-team lock snapshot. A lock attack must match observed enemy position
and current hits; use champion::attack(altar_lock). Reset verifies exact slot,
type/cooldown and fresh spent-basic state. Lock use checks fresh inventory,
range, no existing lock, real Boolean use result. Submit checks no enemy lock
and calls the void submit_gems without translating normal return to success.
Ledger acknowledgement is reconciled by root's fresh after-scene. Never
observe/retry/issue a second action internally, use blind submit as lock probe,
cancel any channel, call legacy bank/fight/move_to/shop, or catch and hide SDK
errors. False/stale/error must preserve existing transaction semantics.

Do not hardcode new resource reserves; use existing checked transaction seam.
No raw imports, private SDK layouts, fabricated API or out-of-scope changes.

Add focused scalar choice cases: free/shared allied channel, own/enemy/hidden
lock, lock hit/reset with shared cast spent, unsafe/unknown camp/enemy, active
channel, stale/incomplete scene, empty bag and placement already attempted.
Compile all production translation units with the supplied real SDK headers.
If actual host issuance cannot be exercised on Pi, explicitly say it remains
for root's strict SDK fixture; do not invent evidence. Do not build a new broad
harness or change frozen assertions. Return the actual implementation promptly.
