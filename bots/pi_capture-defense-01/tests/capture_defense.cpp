// Real bot.cpp, combat.cpp, state_machine.cpp and SDK; deterministic 8x8 host.
// Compile with -fno-access-control to exercise private production entry points.
#include "bot.h"
#include "route_plan.h"
#include <cstdlib>
#include <bit>
#include <iostream>
#include <string>
using namespace lp;
namespace {
Snapshot snap;
int round_now=24, attacks=0, casts=0, moves=0, advances=0, fights=0, retreats=0;
int task_arg=0; bool travel_arg=false;
std::int64_t fuel=100000;
std::uint32_t actor_state=0, spell_kind=0;
int cooldown=0; bool exclusive=false, roll_round=false;
std::string events;
void check(bool ok,const char* label) {if(!ok){std::cerr<<"FAIL: "<<label<<'\n';std::exit(1);}}
std::uint64_t tile(int x,int y) {return (x>=0&&x<8&&y>=0&&y<8)?1ull<<(y*8+x):0;}
}
namespace cambc::detail { extern "C" {
std::int32_t sdk_get_settings(game_settings* p) {*p={};return 0;}
std::int32_t sdk_bc_metadata(metadata* p) {*p={8,8,1,1,1,8,128};return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* p){*p=0;return 0;}
std::int32_t sdk_read_draft_memory(std::int32_t,void*,std::uint32_t){return 0;}
std::int32_t sdk_Bitboard_NumSetBits(const std::uint64_t* p,std::uint32_t* n){*n=std::popcount(*p);return 0;}
std::int32_t sdk_Bitboard_ImportRawBuffer(std::uint64_t* p,const std::uint8_t* v,std::size_t n){std::memcpy(p,v,n);return 0;}
std::int32_t sdk_my_champion(){return 0;}
std::int32_t sdk_my_team(){return 0;}
std::int32_t sdk_shared_memory_size(std::uint32_t* p){*p=8;return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* p){*p={};return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* p){*p={};return 0;}
std::int32_t sdk_bc_map_symmetry(std::int32_t* p){*p=0;return 0;}
std::int32_t sdk_bc_map_mask(std::int32_t,std::uint64_t* p){*p=0;return 0;}
std::int32_t sdk_spawn_region(std::int32_t,aabb* p){*p={};return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t owner,std::uint32_t slot,ability_props* p){
    *p={};if(owner==0&&slot==0){p->kind=spell_kind;p->targets=ability_target_enemies;
    p->attributes=exclusive?ability_attribute_exclusive_with_movement:0;p->payload.damage={3,1};}return 0;
}
std::int32_t sdk_champion(std::uint32_t h,champion_info* p){
    *p={int(h),0,h==0?2:3,2,1000,1000,50,50,1,1,int(h==0?actor_state:0)};return 0;
}
std::int32_t sdk_champion_identity(std::uint32_t h,champion_identity* p){*p={int(h),0};return 0;}
std::int32_t sdk_champion_is_alive(std::uint32_t,std::int32_t* p){*p=1;return 0;}
std::int32_t sdk_champion_gold(std::uint32_t,std::uint32_t* p){*p=0;return 0;}
std::int32_t sdk_champion_channel_time(std::uint32_t,std::int32_t* p){*p=3;return 0;}
std::int32_t sdk_champion_cooldown(std::uint32_t,std::uint32_t,std::int32_t* p){*p=cooldown;return 0;}
std::int32_t sdk_champion_ability_damage(std::uint32_t,std::uint32_t,float* p){*p=50;return 0;}
std::int32_t sdk_champion_ability_damage_against(std::uint32_t,std::uint32_t,std::uint32_t,float* p){*p=50;return 0;}
std::int32_t sdk_champion_ability_heal_against(std::uint32_t,std::uint32_t,std::uint32_t,float* p){*p=50;return 0;}
std::int32_t sdk_bc_round_number(std::uint32_t* p){*p=round_now;return 0;}
std::int64_t sdk_fuel_remaining(){if(roll_round)++round_now;return fuel;}
std::int32_t sdk_bc_submitted_gems(std::uint32_t,std::uint32_t* p){*p=0;return 0;}
std::int32_t sdk_bc_get_last_error(char*,std::uint32_t){return 0;}
std::int32_t sdk_attack(std::uint32_t kind,std::uint32_t h){
    ::check(kind==std::uint32_t(entity_kind::champion)&&h==1,"only enemy attacked");
    ++attacks;events+='A';actor_state&=~champion_state::can_attack.bits();return 0;
}
std::int32_t sdk_cast(std::uint32_t,std::uint32_t,std::uint32_t,std::int32_t,std::int32_t,std::int32_t* p){
    ::check(spell_kind!=std::uint32_t(ability_kind::dash),"no dash selected");++casts;events+='C';*p=1;return 0;
}
std::int32_t sdk_set_priority(std::int32_t){return 0;}
std::int32_t sdk_recall(){events+='R';return 0;}
std::int32_t sdk_cancel_channel(){events+='X';return 0;}
std::int32_t sdk_read_shared_memory(std::int32_t,void* p,std::uint32_t n){std::memset(p,0,n);return 0;}
std::int32_t sdk_write_shared_memory(std::int32_t,const void*,std::uint32_t){return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* p){*p=0;return 0;}
std::int32_t sdk_Bitboard_Test(const std::uint64_t* p,std::int32_t x,std::int32_t y,std::int32_t* v){*v=bool(*p&tile(x,y));return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t* p,std::int32_t x,std::int32_t y,std::int32_t v){if(v)*p|=tile(x,y);else *p&=~tile(x,y);return 0;}
std::int32_t sdk_Bitboard_IsZero(const std::uint64_t* p,std::int32_t* v){*v=*p==0;return 0;}
std::int32_t sdk_Bitboard_Not(const std::uint64_t* p,std::uint64_t* v){*v=~*p;return 0;}
std::int32_t sdk_Bitboard_Union(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* p){*p=*a|*b;return 0;}
std::int32_t sdk_Bitboard_Intersect(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* p){*p=*a&*b;return 0;}
std::int32_t sdk_Bitboard_DrawChebyshev(std::uint64_t* p,std::int32_t x,std::int32_t y,float r){for(int j=0;j<8;++j)for(int i=0;i<8;++i)if(std::max(abs(i-x),abs(j-y))<=r)*p|=tile(i,j);return 0;}
std::int32_t sdk_Bitboard_GetSetBits(const std::uint64_t* p,void* out,std::size_t cap,std::uint32_t* n){
    *n=0;for(int y=0;y<8;++y)for(int x=0;x<8;++x)if(*p&tile(x,y)){if(*n<cap)static_cast<position*>(out)[*n]={x,y};++*n;}return 0;
}
// No live camps in this fixture; fail if production tries to inspect one.
std::int32_t sdk_camp(std::uint32_t,camp_state*){std::abort();}
std::int32_t sdk_camp_state(std::uint32_t,std::uint32_t*){std::abort();}
std::int32_t sdk_camp_design(std::int32_t,camp_design*){std::abort();}
} }
namespace lp {
const Snapshot& observe(){return snap;}
void invalidate_observations(){}
float incoming_at(vec2,const std::vector<champion>&){return 0;}
void World::init(){}
void World::refresh(const Snapshot&,Memory&){}
int World::chunk(vec2)const{return 0;}
void advance_loop(World&,int){++advances;events+='L';}
bitboard camp_goals(const Objective&,const Snapshot&){events+='G';return {};}
RouteStatus move_to(bitboard,bool,TurnBudget&,Memory&,bool){++moves;events+='M';return RouteStatus::wait;}
bool retreat(TurnBudget&,Memory&){++retreats;events+='E';return false;}
void shop(Memory&){}
bool bank(World&,TurnBudget&,Memory&){return false;}
int choose_altar(World&,const Snapshot&,TurnBudget&,int){return -1;}
int choose_camp(World&,const Snapshot&,TurnBudget&,bool,bool){return -1;}
bool explore(World&,TurnBudget&,Memory&){return false;}
}
// Link wrappers count calls without replacing the production fight implementation.
extern "C" bool __real__ZN2lp5fightERNS_5WorldEib(World&,int,bool);
extern "C" bool __wrap__ZN2lp5fightERNS_5WorldEib(World& w,int t,bool travel){
    ++fights;task_arg=t;travel_arg=travel;events+='F';return __real__ZN2lp5fightERNS_5WorldEib(w,t,travel);
}
extern "C" void __wrap__ZN2lp13optional_wardERKNS_5WorldEi(const World&,int){}

