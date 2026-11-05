// Actual economy/navigation/observation code and SDK wrappers; only host imports,
// altar selection and combat are substituted. Geometry is an 8x8 walking grid.
#include "../src/economy.cpp"
#include "../src/navigation.cpp"
#include "../src/observations.cpp"
#include <bit>
#include <cassert>
#include <cstdio>
#include <queue>
#include <string>
using namespace cambc;
namespace host {
int round=100, moves=0, fields=0, camp_reads=0, submits=0;
std::int64_t fuel=100000;
std::uint64_t walls=0, field_walls=0;
bool hidden=false, unreachable=false;
std::string trip;
int trip_after=0;
void tick(const char* event) {if(trip==event&&--trip_after==0){++round;trip.clear();} if(trip==std::string(event)+"_reserve"){fuel=5000;trip.clear();}}
struct Camp {vec2 pos;float strength;int range;unsigned state;};
std::vector<Camp> camps;
std::vector<detail::champion_info> champs;
std::uint8_t restrictions=0;
std::uint64_t bit(int x,int y){assert(x>=0&&y>=0&&x<8&&y<8);return std::uint64_t{1}<<(y*8+x);}
std::uint64_t bit(vec2 p){return bit(p.x,p.y);}
void require(bool ok,const char* msg){if(!ok){std::fprintf(stderr,"FAIL: %s\n",msg);std::exit(1);}}
}
namespace cambc::detail {
extern "C" {
std::int32_t sdk_get_settings(game_settings* o){*o={};return 0;}
std::int32_t sdk_bc_metadata(metadata* o){*o={8,8,1,1,1,8,128};return 0;}
std::int32_t sdk_bc_map_symmetry(std::int32_t* o){*o=0;return 0;}
std::int32_t sdk_draft_num_rounds(std::uint8_t* o){*o=3;return 0;}
std::int32_t sdk_bc_get_last_error(char*,std::uint32_t){return 0;}
std::int32_t sdk_my_team(){return 0;}
std::int32_t sdk_my_champion(){return 0;}
std::int32_t sdk_shared_memory_size(std::uint32_t* o){*o=0;return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* o){*o=0;return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* o){*o={};return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* o){*o={};return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t,std::uint32_t,ability_props* o){*o={};return 0;}
std::int32_t sdk_bc_round_number(std::uint32_t* o){*o=host::round;return 0;}
std::int64_t sdk_fuel_remaining(){return host::fuel;}
std::int32_t sdk_champion(std::uint32_t h,champion_info* o){*o=host::champs.at(h);host::tick("champion");return 0;}
std::int32_t sdk_champion_identity(std::uint32_t h,champion_identity* o){auto c=host::champs.at(h);*o={c.team,c.type};return 0;}
std::int32_t sdk_champion_is_alive(std::uint32_t h,std::int32_t* o){*o=(host::champs.at(h).state&1)!=0;return 0;}
std::int32_t sdk_champion_restrictions(std::uint32_t,std::uint8_t* o){*o=host::restrictions;host::tick("restrictions");return 0;}
std::int32_t sdk_champion_gems(std::uint32_t,std::uint32_t* o){*o=7;return 0;}
std::int32_t sdk_champion_consumables(std::uint32_t,std::uint32_t* o){o[0]=o[1]=0;return 0;}
std::int32_t sdk_bc_map_mask(std::int32_t kind,std::uint64_t* o){*o=kind==0?host::walls:0;return 0;}
std::int32_t sdk_spawn_region(std::int32_t team,aabb* o){*o=team==0?aabb{0,0,1,1}:aabb{7,7,8,8};return 0;}
std::int32_t sdk_vision(std::uint64_t* o){*o=~std::uint64_t{};return 0;}
std::int32_t sdk_ally_occupancy(std::uint64_t* o){*o=host::bit({host::champs[0].x,host::champs[0].y});return 0;}
std::int32_t sdk_enemy_occupancy(std::uint64_t* o){*o=0;for(unsigned i=1;i<host::champs.size();++i)*o|=host::bit({host::champs[i].x,host::champs[i].y});return 0;}
std::int32_t sdk_teleport_occupancy(std::uint64_t* o){*o=host::walls;return 0;}
std::int32_t sdk_camp_occupancy(std::uint64_t* o){*o=0;for(auto c:host::camps)*o|=host::bit(c.pos);return 0;}
std::int32_t sdk_champion_at(std::int32_t x,std::int32_t y,std::uint32_t* o){for(unsigned i=0;i<host::champs.size();++i)if(host::champs[i].x==x&&host::champs[i].y==y){*o=i;return 0;}std::abort();}
std::int32_t sdk_camp_at(std::int32_t x,std::int32_t y,std::uint32_t* o){for(unsigned i=0;i<host::camps.size();++i)if(host::camps[i].pos==vec2{x,y}){*o=i;return 0;}std::abort();}
std::int32_t sdk_map_camp_info(std::uint32_t h,camp_info* o){auto c=host::camps.at(h);*o={c.pos.x,c.pos.y,int(h)};return 0;}
std::int32_t sdk_map_camp_group_of(std::uint32_t,std::uint32_t* o){*o=0;return 0;}
std::int32_t sdk_camp_state(std::uint32_t h,std::uint32_t* o){*o=host::camps.at(h).state;host::tick("camp_state");return 0;}
std::int32_t sdk_camp(std::uint32_t h,camp_state* o){auto c=host::camps.at(h);*o={c.pos.x,c.pos.y,100,100,c.strength,0,{0,0}};++host::camp_reads;host::tick("camp");return 0;}
std::int32_t sdk_camp_design(std::int32_t h,camp_design* o){*o={};o->base_stats.base_attack_range=host::camps.at(h).range;return 0;}
std::int32_t sdk_altar_locks(altar_lock_info*,std::uint32_t,std::uint32_t* o){*o=0;return 0;}
std::int32_t sdk_submit_gems(std::int32_t,std::int32_t){++host::submits;return 0;}
std::int32_t sdk_move_to(std::int32_t x,std::int32_t y,std::int32_t* o){++host::moves;*o=!host::hidden;if(host::hidden)return int(error_code::invalid_action_move_bad_destination);host::champs[0].x=x;host::champs[0].y=y;host::champs[0].state&=~8;return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* o){*o=0;return 0;}
std::int32_t sdk_Bitboard_ImportRawBuffer(std::uint64_t* o,const std::uint8_t* p,std::size_t n){assert(n==8);std::memcpy(o,p,n);return 0;}
std::int32_t sdk_Bitboard_Test(const std::uint64_t* b,std::int32_t x,std::int32_t y,std::int32_t* o){*o=(*b&host::bit(x,y))!=0;return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t* b,std::int32_t x,std::int32_t y,std::int32_t value){if(value)*b|=host::bit(x,y);else *b&=~host::bit(x,y);return 0;}
std::int32_t sdk_Bitboard_IsZero(const std::uint64_t* b,std::int32_t* o){*o=*b==0;return 0;}
std::int32_t sdk_Bitboard_NumSetBits(const std::uint64_t* b,std::uint32_t* o){*o=std::popcount(*b);return 0;}
std::int32_t sdk_Bitboard_GetSetBits(const std::uint64_t* b,void* o,std::size_t cap,std::uint32_t* count){*count=0;for(int i=0;i<64;++i)if((*b>>i)&1){assert(*count<cap);static_cast<vec2*>(o)[(*count)++]={i%8,i/8};}return 0;}
std::int32_t sdk_Bitboard_Union(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* o){*o=*a|*b;return 0;}
std::int32_t sdk_Bitboard_Intersect(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* o){*o=*a&*b;return 0;}
std::int32_t sdk_Bitboard_Not(const std::uint64_t* a,std::uint64_t* o){*o=~*a;return 0;}
std::int32_t sdk_Bitboard_DrawChebyshev(std::uint64_t* b,std::int32_t x,std::int32_t y,float r){for(int yy=0;yy<8;++yy)for(int xx=0;xx<8;++xx)if(std::max(abs(xx-x),abs(yy-y))<=r)*b|=host::bit(xx,yy);return 0;}
std::int32_t sdk_Bitboard_ReachableMask(const std::uint64_t* b,std::int32_t x,std::int32_t y,std::uint64_t* o,std::uint16_t n){assert(n==1);*o=host::bit(x,y);for(int yy=std::max(0,y-1);yy<=std::min(7,y+1);++yy)for(int xx=std::max(0,x-1);xx<=std::min(7,x+1);++xx)if(!(*b&host::bit(xx,yy)))*o|=host::bit(xx,yy);host::tick("neighbors");return 0;}
std::int32_t sdk_DistanceField_Get(const std::uint16_t* f,std::int32_t x,std::int32_t y,std::uint16_t* o){*o=f[y*8+x];return 0;}
std::int32_t sdk_DistanceField_ComputeToWithExpansionCount(const std::uint64_t* b,const std::uint64_t* roots,const std::uint64_t*,std::uint64_t* visited,std::uint16_t* f,std::uint16_t,std::uint16_t* count){
    host::field_walls=*b;++host::fields;std::fill_n(f,64,65535);*visited=0;*count=0;std::queue<int> q;
    if(!host::unreachable)for(int i=0;i<64;++i)if((*roots>>i)&1){f[i]=0;q.push(i);*visited|=std::uint64_t{1}<<i;}
    while(!q.empty()){int i=q.front();q.pop();for(int y=std::max(0,i/8-1);y<=std::min(7,i/8+1);++y)for(int x=std::max(0,i%8-1);x<=std::min(7,i%8+1);++x){int j=y*8+x;if(!(*b&host::bit(x,y))&&f[j]==65535){f[j]=f[i]+1;*visited|=host::bit(x,y);q.push(j);}}}
    host::tick("field");return 0;
}
} // extern C
} // namespace cambc::detail
namespace lp {
int choose_altar(World&,const Snapshot&,TurnBudget&,int previous){return previous;}
bool fight(World&,int,bool){return false;}
}
#include "unused-host-imports.h"

