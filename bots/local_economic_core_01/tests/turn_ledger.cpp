#include "turn_ledger.h"
#include <iostream>
#include <stdexcept>
using namespace lp::action;
int checks=0;
#define CHECK(...) do {++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
struct Host:Driver {
    Epoch now{7,0,10,1};
    bool allowed=true,success=true,ack=false,throw_call=false,
        roll_preflight=false,roll_call=false,roll_return=false,revision_preflight=false;
    int calls=0,invalidations=0,reads=0;
    Epoch epoch()override {
        if(roll_return&&calls&&invalidations){++now.round;roll_return=false;}
        return now;
    }
    bool preflight(const Request&)override {
        ++reads;if(roll_preflight)++now.round;if(revision_preflight)++now.revision;return allowed;
    }
    CallResult call(const Request&)override {
        ++calls;if(roll_call)++now.round;
        if(throw_call)throw std::runtime_error("SDK effects unknown");
        return {success,ack};
    }
    void invalidate()noexcept override{++now.revision;++invalidations;}
    Request req(Op op,bool service=false,int key=1)const {
        Request r{now,op,{}};r.service=service;r.target.key=key;r.target.contact=42;return r;
    }
};
void begin(Ledger& l,Host& h,Owner owner=Owner::service) {
    CHECK(l.begin(h.now,100000));CHECK(l.handoff(owner,h.now));
}
Result act(Ledger& l,Host& h,Op op,bool service=false,int key=1) {
    return l.perform(h.req(op,service,key),h);
}
void fresh(Ledger& l,Host& h,Result r,bool effect=false) {
    CHECK(l.observe(r.event,h.now,false,false,effect));
}
void shared_facets() {
    Ledger l;Host h;begin(l,h);
    auto step=act(l,h,Op::step,true);CHECK(step.accepted());fresh(l,h,step,true);
    CHECK(l.handoff(Owner::bank,h.now));
    CHECK(act(l,h,Op::step,true,2).stop==Stop::denied);
    auto dash=act(l,h,Op::dash,true);fresh(l,h,dash);
    CHECK(l.steps==1&&l.dashes==1&&l.casts==1&&l.primitives==2);
    CHECK(l.handoff(Owner::recovery,h.now));
    CHECK(act(l,h,Op::shield).stop==Stop::denied);
    auto basic=act(l,h,Op::basic);fresh(l,h,basic);
    CHECK(basic.accepted()&&l.basics==1&&l.primitives==3);
    CHECK(l.counts[static_cast<unsigned>(Op::dash)].accepted==1);
    CHECK(l.at(Op::dash).observed==0); // SDK acceptance isn't observed damage
    CHECK(h.calls==3);
}
void reset_sequences() {
    // Ranged walk -> reset -> basic. The SDK can impose a stricter limit.
    Ledger l;Host h;begin(l,h);
    auto a=act(l,h,Op::step);fresh(l,h,a);
    a=act(l,h,Op::reset);fresh(l,h,a);
    a=act(l,h,Op::basic);fresh(l,h,a);
    CHECK(l.steps==1&&l.casts==1&&l.basics==1&&l.primitives==3);
    h.allowed=false;CHECK(act(l,h,Op::basic).stop==Stop::denied);
    CHECK(l.basics==1&&l.service_rejections==0);
    // Basic kill -> reset -> second basic. A refreshed cooldown cannot grant
    // a second cast, third basic, or a fifth primitive.
    Ledger m;Host k;begin(m,k);
    for(auto op:{Op::basic,Op::reset,Op::basic}){auto r=act(m,k,op);fresh(m,k,r);}
    CHECK(act(m,k,Op::reset).stop==Stop::denied);
    CHECK(act(m,k,Op::cast).stop==Stop::denied);
    CHECK(act(m,k,Op::basic).stop==Stop::denied);
    auto step=act(m,k,Op::step);fresh(m,k,step);
    CHECK(m.primitives==4&&k.calls==4);
}
void failure_accounting() {
    Ledger l;Host h;begin(l,h);h.success=false;
    auto r=act(l,h,Op::step,true);CHECK(r.stop==Stop::refused);
    CHECK(l.service_rejections==1&&l.steps==0&&l.step_attempted);
    CHECK(l.charge_contact(r.event));CHECK(!l.charge_contact(r.event));
    fresh(l,h,r);CHECK(l.handoff(Owner::bank,h.now));
    CHECK(act(l,h,Op::step,true,2).stop==Stop::denied);
    auto other=act(l,h,Op::cast,true);fresh(l,h,other);
    CHECK(l.service_rejections==2);CHECK(!l.charge_contact(other.event));
    CHECK(act(l,h,Op::basic,true,4).stop==Stop::denied);
    CHECK(l.handoff(Owner::recovery,h.now));h.success=true;
    auto defense=act(l,h,Op::shield);CHECK(defense.accepted());fresh(l,h,defense);
    CHECK(l.casts==1&&l.service_rejections==2);
    // Same failed service target can't be retried after new observations or
    // owner change, even when the primitive wasn't spent.
    Ledger m;Host k;begin(m,k);k.success=false;
    auto b=act(m,k,Op::basic,true);fresh(m,k,b);
    CHECK(m.handoff(Owner::bank,k.now));
    CHECK(act(m,k,Op::basic,true).stop==Stop::denied);
    k.success=true;auto different=act(m,k,Op::basic,true,2);CHECK(different.accepted());
}
void permission_denial() {
    Ledger l;Host h;begin(l,h);h.allowed=false;
    auto r=act(l,h,Op::step,true);CHECK(r.stop==Stop::denied);
    CHECK(l.step_attempted&&h.calls==0&&l.at(Op::step).issued==0);
    CHECK(l.service_rejections==0&&!l.charge_contact(r.event));
    h.allowed=true;CHECK(l.handoff(Owner::recovery,h.now));
    CHECK(act(l,h,Op::step).stop==Stop::denied);
    auto dash=act(l,h,Op::dash);CHECK(dash.accepted());
}
void stale_and_uncertain() {
    for(int phase=0;phase<5;++phase) {
        Ledger l;Host h;begin(l,h);auto request=h.req(Op::basic,true);
        if(phase==0)++request.epoch.revision;
        if(phase==1)h.roll_preflight=true;
        if(phase==2)h.revision_preflight=true;
        if(phase==3)h.roll_call=true;
        if(phase==4)h.roll_return=true;
        auto r=l.perform(request,h);
        CHECK(!l.open);
        if(phase<3){CHECK(r.stop==Stop::stale&&h.calls==0&&l.basics==0);}
        else {CHECK(r.accepted()&&h.calls==1&&l.basics==1&&l.at(Op::basic).accepted==1);}
        CHECK(act(l,h,Op::basic).stop==Stop::sealed);
        l.finish();l.finish();CHECK(l.basics==(phase>=3?1u:0u));
    }
    Ledger l;Host h;begin(l,h);h.throw_call=true;
    bool threw=false;try{act(l,h,Op::basic,true);}catch(const std::runtime_error&){threw=true;}
    CHECK(threw&&!l.open&&h.calls==1&&h.invalidations==1);
    CHECK(l.at(Op::basic).uncertain==1&&l.basics==0);
    CHECK(!l.pending.in_flight&&l.pending.reduced);
}
void submission_and_channels() {
    for(int outcome=0;outcome<3;++outcome) {
        Ledger l;Host h;begin(l,h,Owner::bank);h.success=false;h.ack=true;
        auto r=act(l,h,Op::submit);CHECK(r.stop==Stop::acknowledged);
        CHECK(l.submit_attempted&&l.at(Op::submit).accepted==0&&l.basics==0);
        CHECK(l.observe(r.event,h.now,outcome==0,outcome==1));
        CHECK(!l.observe(r.event,h.now,true));
        CHECK(l.at(Op::submit).accepted==(outcome==0?1u:0u));
        CHECK(l.basics==(outcome==1?1u:0u));
        CHECK(l.open==(outcome!=2)); // unresolved start stops continuation
        CHECK(!act(l,h,Op::submit).accepted());CHECK(h.calls==1);
    }
    Ledger l;Host h;begin(l,h,Owner::recovery);
    auto r=act(l,h,Op::cancel_recall);CHECK(r.accepted());fresh(l,h,r);
    CHECK(act(l,h,Op::recall).stop==Stop::denied);
    CHECK(act(l,h,Op::cancel_recall).stop==Stop::denied);
    Ledger m;Host k;begin(m,k,Owner::recovery);
    m.channel_history(true,false,false);
    CHECK(act(m,k,Op::recall).stop==Stop::denied);
    CHECK(m.at(Op::recall).admitted==0); // observed native flag isn't a local call
}
void lifecycle_and_budgets() {
    Ledger l;Host h;begin(l,h);l.fields=1;l.planning_jobs=1;
    l.queries_issued=6;l.queries_completed=5;l.recovery_captures=3;
    auto r=act(l,h,Op::basic);fresh(l,h,r);
    CHECK(l.handoff(Owner::recovery,h.now));
    CHECK(l.fields==1&&l.planning_jobs==1&&l.queries_issued==6&&l.recovery_captures==3);
    CHECK(!l.begin(h.now,100000));CHECK(l.basics==1);
    l.finish();CHECK(!l.begin(h.now,100000)&&!l.open);
    ++h.now.round;CHECK(l.begin(h.now,100000));CHECK(l.basics==0&&l.fields==0&&l.recovery_captures==0);
    CHECK(l.next_event>r.event&&l.last_reduced==r.event);
    CHECK(l.reconcile_life(1));h.now.life=1;
    CHECK(l.handoff(Owner::service,h.now));
    auto b=act(l,h,Op::basic);fresh(l,h,b);
    CHECK(!l.reconcile_life(2)&&!l.open); // no allowance renewal on unexpected death
    Ledger m;Host k;begin(m,k);unsigned fuel=0;
    m.sample_fuel(k.now.round,90000);CHECK(m.fuel_delta(fuel)&&fuel==10000);
    m.sample_fuel(k.now.round+1,100000);CHECK(!m.fuel_delta(fuel));
}
void optional_and_after_capture() {
    Ledger l;Host h;begin(l,h,Owner::optional);
    for(int i=0;i<40;++i){auto r=act(l,h,Op::item_buy);CHECK(r.accepted());fresh(l,h,r);}
    CHECK(act(l,h,Op::item_buy).stop==Stop::denied);
    auto ward=act(l,h,Op::ward);fresh(l,h,ward);CHECK(act(l,h,Op::ward).stop==Stop::denied);
    CHECK(l.casts==0&&l.primitives==0);
    CHECK(l.handoff(Owner::bank,h.now));h.success=false;
    auto lock=act(l,h,Op::lock_use);fresh(l,h,lock);
    CHECK(act(l,h,Op::lock_use).stop==Stop::denied&&l.service_rejections==0);
    // Acceptance followed by failed after-capture cannot cause another call.
    Ledger m;Host k;begin(m,k);auto basic=act(m,k,Op::basic);
    CHECK(basic.accepted()&&act(m,k,Op::cast).stop==Stop::denied&&k.calls==1);
    fresh(m,k,basic);CHECK(act(m,k,Op::cast).accepted());
}
int main() {
    try {
        shared_facets();reset_sequences();failure_accounting();permission_denial();
        stale_and_uncertain();submission_and_channels();lifecycle_and_budgets();optional_and_after_capture();
        std::cout<<"PASS: "<<checks<<" shared-ledger assertions\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
