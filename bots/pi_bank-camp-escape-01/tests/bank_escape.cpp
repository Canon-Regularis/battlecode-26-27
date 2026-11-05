// Links the unmodified production bank body against the real SDK header and
// deterministic host/link substitutes. This is a caller contract, not gameplay.
#include "economy.h"
#include <cstdlib>
#include <iostream>
using namespace lp;
namespace {
Snapshot snapshot;
int now=113, round_queries=0, cross_on_query=0, observes=0;
int approaches=0, retreats=0, selections=0, submissions=0, fights=0;
int chosen=0, blocked_after=1;
unsigned fuel=60000;
RouteStatus route=RouteStatus::no_route_now;
bool cross_in_move=false,cross_in_observe=false,escape_moves=false,arrive=false;
bool refreshed_camp=true;
float refreshed_incoming=60;
std::uint32_t state=1|8;
World* active_world=nullptr;
bool expect_cleared=false;
void check(bool ok,const char* message) {
    if(!ok){std::cerr<<"FAIL: "<<message<<'\n';std::exit(1);}
}
void reset(World& w,Memory& m,TurnBudget& b) {
    snapshot=Snapshot{};snapshot.round=113;snapshot.pos={1,1};snapshot.bag=7;
    snapshot.camp_hit=true;snapshot.incoming=60;
    now=113;round_queries=cross_on_query=observes=0;
    approaches=retreats=selections=submissions=fights=0;
    chosen=0;blocked_after=1;fuel=60000;route=RouteStatus::no_route_now;
    cross_in_move=cross_in_observe=escape_moves=arrive=expect_cleared=false;
    refreshed_camp=true;refreshed_incoming=60;state=1|8;
    w=World{};w.altars={{6,6}};w.altar_retry={0};w.slot=0;
    m=Memory{};m.altar=0;m.bank_bag=91;m.bank_score=92;
    b=TurnBudget{113};active_world=&w;
}
void failed(World& w,Memory& m,TurnBudget& b,int expected) {
    check(!bank(w,b,m),"failed bank/escape returns false");
    check(retreats==expected,"bounded retreat invocation count");
    check(approaches==1&&observes==2,"one safe approach and existing observation refresh only");
    check(submissions==0&&m.bank_bag==91&&m.bank_score==92,"no false bank accounting");
}
}
namespace lp {
const Snapshot& observe() {
    if(++observes==2){snapshot.camp_hit=refreshed_camp;snapshot.incoming=refreshed_incoming;
        if(cross_in_observe)++now;}
    return snapshot;
}
void invalidate_observations() {}
int choose_altar(World&,const Snapshot&,TurnBudget&,int){++selections;return chosen;}
RouteStatus move_to(bitboard goals,bool safe,TurnBudget&,Memory& m,bool constrained) {
    ++approaches;check(safe&&!constrained&&!goals.is_empty(),"ordinary safe altar approach");
    m.blocked=blocked_after;
    if(arrive)snapshot.pos={5,5};
    if(cross_in_move)++now;
    return route;
}
bool retreat(TurnBudget& b,Memory& m) {
    ++retreats;check(b.current(),"retreat entered in current round");
    if(expect_cleared)check(m.altar==-1&&m.blocked==0&&active_world->altar_retry[0]==116,
        "third failure cooldown and clear precede retreat");
    if(escape_moves)snapshot.pos={2,1};
    return escape_moves;
}
bool fight(World&,int,bool){++fights;return false;}
}
namespace cambc::detail {
extern "C" {
std::int32_t sdk_bc_map_mask(std::int32_t,std::uint64_t* out){*out=0;return 0;}
std::int32_t sdk_spawn_region(std::int32_t,aabb* out){*out={0,0,1,1};return 0;}
std::int32_t sdk_bc_map_symmetry(std::int32_t* out){*out=0;return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* out){*out={};return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t,std::uint32_t,ability_props* out){*out={};return 0;}
std::int32_t sdk_Bitboard_IsZero(const std::uint64_t* board,std::int32_t* out){*out=*board==0;return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t* board,std::int32_t x,std::int32_t y,std::int32_t value){
    auto bit=std::uint64_t{1}<<(y*8+x);if(value)*board|=bit;else *board&=~bit;return 0;
}
std::int32_t sdk_Bitboard_Test(const std::uint64_t* board,std::int32_t x,std::int32_t y,std::int32_t* out){
    *out=(*board&(std::uint64_t{1}<<(y*8+x)))!=0;return 0;
}
std::int32_t sdk_get_settings(game_settings* out){*out={};return 0;}
std::int32_t sdk_bc_metadata(metadata* out){*out={8,8,1,1,1,8,128};return 0;}
std::int32_t sdk_shared_memory_size(std::uint32_t* out){*out=0;return 0;}
std::int32_t sdk_my_champion(){return 0;}
std::int32_t sdk_my_team(){return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* out){*out=0;return 0;}
std::int32_t sdk_read_draft_memory(std::int32_t,void*,std::uint32_t){std::abort();}
std::int32_t sdk_bc_get_last_error(char*,std::uint32_t){return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* out){*out={};return 0;}
std::int32_t sdk_champion(std::uint32_t,champion_info* out){*out={};out->state=state;return 0;}
std::int32_t sdk_champion_gems(std::uint32_t,std::uint32_t* out){*out=7;return 0;}
std::int32_t sdk_champion_consumables(std::uint32_t,std::uint32_t* out){std::fill_n(out,static_cast<unsigned>(consumable_type::count),0);return 0;}
std::int32_t sdk_altar_locks(altar_lock_info*,std::uint32_t,std::uint32_t* count){*count=0;return 0;}
std::int32_t sdk_bc_round_number(std::uint32_t* out){
    if(++round_queries==cross_on_query)++now;
    *out=now;return 0;
}
std::int64_t sdk_fuel_remaining(){return fuel;}
std::int32_t sdk_submit_gems(std::int32_t,std::int32_t){++submissions;state|=4;return 0;}
std::int32_t sdk_bc_submitted_gems(std::uint32_t,std::uint32_t* out){*out=123;return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* out){*out=0;return 0;}
std::int32_t sdk_Bitboard_DrawChebyshev(std::uint64_t* out,std::int32_t x,std::int32_t y,float r){
    for(int yy=0;yy<8;++yy)for(int xx=0;xx<8;++xx)
        if(std::max(std::abs(xx-x),std::abs(yy-y))<=r)*out|=std::uint64_t{1}<<(yy*8+xx);
    return 0;
}
std::int32_t sdk_use_consumable(std::uint32_t,std::int32_t,std::int32_t,std::int32_t*){std::abort();}
std::int32_t sdk_attack(std::uint32_t,std::uint32_t){std::abort();}
}
}
int main() {
    World w;Memory m;TurnBudget b{113};
    for(auto status:{RouteStatus::no_route_now,RouteStatus::invalid_goals})
        for(bool moves:{false,true})for(int blocked:{1,3}) {
            reset(w,m,b);route=status;escape_moves=moves;blocked_after=blocked;expect_cleared=blocked==3;
            failed(w,m,b,1);
            check(snapshot.pos==vec2{moves?2:1,1},"moving and immobile retreat results");
            if(blocked==1)check(m.altar==0&&w.altar_retry[0]==0,"first failure retains altar");
        }
    reset(w,m,b);snapshot.camp_hit=false;snapshot.incoming=0;failed(w,m,b,1); // refreshed hazard
    reset(w,m,b);refreshed_camp=false;failed(w,m,b,0);
    for(float incoming:{0.f,-1.f}){reset(w,m,b);refreshed_incoming=incoming;failed(w,m,b,0);}
    for(unsigned remaining:{0u,Config::reserve,Config::reserve+1}) {
        reset(w,m,b);fuel=remaining;failed(w,m,b,remaining>Config::reserve?1:0);
    }
    reset(w,m,b);refreshed_camp=false;blocked_after=3;failed(w,m,b,0);
    check(m.altar==-1&&m.blocked==0&&w.altar_retry[0]==116,"nonhazard third failure cooldown");
    reset(w,m,b);cross_in_move=true;failed(w,m,b,0);
    reset(w,m,b);cross_in_observe=true;failed(w,m,b,0);
    reset(w,m,b);cross_on_query=2;failed(w,m,b,0); // second caller round guard
    reset(w,m,b);cross_in_move=true;blocked_after=3;failed(w,m,b,0);
    check(m.altar==-1&&m.blocked==0&&w.altar_retry[0]==116,"old cooldown order survives rollover");
    for(auto status:{RouteStatus::deferred,RouteStatus::wait,RouteStatus::at_goal,RouteStatus::moved}) {
        reset(w,m,b);route=status;failed(w,m,b,0);
    }
    reset(w,m,b);m.altar=-1;chosen=-1;
    check(!bank(w,b,m)&&retreats==0&&approaches==0&&selections==1,"no altar candidate");
    reset(w,m,b);snapshot.bag=0;m.queue_started=110;
    check(!bank(w,b,m)&&retreats==0&&approaches==0&&m.altar==-1&&m.queue_started==-1,"empty bag");
    for(bool walking:{false,true}) {
        reset(w,m,b);route=RouteStatus::moved;arrive=walking;
        if(!walking)snapshot.pos={5,5};
        check(bank(w,b,m)&&retreats==0&&submissions==1,"ordinary approach starts channel");
        check(m.bank_bag==7&&m.bank_score==123,"confirmed channel accounting");
    }
    reset(w,m,b);snapshot.pos={5,5};state|=4;
    check(bank(w,b,m)&&retreats==0&&submissions==0,"active submission channel");
    std::cout<<"PASS production bank escape contracts\n";
}