using namespace lp;
void reset(){
    host::round=100;host::fuel=100000;host::moves=host::fields=host::camp_reads=host::submits=0;
    host::hidden=host::unreachable=false;host::restrictions=0;host::trip.clear();host::walls=0;
    host::champs={{0,0,0,3,1300,1300,60,0,1,1,9}};
    host::camps={{{3,2},60,3,1}};
    invalidate_observations();
}
bitboard goal(){return around({0,7},1);}
World world(){World w;w.altars={{0,7}};w.altar_retry={0};w.slot=0;return w;}
int main(){
    using host::require;
    reset();Memory m;m.blocked=2;TurnBudget b{100};auto before=m;
    require(bank_egress(goal(),b,m)==RouteStatus::moved,"equal incoming camp egress");
    require(self().position()==vec2{0,4},"goalward south step, away from north spawn, y/x tie");
    require(m.blocked==0&&m.last_distance==2&&b.fields==1&&host::moves==1,"one field/move and movement memory");
    before.blocked=0;before.last_distance=2;require(std::memcmp(&before,&m,sizeof m)==0,"no other memory changed");
    reset();m=Memory{};m.altar=0;b={100};auto w=world();
    require(!bank(w,b,m)&&host::moves==1&&host::fields==2,"actual failed safe bank invokes egress, returns false");
    require(host::submits==0&&self().position()==vec2{0,4},"no bank channel or spawn route");
    reset();m=Memory{};m.altar=0;m.blocked=2;b={100};w=world();
    require(!bank(w,b,m)&&m.altar==-1&&w.altar_retry[0]==103&&host::moves==1,"third failure retains original altar goals after reset");
    reset();host::camps[0].range=7;m=Memory{};m.altar=0;m.blocked=2;b={100};w=world();
    require(!bank(w,b,m)&&m.altar==-1&&w.altar_retry[0]==103&&host::fields==1&&host::moves==1,"invalid-goals third failure also invokes original altar egress");
    reset();host::hidden=true;m=Memory{};m.blocked=2;b={100};auto revision=observation_version();
    require(bank_egress(goal(),b,m)==RouteStatus::wait&&host::moves==1&&m.blocked==2&&m.last_distance==65535&&observation_version()>revision,"hidden blocker: one rejection, invalidated, no memory success");
    reset();host::camps.push_back({{0,7},100,3,1});m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::no_route_now&&host::moves==0&&m.blocked==0,"higher incoming rejects all improving neighbors without failure increment");
    reset();host::champs.push_back({1,0,3,5,1000,1000,0,0,1,1,1});m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::moved&&self().position()==vec2{0,4},"enemy risk retained");
    require(host::field_walls&host::bit(1,4),"enemy risk is blocked in actual egress field");
    reset();host::walls=host::bit(0,4);m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::moved&&self().position()==vec2{1,4},"physical blocker excluded");
    reset();host::walls=~host::bit(0,3);m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::invalid_goals&&b.fields==0,"blocked goals masked");
    reset();m=Memory{};b={100};require(bank_egress(around({0,3},0),b,m)==RouteStatus::at_goal&&b.fields==0,"already at goal");
    reset();host::unreachable=true;m=Memory{};b={100};require(bank_egress(goal(),b,m)==RouteStatus::no_route_now&&m.blocked==0,"unreachable origin");
    for(int test=0;test<12;++test){reset();m=Memory{};m.blocked=2;b={100};
        if(test==0)b.fields=3;
        if(test==1)host::fuel=5000;
        if(test==2)host::fuel=29999;
        if(test==3){observe();host::trip="camp";host::trip_after=1;}
        if(test==4){host::trip="field";host::trip_after=1;}
        if(test==5){host::trip="neighbors";host::trip_after=1;}
        if(test==6)host::trip="field_reserve";
        if(test==7)b.round=99;
        if(test==8){observe();host::trip="camp_reserve";}
        if(test==9){observe();host::trip="restrictions";host::trip_after=2;}
        if(test==10){observe();host::trip="champion";host::trip_after=1;}
        if(test==11)host::trip="neighbors_reserve";
        require(bank_egress(goal(),b,m)==RouteStatus::deferred&&host::moves==0&&m.blocked==2&&m.last_distance==65535,"quota/fuel/rollover refuses mutation");
    }
    for(int test=0;test<4;++test){reset();m=Memory{};b={100};
        if(test==0)host::champs[0].state=0;
        if(test==1)host::champs[0].state=1;
        if(test==2)host::champs[0].state=13;
        if(test==3)host::restrictions=buff_restrictions::move.bits();
        require(bank_egress(goal(),b,m)==RouteStatus::wait&&b.fields==0&&host::moves==0,"life/channel/can-move/restriction guards");
    }
    // No camp danger means ordinary movement succeeds without an extra field.
    reset();host::camps.clear();m=Memory{};m.altar=0;b={100};w=world();
    require(!bank(w,b,m)&&host::fields==1&&host::moves==1,"safe success no fallback");
    reset();m=Memory{};b={100};w=world();require(!bank(w,b,m)&&host::fields==0&&host::moves==0,"no altar no fallback");
    reset();m=Memory{};m.altar=0;b={100,3};w=world();require(!bank(w,b,m)&&host::fields==0&&host::moves==0,"deferred approach no fallback");
    reset();host::champs[0].state=1;m=Memory{};m.altar=0;b={100};w=world();require(!bank(w,b,m)&&host::fields==0&&host::moves==0,"wait approach no fallback");
    // Sleeping/dead/zero-strength camps must not raise candidate incoming.
    reset();host::camps.push_back({{0,7},1000,3,2});host::camps.push_back({{1,7},1000,3,0});host::camps.push_back({{2,7},0,3,1});m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::moved&&self().position()==vec2{0,4},"camp state/strength filtering");
    // A champion contributes even if its strength is negative (existing semantics).
    reset();host::champs.push_back({1,0,7,0,100,100,-7,0,1,7,1});
    auto foes=std::vector<champion>{detail::handle_access::make_champion(static_cast<handle_champion_t>(1))};
    require(incoming_at({0,3},foes)==53&&incoming_at({0,4},foes)==53,"existing enemy plus camp aggregation reference");
    // Lower incoming wins before coordinate ties; use a centered geometry.
    reset();host::champs[0].x=3;host::camps.push_back({{0,4},20,2,1});m=Memory{};b={100};
    require(bank_egress(around({3,7},1),b,m)==RouteStatus::moved&&self().position()==vec2{3,4},"incoming breaks equal-distance tie before x");
    reset();host::champs[0].x=3;host::camps={{{0,0},60,7,1}};m=Memory{};b={100};
    require(bank_egress(around({7,3},1),b,m)==RouteStatus::moved&&self().position()==vec2{4,2},"y tie before x for eastbound goal");
    // Clear synthetic risk only in these aggregation unit cases so enemy damage
    // can be tested independently of the real risk-exclusion integration above.
    reset();host::champs.push_back({1,0,0,1,100,100,40,0,1,2,1});
    host::camps.push_back({{0,7},30,3,1});const_cast<Snapshot&>(observe()).risk.clear();m=Memory{};b={100};
    require(incoming_at({0,3},observe().foes)==100&&incoming_at({0,4},observe().foes)==90,"champion live range/strength plus camp reference");
    require(bank_egress(goal(),b,m)==RouteStatus::moved,"helper includes champion damage at current tile");
    // Floating point cancellation detects enemy-then-camp accumulation order.
    reset();host::camps={{{3,2},2,3,1},{{0,7},0.5f,3,1}};
    host::champs.push_back({1,0,6,0,100,100,16777216,0,1,7,1});
    host::champs.push_back({1,0,7,0,100,100,-16777216,0,1,7,1});
    const_cast<Snapshot&>(observe()).risk.clear();m=Memory{};b={100};
    require(incoming_at({0,3},observe().foes)==2&&incoming_at({0,4},observe().foes)==2.5f,"enemy-then-camp float reference");
    require(bank_egress(goal(),b,m)==RouteStatus::no_route_now&&host::moves==0,"helper preserves enemy-then-camp float accumulation");
    // Current damage must be recomputed from captured sources, not s.incoming.
    reset();const_cast<Snapshot&>(observe()).incoming=0;host::camp_reads=0;m=Memory{};b={100};
    require(bank_egress(goal(),b,m)==RouteStatus::moved&&host::camp_reads==2,"local threat position/strength copied once; stale incoming unused");
    // Camp-hit and positive incoming are independent bank integration gates.
    for(int test=0;test<2;++test){reset();auto& snapshot=const_cast<Snapshot&>(observe());
        if(test==0)snapshot.camp_hit=false;else snapshot.incoming=0;
        m=Memory{};m.altar=0;b={100};w=world();
        require(!bank(w,b,m)&&host::fields==1&&host::moves==0,"failed bank requires current camp hit and positive incoming");
    }
    reset();const_cast<Snapshot&>(observe()).bag=0;m=Memory{};m.altar=0;b={100};w=world();
    require(!bank(w,b,m)&&host::fields==0&&host::moves==0,"empty bag no fallback");
    reset();host::champs[0].state=13;m=Memory{};m.altar=0;b={100};w=world();
    require(!bank(w,b,m)&&host::fields==0&&host::moves==0,"channel approach no fallback");
    // A second call after leaving exposure must use only the ordinary safe path.
    reset();host::camps[0].range=2;host::champs[0].x=1;m=Memory{};m.altar=0;b={100};w=world();
    require(!bank(w,b,m)&&host::moves==1,"egress leaves current camp region");
    ++host::round;host::champs[0].state=9;b={host::round};host::fields=0;
    require(!observe().camp_hit,"egress trigger disappears outside camp range");
    bank(w,b,m);require(host::fields==1,"next turn safe bank gets first refusal");
    std::puts("PASS production bank egress and integration scenarios");
}
