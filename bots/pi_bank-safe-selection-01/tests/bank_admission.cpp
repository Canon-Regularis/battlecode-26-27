#include "bot.h"
#include "route_plan.h"
#include <cstdlib>
#include <iostream>
#include <string>
using namespace lp;
static Snapshot scene;
static RouteStatus route_result=RouteStatus::moved;
static int camp_attacks=0,retreats=0,route_calls=0,ward_calls=0,checks=0;
static void require(bool ok,const char* message){++checks;if(!ok){std::cerr<<"FAIL: "<<message<<" (check "<<checks<<")\n";std::exit(1);}}
namespace lp {
void World::init() {}
#ifndef BSS_REAL_REFRESH
void World::refresh(const Snapshot&,Memory&) {}
#endif
const Snapshot& observe(){scene.round=host_round;scene.bag=actors[0].bag;scene.alive=actors[0].alive;scene.pos=actors[0].pos;return scene;}
void invalidate_observations() {}
unsigned observation_version(){return host_version;}
void shop(Memory&) {}
void load_draft_routes(World&) {}
int preferred_loop_camp(World&,const std::vector<bool>&){return -1;}
void advance_loop(World&,int) {}
RouteStatus move_to(bitboard,bool,TurnBudget&,Memory& m,bool){++route_calls;if(route_result==RouteStatus::moved){++moves;m.last_distance=0;}else if(route_result==RouteStatus::no_route_now)++m.blocked;return route_result;}
bool retreat(TurnBudget&,Memory&){++retreats;return true;}
bool fight([[maybe_unused]] World& w,int task,bool){if(task>=0&&self().can_attack()){++camp_attacks;++attacks;
#ifdef BSS_REAL_REFRESH
host_camp_hp-=50;++host_version;
#else
w.camps[task].remaining=std::max(0.0f,w.camps[task].remaining-50);
#endif
return true;}return false;}
bool defend_cast(const Snapshot&){return false;}
void optional_ward(const World&,int){++ward_calls;}
}
static Bot fresh(int round=100){
    host_round=round;host_fuel=100000;host_score=0;score_calls=field_calls=attacks=moves=submissions=0;
    after_field=after_score=during_scoring={};on_camp_query={};camp_queries.clear();vision::local_camps.clear();host_camp_hp=10000;host_version=0;vision::locks.clear();actors={};actors[0].bag=8;
    camp_attacks=retreats=route_calls=ward_calls=0;route_result=RouteStatus::moved;
    scene=Snapshot{};scene.alive=true;scene.hp=scene.max_hp=1000;scene.pos={2,2};scene.round=round;scene.bag=8;
    scene.allies={champion{0}};scene.visible.draw_chebyshev({10,10},30);
    Bot bot;bot.world.width=W;bot.world.height=H;bot.world.columns=bot.world.rows=2;bot.world.roster={champion{0}};
    bot.world.altars={{12,2},{12,12}};bot.world.altar_retry={0,0};
    Objective o;o.anchor={3,2};o.tiles.set({3,2});o.approach=around({3,2},1);o.lifecycle=1;o.seen=round;o.remaining=o.design_health=50;
    bot.world.camps.push_back(o);bot.memory.bag_since=round-80;bot.memory.prior_bag=8;
    observe();return bot;
}
static void unavailable(){scene.risk.draw_chebyshev({10,10},30);}
static void divided(){for(int y=0;y<H;++y)scene.risk.set({7,y});}
static void expired(Bot& b){b.memory.task=0;b.memory.task_started=host_round-90;b.memory.progressed=host_round;}
static AltarSelection select(Bot& b,int prev=-1){TurnBudget budget{host_round};return choose_altar(b.world,observe(),budget,prev);}
static void status(AltarSelection r,AltarStatus wanted,const char* msg){require(r.status==wanted,msg);require((wanted==AltarStatus::selected)==(r.index>=0),"only selected has valid index");}
[[maybe_unused]] static void selection_checks(){
    auto b=fresh();unavailable();status(select(b,0),AltarStatus::unavailable,"unreachable previous revoked, no sentinel hysteresis");
    b=fresh();b.world.altar_retry={110,110};status(select(b,0),AltarStatus::cooldown,"cooling previous not selected");
    b=fresh();divided();b.world.altars={{12,2},{4,2}};b.world.altar_retry={110,110};status(select(b,0),AltarStatus::cooldown,"unreachable cooling plus reachable cooling is cooldown");
    b.world.altar_retry[0]=0;status(select(b,0),AltarStatus::cooldown,"unreachable eligible does not count as spatial candidate");
    b.world.altar_retry[1]=0;auto r=select(b,0);status(r,AltarStatus::selected,"reachable alternative selected");require(r.index==1,"unreachable previous cannot win margin");
    b=fresh();b.world.altars={{5,2},{2,5}};r=select(b);require(r.index==0,"equal scores use original first index");r=select(b,1);require(r.index==1,"eligible previous wins ordinary tie");
    b.world.altars={{5,2},{8,2}};require(select(b,1).index==1,"margin three retained");b.world.altars[1]={9,2};require(select(b,1).index==0,"outside margin switches");
    b=fresh();b.world.altars={{5,2},{2,5}};b.world.altar_retry={0,110};require(select(b,1).index==0,"cooling reachable previous cannot win");
    b=fresh();b.world.altars={{5,2},{2,5}};scene.visible.set({5,2},false);require(select(b).index==1,"old hidden penalty retained");
    scene.visible.set({5,2});vision::locks={{{5,2},5}};require(select(b).index==1,"old enemy lock penalty retained");
    vision::locks.clear();actors[1].pos={6,2};scene.foes={champion{1}}; // both within six: still tie
    require(select(b).index==0,"old equal enemy penalties preserve tie");
    b.world.altars={{5,2},{2,9}};actors[1].pos={6,0};require(select(b).index==1,"six-point enemy penalty changes the winner");
    b=fresh();b.world.altars.clear();b.world.altar_retry.clear();status(select(b),AltarStatus::unavailable,"admitted no-altars is unavailable");require(field_calls==1,"no-altars still consumes admitted field");
    b=fresh();b.world.altar_retry={110,110};unavailable();status(select(b),AltarStatus::unavailable,"cooling unreachable is unavailable, not cooldown");
    b=fresh();host_fuel=29999;status(select(b,0),AltarStatus::deferred,"admission denial typed deferred");require(field_calls==0,"denial builds no field");
    b=fresh();TurnBudget capped{host_round,1};status(choose_altar(b.world,observe(),capped,0),AltarStatus::deferred,"selector field cap");require(field_calls==0,"cap builds no extra field");
    for(int mode=0;mode<6;++mode){
        b=fresh();b.memory.altar=0;b.memory.queue_started=91;b.memory.bank_unavailable_round=95;
        if(mode==0)host_fuel=25000;
        if(mode==1)after_field=[] {++host_round;};
        if(mode==2)after_field=[] {host_fuel=4999;};
        if(mode==3)during_scoring=[] {++host_round;};
        if(mode==4)during_scoring=[] {host_fuel=4999;};
        TurnBudget budget{host_round,mode==5?1:0};auto result=choose_altar(b.world,observe(),budget,0);
        status(result,AltarStatus::deferred,"incomplete work defers");apply_altar_selection(result,scene,budget,b.memory);
        require(b.memory.altar==0&&b.memory.queue_started==91&&b.memory.bank_unavailable_round==95,"deferred application preserves commitment queue admission");
    }
    b=fresh();after_field=[] {host_fuel=25000;};status(select(b),AltarStatus::selected,"25000 after field completes despite admission threshold");
    b=fresh();unavailable();after_field=[] {host_fuel=5000;};status(select(b),AltarStatus::unavailable,"reserve boundary completes");
    for(bool rollover:{false,true}){
        b=fresh();unavailable();b.memory.altar=0;b.memory.queue_started=90;TurnBudget budget{host_round};auto result=choose_altar(b.world,observe(),budget,0);
        after_score=[rollover] {if(rollover)++host_round;else host_fuel=4999;};apply_altar_selection(result,scene,budget,b.memory);
        require(b.memory.altar==0&&b.memory.queue_started==90&&b.memory.bank_unavailable_round==-1,"urgency query rollover/fuel cannot commit failure");
    }
}
[[maybe_unused]] static void caller_checks(){
    for(bool expiry:{false,true})for(bool cooling:{false,true}){
        auto b=fresh(99);b.memory.altar=0;b.memory.queue_started=90;
        if(cooling)b.world.altar_retry={110,110};else unavailable();
        if(expiry){expired(b);b.play_turn();}else {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
        require(b.memory.altar==-1&&b.memory.queue_started==-1,"both caller sites revoke completed failure commitment and queue");
        require(b.memory.bank_unavailable_round==(cooling?-1:99),"only unavailable arms work");
        require(camp_attacks==0,"due failure never dispatches same-round camp action");
    }
    auto b=fresh(99);b.memory.altar=0;b.memory.blocked=2;route_result=RouteStatus::no_route_now;
    {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
    require(b.memory.altar==-1&&b.world.altar_retry[0]==102,"normal selected route failure retains retry behavior");require(b.memory.bank_unavailable_round==-1,"route failure alone never arms work");
    b=fresh(99);b.world.altars={{3,2}};b.world.altar_retry={0};actors[1].pos={2,3};actors[1].bag=20;actors[1].submit=true;scene.allies.push_back(champion{1});
    {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
    require(b.memory.altar==0&&b.memory.queue_started==99&&submissions==0,"legitimate queue intact");require(b.memory.bank_unavailable_round==-1,"queue does not arm admission");
    b=fresh(99);b.world.altars={{3,2}};b.world.altar_retry={0};vision::locks={{{3,2},5}};
    {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
    require(attacks==1&&submissions==0&&b.memory.altar==0,"enemy lock attack retained");require(b.memory.bank_unavailable_round==-1,"lock progress does not arm admission");
    b=fresh(99);b.world.altars={{3,2}};b.world.altar_retry={0};
    {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
    require(submissions==1&&b.memory.bank_bag==8&&b.memory.state==State::explore,"bank caller accounts actual channel start");b.play_turn();require(b.memory.state==State::bank&&camp_attacks==0,"active tribute dispatch intact");
    b=fresh(99);unavailable();expired(b);actors[0].submit=true;b.play_turn();
    require(b.memory.bank_unavailable_round==99&&b.memory.state==State::bank,"maintenance may record dormant admission during channel");
    int oldfields=field_calls;host_round=100;b.play_turn();require(b.memory.state==State::bank&&camp_attacks==0&&field_calls==oldfields&&actors[0].submit,"dormant window never executes work or cancels channel");
    host_round=110;b.play_turn();require(b.memory.bank_unavailable_round==-1&&actors[0].submit,"channel time consumes window without extending it");
    b=fresh(99);expired(b);b.memory.altar=0;b.memory.queue_started=90;b.memory.bag_since=99;host_fuel=25000;b.play_turn();
    require(b.memory.altar==0&&b.memory.queue_started==90&&b.memory.state==State::prepare_bank,"young-bag deferred task expiry preserves old commitment and preemption");
    require(b.memory.bank_unavailable_round==-1,"deferred expiry cannot stamp failure");
    b=fresh(99);expired(b);b.memory.altar=1;b.memory.bag_since=99;b.world.altars={{5,2},{2,5}};b.play_turn();require(b.memory.altar==0,"completed task expiry retains default no previous preference");
    b=fresh(99);host_fuel=25000;b.memory.altar=0;b.memory.queue_started=90;b.play_turn();require(b.memory.altar==0&&route_calls>0,"deferred bank reselection retains normal old approach execution");
}
[[maybe_unused]] static void caller_rollover_checks(){
    for(bool expiry:{false,true})for(bool fuel:{false,true}) {
        auto b=fresh(99);unavailable();b.memory.altar=0;b.memory.queue_started=90;
        // No active stamp: task maintenance does not query urgency. The first
        // score query belongs to completed-failure application at either site.
        after_score=[fuel] {if(score_calls==1){if(fuel)host_fuel=4999;else ++host_round;}};
        if(expiry){expired(b);b.play_turn();}else {TurnBudget budget{host_round};bank(b.world,budget,b.memory);}
        require(b.memory.altar==0&&b.memory.queue_started==90&&b.memory.bank_unavailable_round==-1,"both callers preserve old state when failure application urgency becomes stale");
    }
}
[[maybe_unused]] static void transition_checks(){
    auto b=fresh(99);unavailable();b.play_turn();require(b.memory.bank_unavailable_round==99&&b.memory.altar==-1,"completed due failure stamps F");
    require(bank_due(8,b.memory.bag_since,99,0),"old bag remains due in failure round");require(camp_attacks==0&&field_calls==1&&b.memory.state==State::prepare_bank,"no same-turn admission or extra selector field");
    for(int r=100;r<=109;++r){
        host_round=r; // Keep the observed task progressing, but do not pause its actual timers.
        if(b.memory.task>=0)b.memory.progressed=r;
        b.play_turn();require(b.memory.bank_unavailable_round==99,"window never refreshes during work");require(camp_attacks>0&&b.memory.task==0,"admitted production dispatch selects and executes ordinary camp");
        require(actors[0].bag==8&&b.memory.bag_since==19&&b.memory.prior_bag==8&&b.memory.life==0,"admission preserves bag age size prior and life");
        require(bank_due(8,b.memory.bag_since,r,0)&&b.memory.state==State::capture,"still-due bag can perform ordinary work F+1 through F+10");
    }
    host_round=110;int before=camp_attacks;host_fuel=25000;b.play_turn();require(b.memory.bank_unavailable_round==-1&&b.memory.state==State::prepare_bank&&camp_attacks==before,"F+11 restores bank preemption without expiry refresh");
    b=fresh(99);unavailable();b.play_turn();for(int r=100;r<=109;++r){host_round=r;host_fuel=25000;b.play_turn();require(b.memory.bank_unavailable_round==99&&camp_attacks==0,"deferred work selector consumes absolute window");}host_round=110;b.play_turn();require(b.memory.bank_unavailable_round==-1,"deferral never extends window");
    b=fresh(99);unavailable();b.play_turn();host_round=100;expired(b);b.memory.state=State::capture;bool field_in_bank=false;after_field=[&] {field_in_bank=b.memory.state==State::prepare_bank;};b.play_turn();require(b.memory.bank_unavailable_round==100&&field_calls==2&&camp_attacks==0&&field_in_bank,"admitted entry skips legacy expiry preselector, normal bank owns completed retry");
    // The ordinary branch gets the next field with no live task at entry, including task-expiry's failure path.
    b=fresh(99);unavailable();b.world.camps.push_back(b.world.camps[0]);expired(b);b.play_turn();require(field_calls==1&&b.memory.task==-1,"expiry completed failure consumes only field in F");host_round=100;b.play_turn();require(field_calls==2&&b.memory.task==1&&camp_attacks>0,"expiry cannot steal next admitted eligible camp selector field");
    b=fresh(99);unavailable();b.play_turn();host_round=100;b.world.camps[0].design_health=20000;b.play_turn();require(b.memory.task==-1&&camp_attacks==0&&b.memory.state==State::explore&&b.stats.defers==0,"completed no eligible camp explores without claiming productive farming");
    for(bool cooling:{false,true}){
        b=fresh(99);expired(b);b.memory.bag_since=99;b.memory.altar=0;if(cooling)b.world.altar_retry={110,110};else unavailable();b.play_turn();
        require(b.memory.altar==-1&&b.memory.task==-1&&b.memory.state==State::explore,"young non-due bag keeps normal ordinary dispatch in F");
        require(b.stats.defers==1&&field_calls==1&&camp_attacks==0,"young same-turn camp selector is deferred, not completed no-camp; counters not reset");
        require(b.memory.bank_unavailable_round==(cooling?-1:99),"young unavailable stamp grants no same-turn admission; cooldown does not arm");
    }
    for(int mode=0;mode<7;++mode){
        b=fresh(100);b.memory.bank_unavailable_round=99;b.memory.task=0;b.memory.task_started=b.memory.progressed=100;
        if(mode==0)actors[0].bag=0;
        if(mode==1)actors[0].alive=false;
        if(mode==2){b.world.camps[0].lifecycle=3;b.world.camps[0].seen=100;b.world.camps[0].respawn=200;}
        if(mode==3)b.memory.progressed=90;
        if(mode==4)host_score=992;
        if(mode==5)host_round=1974; // 1974+20+1+5=2000
        if(mode==6){scene.enemies=2;scene.friends=1;scene.foes={champion{1}};}
        b.play_turn();require(b.memory.bank_unavailable_round!=99,"zero/death/completion/stall/win/endgame/abandon clears old window");
        if(mode==1)require(b.memory.life==1&&b.memory.state==State::dead,"death keeps original life bookkeeping");
        if(mode==4||mode==5)require(b.memory.state==State::prepare_bank&&camp_attacks==0&&b.memory.bank_unavailable_round==-1,"hard urgency overrides admission immediately");
    }
    b=fresh(100);b.memory.bank_unavailable_round=99;actors[0].bag=35;b.play_turn();require(b.memory.task==0&&camp_attacks>0&&b.memory.bank_unavailable_round==99,"size 35 alone remains deferrable");
    b=fresh(100);b.memory.bank_unavailable_round=99;b.memory.altar=0;b.play_turn();require(b.memory.state==State::capture&&camp_attacks>0,"admission suppresses whole altar-or-due expression");
    b=fresh(100);b.memory.bank_unavailable_round=99;TurnBudget budget{100};apply_altar_selection({AltarStatus::selected,1},observe(),budget,b.memory);require(b.memory.altar==1&&b.memory.bank_unavailable_round==-1,"selected clears admission");
    b=fresh(99);unavailable();scene.enemies=2;scene.foes={champion{1}};b.play_turn();require(b.memory.state==State::escape&&retreats==1&&field_calls==0&&b.memory.bank_unavailable_round==-1,"danger before search cannot fabricate failure");
    b=fresh(100);b.memory.bank_unavailable_round=99;actors[0].recall=true;b.play_turn();require(b.memory.state==State::recall&&camp_attacks==0&&b.memory.bank_unavailable_round==99,"recall safety consumes time without clearing or extending window");
    b=fresh(100);b.memory.bank_unavailable_round=99;scene.spawn=true;scene.hp=500;b.play_turn();require(b.memory.state==State::healing&&camp_attacks==0,"healing priority intact");
    b=fresh(100);b.memory.bank_unavailable_round=99;scene.spawn=true;scene.incoming=1;b.play_turn();require(b.memory.state==State::defend&&camp_attacks==0,"spawn defense priority intact");
    // Boundary expression is shared with production bank_due, not duplicated in this fixture.
    require(!hard_bank_due(8,1973,0)&&hard_bank_due(8,1974,0),"default endgame hard urgency boundary");
    require(!hard_bank_due(0,1999,1000)&&hard_bank_due(8,100,992),"positive-bag winning urgency");
}
#ifndef BSS_REAL_REFRESH
int main(){selection_checks();caller_checks();caller_rollover_checks();transition_checks();std::cout<<"PASS: "<<checks<<" production selection/application/dispatch assertions\n";}

#endif
