#pragma once
#include "observations.h"
#include "turn_ledger.h"
#include <type_traits>
namespace lp {
// A dispatch is owned by Bot. Every owner uses this same object, including
// revision refreshes and recovery takeovers. No destructor queries/actions.
struct TurnExpired {};
struct TurnDeferred {};
class LiveTurn {
    action::Ledger& ledger_;
    Memory& memory_;
    int actor_;
public:
    LiveTurn(action::Ledger& l,Memory& m,int actor):ledger_(l),memory_(m),actor_(actor){}
    action::Ledger& ledger(){return ledger_;}
    action::Epoch epoch()const{return {actor_,memory_.life,int(round_number()),observation_version()};}
    void check() {
        const auto e=epoch();ledger_.sample_fuel(e.round,fuel_remaining());
        if(!ledger_.current(e)){ledger_.seal();throw TurnExpired{};}
        if(fuel_remaining()<Config::reserve)throw TurnDeferred{};
    }
    template<class F> auto read(F&& f) {
        check();
        if(ledger_.queries_issued==UINT32_MAX){ledger_.seal();throw TurnDeferred{};}
        ++ledger_.queries_issued;
        auto value=f();
        ++ledger_.queries_completed;
        check();return value;
    }
    bool preflight(action::Op);
    template<class Check,class Call>
    action::Result perform(action::Request request,Check&& check_action,Call&& issue) {
        struct CallbackDriver final:action::Driver {
            LiveTurn& turn;Check& guard;Call& mutation;
            CallbackDriver(LiveTurn& t,Check& g,Call& c):turn(t),guard(g),mutation(c){}
            action::Epoch epoch()override{return turn.epoch();}
            bool preflight(const action::Request& r)override {
                return turn.preflight(r.op)&&guard();
            }
            action::CallResult call(const action::Request& r)override {
                if constexpr(std::is_void_v<std::invoke_result_t<Call&>>) {
                    mutation();return {r.op!=action::Op::submit,r.op==action::Op::submit};
                } else return {bool(mutation()),false};
            }
            void invalidate()noexcept override{invalidate_observations();}
        } driver(*this,check_action,issue);
        check();return ledger_.perform(request,driver);
    }
};
}
