#pragma once
#include <array>
#include <cstdint>
#include <limits>

namespace lp::action {
struct Epoch {
    int actor=0, life=0, round=-1;
    unsigned revision=0;
    friend bool operator==(Epoch,Epoch)=default;
    bool same_turn(Epoch b)const{return actor==b.actor&&life==b.life&&round==b.round;}
};
enum class Owner { none, optional, service, bank, recovery };
enum class Op { step, dash, basic, lock_basic, reset, shield, heal, cast,
    recall, cancel_recall, submit, lock_use, ward, item_buy, consumable_buy,
    priority, count };
enum class Stop { accepted, acknowledged, refused, denied, stale, sealed, uncertain };
struct Target {
    int key=-1, x=0, y=0, slot=-1;
    int task=-1, cycle=-1, contact=-1;
    friend bool operator==(Target,Target)=default;
};
struct Request {
    Epoch epoch;
    Op op=Op::step;
    Target target;
    bool service=false;
};
struct Counts {
    std::uint32_t admitted=0, issued=0, acknowledged=0, accepted=0,
        observed=0, rejected=0, uncertain=0;
};
struct Receipt {
    std::uint64_t event=0;
    Request request;
    Epoch returned;
    Stop stop=Stop::denied;
    bool in_flight=false, reduced=false, after_observed=false, effects_observed=false,
        contact_charged=false, implicit_basic=false;
};
struct Result {
    Stop stop=Stop::denied;
    std::uint64_t event=0;
    bool accepted()const{return stop==Stop::accepted;}
};
struct CallResult {
    bool accepted=false;
    bool acknowledged=false; // submit's normal void return is only acknowledgement
};
// Production and scripted SDK hosts cross this same mutation seam. A driver
// must not retry. preflight reads fresh permissions; call issues exactly once.
struct Driver {
    virtual ~Driver()=default;
    virtual Epoch epoch()=0;
    virtual bool preflight(const Request&)=0;
    virtual CallResult call(const Request&)=0;
    virtual void invalidate() noexcept=0;
};

class Ledger {
    struct Failure { Op op=Op::step; Target target; };
    std::array<Failure,2> failures{};
    bool bound=false;
    bool increment(std::uint32_t& n) {
        if(n==std::numeric_limits<std::uint32_t>::max()){seal();return false;}
        ++n;return true;
    }
    void accept(Op);
    void reject_service(const Request&);
    bool permitted(const Request&)const;
public:
    Epoch origin;
    Owner owner=Owner::none;
    bool open=false;
    std::uint64_t next_event=1, last_reduced=0;
    std::array<Counts,static_cast<unsigned>(Op::count)> counts{};
    Receipt pending;
    bool step_attempted=false,dash_attempted=false,recall_attempted=false,
        cancel_attempted=false,submit_attempted=false,lock_attempted=false;
    unsigned steps=0,dashes=0,basics=0,casts=0,primitives=0;
    unsigned service_rejections=0;
    int fields=0,planning_jobs=0;
    std::uint32_t queries_issued=0,queries_completed=0,captures=0,
        recovery_captures=0,conversions=0,dirty_refreshes=0;
    unsigned entry_fuel=0,latest_fuel=0;
    bool fuel_crossed=false,fuel_invalid=false;

    // Called only by an outer play_turn entry. Revision changes and owner
    // handoffs cannot reset this record. Same-round reentry stays sealed.
    bool begin(Epoch,unsigned fuel);
    bool reconcile_life(int life);
    bool current(Epoch e)const{return open&&origin.same_turn(e);}
    bool handoff(Owner next,Epoch e) {
        if(!current(e))return false;
        owner=next;origin.revision=e.revision;return true;
    }
    void channel_history(bool recall_started,bool recall_cancelled,bool submit_started) {
        recall_attempted|=recall_started;cancel_attempted|=recall_cancelled;
        submit_attempted|=submit_started;
    }
    void seal() noexcept {open=false;owner=Owner::none;}
    void sample_fuel(int round,unsigned fuel) {
        if(round!=origin.round){fuel_crossed=true;return;}
        if(fuel>latest_fuel){fuel_invalid=true;return;}
        latest_fuel=fuel;
    }
    bool fuel_delta(unsigned& value)const {
        if(fuel_crossed||fuel_invalid)return false;
        value=entry_fuel-latest_fuel;return true;
    }
    Counts& at(Op op){return counts[static_cast<unsigned>(op)];}
    const Counts& at(Op op)const{return counts[static_cast<unsigned>(op)];}
    Result perform(const Request&,Driver&);
    // Owned after-facts can be attached later. No second charge/replayed call.
    bool observe(std::uint64_t event,Epoch,bool submit_started=false,
                 bool implicit_lock_basic=false,bool effect_observed=false);
    bool charge_contact(std::uint64_t event);
    void finish() noexcept {seal();}
};
}
