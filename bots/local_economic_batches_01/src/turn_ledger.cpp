#include "turn_ledger.h"
namespace lp::action {
bool Ledger::begin(Epoch e,unsigned fuel) {
    if(bound) {
        if(e.actor!=origin.actor||e.round<=origin.round) return false;
        // A suspended host mutation must return into its original dispatch.
        // Never discard an unresolved event to mint fresh action allowances.
        if(pending.in_flight){seal();return false;}
    }
    const auto event=next_event,reduced=last_reduced;
    *this=Ledger{};bound=true;origin=e;open=true;
    next_event=event;last_reduced=reduced;
    entry_fuel=latest_fuel=fuel;return true;
}
bool Ledger::reconcile_life(int life) {
    if(!open)return false;
    if(life==origin.life)return true;
    // First observed death is reconciled before any admitted action/work.
    // Entry self reads are required to discover death. Preserve their charges;
    // reconcile identity before any plan or admitted mutation, without reset.
    bool pristine=next_event==last_reduced+1&&pending.event==0&&fields==0&&planning_jobs==0;
    if(!pristine){seal();return false;}
    origin.life=life;return true;
}
bool Ledger::permitted(const Request& r)const {
    if(!current(r.epoch)||owner==Owner::none||pending.in_flight)return false;
    if(pending.event&&at(pending.request.op).issued&&
        (pending.stop==Stop::accepted||pending.stop==Stop::acknowledged||pending.stop==Stop::refused)&&
        !pending.after_observed)return false;
    if((r.op==Op::item_buy||r.op==Op::consumable_buy||r.op==Op::priority||r.op==Op::ward)&&owner!=Owner::optional)return false;
    if((r.op==Op::submit||r.op==Op::lock_use||r.op==Op::lock_basic)&&owner!=Owner::bank)return false;
    if((r.op==Op::recall||r.op==Op::cancel_recall)&&owner!=Owner::recovery)return false;
    if(r.service&&(owner!=Owner::service&&owner!=Owner::bank))return false;
    if(r.service) {
        if(service_rejections>=failures.size())return false;
        for(unsigned i=0;i<service_rejections;++i)
            if(failures[i].op==r.op&&failures[i].target==r.target)return false;
    }
    switch(r.op) {
    case Op::step:return !step_attempted&&steps+dashes<2&&primitives<4;
    case Op::dash:return !dash_attempted&&casts<1&&steps+dashes<2&&primitives<4;
    case Op::basic:case Op::lock_basic:return basics<2&&primitives<4;
    case Op::reset:case Op::shield:case Op::heal:case Op::cast:return casts<1&&primitives<4;
    case Op::recall:return !recall_attempted&&!cancel_attempted;
    case Op::cancel_recall:return !cancel_attempted;
    case Op::submit:return !submit_attempted;
    case Op::lock_use:return !lock_attempted;
    case Op::ward:case Op::consumable_buy:case Op::priority:return at(r.op).admitted==0;
    case Op::item_buy:return at(r.op).admitted<40;
    case Op::count:return false;
    }
    return false;
}
void Ledger::accept(Op op) {
    increment(at(op).accepted);
    switch(op) {
    case Op::step:++steps;++primitives;break;
    case Op::dash:++dashes;++casts;++primitives;break;
    case Op::basic:case Op::lock_basic:++basics;++primitives;break;
    case Op::reset:case Op::shield:case Op::heal:case Op::cast:++casts;++primitives;break;
    default:break;
    }
}
void Ledger::reject_service(const Request& r) {
    if(r.service&&service_rejections<failures.size())
        failures[service_rejections++]={r.op,r.target};
}
Result Ledger::perform(const Request& r,Driver& driver) {
    if(!open)return {Stop::sealed,0};
    if(!current(r.epoch)||driver.epoch()!=r.epoch){seal();return {Stop::stale,0};}
    if(!permitted(r))return {Stop::denied,0};
    // Never silently reuse/wrap an event identity.
    if(next_event==std::numeric_limits<std::uint64_t>::max()){seal();return {Stop::sealed,0};}
    if(!increment(at(r.op).admitted))return {Stop::sealed,0};
    switch(r.op) {
    case Op::step:step_attempted=true;break;
    case Op::dash:dash_attempted=true;break;
    case Op::recall:recall_attempted=true;break;
    case Op::cancel_recall:cancel_attempted=true;break;
    case Op::submit:submit_attempted=true;break;
    case Op::lock_use:lock_attempted=true;break;
    default:break;
    }
    pending=Receipt{};pending.event=next_event++;pending.request=r;
    const auto event=pending.event;
    try {
        bool ready=driver.preflight(r);
        // Even a refused preflight may have crossed rounds. No failed contact
        // or service-rejection ticket is charged for permissions/resource denial.
        if(driver.epoch()!=r.epoch){pending.stop=Stop::stale;pending.reduced=true;
            last_reduced=event;seal();return {Stop::stale,event};}
        if(!ready){pending.stop=Stop::denied;pending.reduced=true;
            last_reduced=event;return {Stop::denied,event};}
        if(!increment(at(r.op).issued)){pending.stop=Stop::sealed;return {Stop::sealed,event};}
        pending.in_flight=true;
        const auto result=driver.call(r);
        // Save return facts BEFORE any refresh or epoch query can suspend.
        pending.in_flight=false;
        pending.stop=result.accepted?Stop::accepted:
            result.acknowledged?Stop::acknowledged:Stop::refused;
        if(result.acknowledged)increment(at(r.op).acknowledged);
        if(result.accepted)accept(r.op);
        else if(!result.acknowledged){increment(at(r.op).rejected);reject_service(r);}
        pending.reduced=true;last_reduced=event;
        driver.invalidate();
        pending.returned=driver.epoch();
        if(!r.epoch.same_turn(pending.returned))seal();
        return {pending.stop,event};
    } catch(...) {
        // preflight exceptions issued no mutation; in-flight exceptions may
        // have committed effects. Neither permits continuation/retry.
        if(pending.in_flight){increment(at(r.op).uncertain);pending.stop=Stop::uncertain;}
        else if(!pending.reduced)pending.stop=Stop::denied;
        pending.in_flight=false;pending.reduced=true;last_reduced=event;
        driver.invalidate();seal();throw;
    }
}
bool Ledger::observe(std::uint64_t event,Epoch e,bool submit_started,bool implicit_lock_basic,bool effect_observed) {
    if(!open||pending.event!=event||!pending.reduced||
        !pending.request.epoch.same_turn(e)||pending.after_observed)return false;
    if(pending.stop!=Stop::accepted&&pending.stop!=Stop::acknowledged&&pending.stop!=Stop::refused)return false;
    // Submit can auto-hit a lock. Only positively bracketed target HP evidence
    // may identify that implicit basic; an allowance change is insufficient.
    if(pending.request.op==Op::submit) {
        if(submit_started&&implicit_lock_basic){seal();return false;}
        if(submit_started){accept(Op::submit);pending.stop=Stop::accepted;}
        if(implicit_lock_basic) {
            if(basics>=2||primitives>=4){seal();return false;}
            ++basics;++primitives;pending.implicit_basic=true;
        }
        if(!submit_started&&!implicit_lock_basic)seal();
    }
    pending.after_observed=true;
    pending.effects_observed=effect_observed||submit_started||implicit_lock_basic;
    if(pending.effects_observed)increment(at(pending.request.op).observed);
    origin.revision=e.revision;return true;
}
bool Ledger::charge_contact(std::uint64_t event) {
    if(pending.event!=event||pending.contact_charged||
        pending.stop!=Stop::refused||!pending.request.service||
        pending.request.target.contact<0||
        (pending.request.op!=Op::step&&pending.request.op!=Op::dash))return false;
    pending.contact_charged=true;return true;
}
}
