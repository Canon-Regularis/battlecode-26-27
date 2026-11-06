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
    action::Epoch capture_check(const action::Epoch* expected=nullptr,bool enforce_reserve=true) {
        const auto before=epoch();const auto fuel=fuel_remaining();const auto after=epoch();
        ledger_.sample_fuel(after.round,fuel);
        if(before!=after||!ledger_.current(after)||(expected&&after!=*expected)) {
            ledger_.seal();throw TurnExpired{};
        }
        if(enforce_reserve&&fuel<Config::reserve)throw TurnDeferred{};
        return after;
    }
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
    // Only audited public getter calls in EconomicCapture use this reader.
    // A call may resume after suspension; up to seven remaining pure reads
    // can then run before close rejects the entire provisional result.
    class CaptureReads {
        LiveTurn& turn_;
        unsigned calls_=0;
        explicit CaptureReads(LiveTurn& turn):turn_(turn){}
        friend class LiveTurn;
    public:
        CaptureReads(const CaptureReads&)=delete;
        CaptureReads& operator=(const CaptureReads&)=delete;
        template<class F> auto read(F&& f) {
            auto& ledger=turn_.ledger_;
            if(calls_==8||ledger.queries_issued==UINT32_MAX||ledger.queries_completed==UINT32_MAX) {
                ledger.seal();throw TurnDeferred{};
            }
            ++calls_;++ledger.queries_issued;
            auto value=f();
            ++ledger.queries_completed;return value;
        }
    };
    template<class F> void capture_reads(F&& f) {
        const auto start=capture_check();
        CaptureReads batch(*this);
        try {f(batch);}
        catch(...) {capture_check(&start,false);throw;}
        capture_check(&start);
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