static Bot fixture(bool enemy=true){
    round_now=24;fuel=100000;roll_round=false;cooldown=0;exclusive=false;spell_kind=0;
    actor_state=(champion_state::can_attack|champion_state::can_cast|champion_state::can_move).bits();
    cambc::detail::cached_self=cambc::detail::handle_access::make_champion(handle_champion_t(0));
    snap={};snap.round=24;snap.pos={2,2};snap.alive=true;snap.hp=snap.max_hp=1000;snap.friends=1;
    if(enemy){snap.foes.push_back(cambc::detail::handle_access::make_champion(handle_champion_t(1)));snap.enemies=1;}
    Bot b;b.world.camps.push_back({cambc::detail::handle_access::make_camp_group(handle_camp_group_t(0),0,0,0,{})});auto& o=b.world.camps[0];o.lifecycle=2;o.seen=24;o.tiles.set({2,2});
    b.memory.task=0;b.memory.task_started=b.memory.progressed=24;
    attacks=casts=moves=advances=fights=retreats=0;events.clear();return b;
}
static void run(Bot& b){TurnBudget budget{24};b.camp_action(budget);}
static void stationary(const Bot& b){check(moves==0&&advances==0&&b.memory.task==0,"occupation neither moves nor abandons");check(self().position()==snap.pos,"host position retained");}
int main(){
    auto b=fixture();run(b);check(fights==1&&task_arg==-1&&travel_arg&&attacks==1,"fresh occupation fights once, enemy-only");stationary(b);
    b=fixture(false);run(b);check(fights==0&&attacks==0&&casts==0,"quiet occupation immediate return");stationary(b);
    for(auto state:{std::uint32_t(0),champion_state::recalling.bits(),champion_state::submitting_gems.bits(),champion_state::teleporting.bits()}){
        b=fixture();actor_state=state?actor_state|state:0;run(b);check(fights==1&&attacks==0&&casts==0,"real fight guards unavailable/channeling actor");stationary(b);
    }
    for(auto kind:{ability_kind::damage,ability_kind::aoe_damage,ability_kind::cc,ability_kind::dash}){
        b=fixture();spell_kind=std::uint32_t(kind);
        cambc::detail::cached_self=cambc::detail::handle_access::make_champion(handle_champion_t(0));
        run(b);check(attacks==1&&casts==(kind==ability_kind::dash?0:1),"stationary offensive kinds; dash excluded");stationary(b);
    }
    for(int mode=0;mode<3;++mode){
        b=fixture();spell_kind=std::uint32_t(ability_kind::cc);exclusive=true;
        if(mode==0)cooldown=1;
        if(mode==1)actor_state&=~champion_state::can_move.bits();
        cambc::detail::cached_self=cambc::detail::handle_access::make_champion(handle_champion_t(0));
        run(b);check(attacks==1&&casts==(mode==2?1:0),"real readiness and movement-exclusion guards");stationary(b);
    }
    b=fixture();b.memory.task=-1;run(b);check(fights==0&&moves==0,"no task remains inert");
    b=fixture();fuel=Config::reserve;run(b);check(fights==1&&attacks==0&&casts==0,"fuel reserve guard");
    b=fixture();roll_round=true;run(b);check(attacks==0&&casts==0,"round rollover guard");
    for(int mode=0;mode<4;++mode){
        b=fixture();if(mode==3)b.world.camps[0].lifecycle=0;
        if(mode==0)b.world.camps[0].lifecycle=1;
        if(mode==1)b.world.camps[0].seen=23;
        if(mode==2)b.world.camps[0].tiles.clear();
        run(b);check(moves==1&&fights==1&&task_arg==0&&!travel_arg&&advances==0,"living/stale/outside retain navigation and task combat");
    }
    b=fixture();b.world.camps[0].tiles.clear();b.world.camps[0].tiles.set({3,2});snap.allies=snap.foes;
    run(b);check(fights==1&&task_arg==0&&!travel_arg&&moves==0,"other occupant retains guard path");
    b=fixture();b.play_turn();check(fights==1&&attacks==1,"real dispatcher reaches occupied camp");stationary(b);
    b=fixture();snap.enemies=2;b.play_turn();check(b.memory.state==State::escape&&retreats==1&&advances==1,"escape wins over occupied camp");
    check(events.find('E')<events.find('F')&&fights==1,"escape combat only after retreat");
    for(auto state:{champion_state::submitting_gems,champion_state::teleporting}){
        b=fixture();actor_state|=state.bits();snap.enemies=2;b.play_turn();
        check(b.memory.state==State::bank&&fights==0&&moves==0&&advances==0,"channel dispatch wins even under danger");
    }
    b=fixture(false);actor_state|=champion_state::recalling.bits();b.play_turn();
    check(b.memory.state==State::recall&&fights==0&&moves==0,"safe recall dispatch preserved");
    std::cout<<"PASS production occupation, combat guards and dispatcher scenarios\n";
}
