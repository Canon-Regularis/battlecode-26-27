#include "economic_owner.h"
#include <iostream>
#include <stdexcept>
using namespace lp::economic;
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
Observation scene() {
    Observation o;o.complete=true;o.has_altars=true;o.self.epoch={1,0,10,1};
    o.self.hp=o.self.max_hp=1000;o.self.alive=true;return o;
}
Candidate camp(int id,std::uint64_t gems,std::uint64_t turns=20) {
    Candidate c;c.key={id,0,0,Purpose::gems,Role::worker};c.anchor={id,2};
    c.approach=c.service=c.recipient=c.conversion=Evidence::ready;
    c.own_gems=gems;c.work_turns=turns;c.estimate_priced=true;c.conditional=false;return c;
}
Candidate bank(int id,std::uint64_t turns,bool conditional=false) {
    auto c=camp(id,0,0);c.key.purpose=conditional?Purpose::observe_access:Purpose::convert;
    c.key.role=Role::carrier;c.tribute_turns=turns;c.conditional=conditional;
    if(conditional)c.conversion=Evidence::unknown;
    return c;
}
void rates_and_selection() {
    CHECK(compare({1,3,true},{2,6,true})==0);
    CHECK(compare({UINT64_MAX,UINT64_MAX-1,true},{UINT64_MAX-1,UINT64_MAX,true})>0);
    CHECK(compare({0,UINT64_MAX,true},{UINT64_MAX,UINT64_MAX,true})<0);
    for(std::uint64_t a=1;a<=19;++a)for(std::uint64_t b=1;b<=19;++b) {
        const auto order=compare({UINT64_MAX-a,UINT64_MAX-b,true},{UINT64_MAX-b,UINT64_MAX-a,true});
        CHECK((a==b&&order==0)||(a<b&&order>0)||(a>b&&order<0));
    }
    auto o=scene();o.self.bag=10;Owner owner;
    auto d=owner.update(o,{camp(1,10,40),bank(0,20)});
    CHECK(d.decision==Decision::task&&d.task.key.purpose==Purpose::convert); // exact tie -> bank
    Owner next;d=next.update(o,{camp(1,20,40),bank(0,20)});
    CHECK(d.task.key.purpose==Purpose::gems); // same current bag in both numerators
    // No hard 90-work cap, no compulsory shop/funding phase.
    o.self.bag=0;Owner large;d=large.update(o,{camp(9,343,1000)});
    CHECK(d.decision==Decision::task&&d.task.key.object==9);
    Owner unpriced;auto unknown=camp(9,343);unknown.estimate_priced=false;
    d=unpriced.update(o,{unknown});CHECK(d.decision==Decision::task&&d.task.key.object==9);
    Owner overflow;auto huge=camp(8,UINT64_MAX,UINT64_MAX);huge.delivery_hops=1;
    d=overflow.update(o,{huge});CHECK(d.decision==Decision::task); // unpriced contact, not impossible
}
void commitment_and_suppression() {
    auto o=scene();Owner owner;auto first=camp(1,10),better=camp(2,100);
    auto d=owner.update(o,{first});CHECK(d.task.key.object==1);
    o.self.epoch.round=1000;d=owner.update(o,{better,first});CHECK(d.task.key.object==1);
    owner.apply({1,first.key,Stop::blocked,Reason::unsafe,77});
    d=owner.update(o,{first});CHECK(d.decision==Decision::no_task);
    // A different frame/fact ID, death and recovery cannot reopen by themselves.
    first.fact=78;++o.self.epoch.revision;d=owner.update(o,{first});CHECK(d.decision==Decision::no_task);
    o.self.alive=false;++o.self.epoch.life;CHECK(owner.update(o,{first}).decision==Decision::dead);
    o.self.alive=true;CHECK(owner.update(o,{first}).decision==Decision::no_task);
    CHECK(!owner.reopen({first.key,Reason::occupied,78,true}));
    CHECK(!owner.reopen({first.key,Reason::unsafe,77,true}));
    CHECK(!owner.reopen({first.key,Reason::unsafe,78,false}));
    CHECK(owner.reopen({first.key,Reason::unsafe,78,true}));
    CHECK(!owner.reopen({first.key,Reason::unsafe,78,true}));
    CHECK(owner.update(o,{first}).task.key.object==1);
    owner.apply({2,first.key,Stop::work,Reason::none,0,true,15,true,false});
    owner.apply({2,first.key,Stop::work,Reason::none,0,true,15,true,false});
    CHECK(owner.confirmed_damage==15&&owner.observed_gold_receipts==1);
    owner.apply({3,first.key,Stop::allowance});
    CHECK(owner.update(o,{}).task.present);
    owner.apply({4,first.key,Stop::deferred});CHECK(owner.update(o,{},false).task.present);
}
void roles() {
    auto o=scene();Owner owner;auto c=camp(1,10);CHECK(owner.update(o,{c}).task.present);
    GroupObservation g;g.object=1;g.cycle=0;g.fresh=true;g.life=Life::reward;
    g.allied_holder=true;g.capture_timer=3;g.role_fact=10;o.groups={g};
    auto d=owner.update(o,{c});CHECK(d.decision==Decision::no_task); // redundant helper released
    CHECK(owner.observed_gem_receipts==0);
    Owner takeover;g.holder_departing=true;g.earliest_departure=2;o.groups={g};
    CHECK(takeover.update(o,{c}).task.present);
    d=takeover.update(o,{c});CHECK(d.task.key.role==Role::takeover);
    Owner enough;g.earliest_departure=3;o.groups={g};CHECK(enough.update(o,{c}).decision==Decision::no_task);
    Owner holder;g.self_occupant=true;g.allied_holder=false;o.groups={g};holder.update(o,{c});
    d=holder.update(o,{c});CHECK(d.task.key.role==Role::holder&&d.task.phase==Phase::hold);
    g.contested=true;o.groups={g};d=holder.update(o,{c});CHECK(d.task.key.role==Role::defender);
    g.life=Life::respawning;o.groups={g};d=holder.update(o,{});CHECK(!d.task.present);
}
void access_and_gold() {
    auto o=scene();o.self.bag=20;Owner owner;auto b=bank(0,10,true),c=camp(1,100,1);
    auto d=owner.update(o,{c,b});CHECK(d.task.key.purpose==Purpose::observe_access&&owner.held_bag==20);
    owner.apply({1,b.key,Stop::access_unavailable,Reason::access,10});
    // Changing the purpose cannot mint a fresh access attempt.
    auto convert=bank(0,10,false),gold=camp(2,0,10);gold.key.purpose=Purpose::gold;gold.own_gold=40;
    d=owner.update(o,{convert,c,gold});CHECK(d.task.key.purpose==Purpose::gold&&d.needs_conversion);
    CHECK(owner.held_bag==20); // useful gold doesn't pretend the existing bag is bankable
    auto win=bank(3,2);win.winning_start=true;
    d=owner.update(o,{win});CHECK(d.task.key.purpose==Purpose::convert&&d.task.key.object==3);
    // No altar maps use gold without a gem/gold exchange coefficient.
    Owner noaltar;o.has_altars=false;o.self.bag=0;
    d=noaltar.update(o,{c,gold});CHECK(d.task.key.purpose==Purpose::gold);
}
void safety_and_disposition() {
    auto o=scene();Owner owner;auto c=camp(1,10);owner.update(o,{c});
    o.self.hp=340;CHECK(owner.update(o,{c}).decision==Decision::recovery);
    o.self.hp=500;CHECK(owner.update(o,{c}).decision==Decision::recovery);
    o.self.hp=550;CHECK(owner.update(o,{c}).decision==Decision::task);
    CHECK(owner.task().key.object==1);
    o.self.channel=Channel::submit;o.self.hp=10;o.self.danger=true;
    CHECK(owner.update(o,{c}).decision==Decision::protected_channel);
    o.self.channel=Channel::teleport;CHECK(owner.update(o,{c}).decision==Decision::protected_channel);
    Owner events;o=scene();o.self.bag=30;o.self.channel=Channel::submit;events.update(o,{});
    o.self.channel=Channel::none;o.self.bag=0;o.self.score=30;
    auto d=events.update(o,{});CHECK(d.disposition==Disposition::possible_deposit&&!d.needs_conversion);
    Owner lost;o.self.bag=30;o.self.score=0;lost.update(o,{});o.self.alive=false;o.self.bag=0;
    CHECK(lost.update(o,{}).disposition==Disposition::loss);
    Owner unknown;o.self.alive=true;o.self.bag=30;unknown.update(o,{});o.self.bag=0;
    CHECK(unknown.update(o,{}).disposition==Disposition::unknown);
    Owner deferred;o=scene();o.complete=false;
    CHECK(deferred.update(o,{c}).decision==Decision::deferred&&!deferred.task().present);
}
int main(){try{rates_and_selection();commitment_and_suppression();roles();access_and_gold();safety_and_disposition();
    std::cout<<"PASS: "<<checks<<" economic-owner assertions (synthetic owned observations)\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
