// Production SDK, observations, combat and Bot dispatch; only the host and
// unrelated economy/objective/navigation dependencies are substituted.
#include "bot.h"
#include <bit>
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
using namespace cambc;
namespace host {
constexpr int words=16;
struct Threat {vec2 pos;float strength=60;int range=4;unsigned state=1;};
std::vector<Threat> camps;
vec2 pos{27,27},foe{10,10};
bool enemy=false,alive=true,mobile=true,restricted=false,casting=false,shield=false,spend_move=false,kill=false;
bool hidden=false,throw_move=false,vanish_risk=false,seed_task=false,seeded=false;
int channel=0,round=250,moves=0,attacks=0,casts=0,scans=0;
float hp=940;
std::uint64_t occupied[words]{};
std::int64_t fuel=40000;
std::string hook;int hook_n=0,hook_seen=0;bool rollover=false;
std::vector<std::string> actions;
lp::Memory* memory=nullptr;
int work=0;
void tick(const char* name) {if(hook==name&&++hook_seen==hook_n){if(rollover)++round;else fuel=lp::Config::reserve;}}
bool inside(int x,int y){return x>=0&&x<32&&y>=0&&y<32;}
void set(std::uint64_t* b,int x,int y,bool v=true){if(!inside(x,y))return;auto k=y*32+x;if(v)b[k/64]|=1ULL<<(k%64);else b[k/64]&=~(1ULL<<(k%64));}
bool get(const std::uint64_t* b,int x,int y){if(!inside(x,y))return false;auto k=y*32+x;return b[k/64]>>(k%64)&1;}
void zero(std::uint64_t* b){std::memset(b,0,words*8);}
void reset(){camps={{{26,23}}};pos={27,27};foe={10,10};enemy=false;alive=mobile=true;restricted=casting=shield=spend_move=kill=hidden=throw_move=vanish_risk=seed_task=seeded=false;channel=0;round=250;moves=attacks=casts=scans=0;hp=940;fuel=40000;zero(occupied);set(occupied,28,27);set(occupied,29,27);hook.clear();hook_seen=hook_n=0;rollover=false;actions.clear();memory=nullptr;work=0;lp::invalidate_observations();}
}
namespace cambc::detail {extern "C" {
std::int32_t sdk_get_settings(game_settings* out){*out={};return 0;}
std::int32_t sdk_bc_metadata(metadata* out){*out={32,32,4,4,4,128,2048};return 0;}
std::int32_t sdk_my_champion(){return 0;}
std::int32_t sdk_my_team(){return 1;}
std::int32_t sdk_spawn_region(std::int32_t t,aabb* out){*out=t==1?aabb{27,27,30,30}:aabb{0,0,3,3};return 0;}
std::int32_t sdk_bc_map_mask(std::int32_t,std::uint64_t* out){host::zero(out);return 0;}
std::int32_t sdk_bc_map_symmetry(std::int32_t* out){*out=0;return 0;}
std::int32_t sdk_read_shared_memory(std::int32_t,void* out,std::uint32_t size){std::memset(out,0,size);return 0;}
std::int32_t sdk_shared_memory_size(std::uint32_t* out){*out=1024;return 0;}
std::int32_t sdk_read_draft_memory(std::int32_t,void* out,std::uint32_t size){std::memset(out,0,size);return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* out){*out=1024;return 0;}
std::int32_t sdk_draft_num_rounds(std::uint8_t* out){*out=5;return 0;}
std::int32_t sdk_item_info(std::uint32_t,item_info* out){*out={};return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* out){*out={};return 0;}
std::int32_t sdk_bc_round_number(std::uint32_t* out){*out=host::round;return 0;}
std::int64_t sdk_fuel_remaining(){host::tick("fuel");return host::fuel;}
std::int32_t sdk_champion_is_alive(std::uint32_t,std::int32_t* out){host::tick("alive");*out=host::alive;return 0;}
std::int32_t sdk_champion(std::uint32_t h,champion_info* out){host::tick("champion");*out={};auto p=h?host::foe:host::pos;out->x=p.x;out->y=p.y;out->health=h?100:host::hp;out->max_health=1000;out->strength=60;out->attack_range=4;out->team=h?0:1;out->state=1|16|(host::mobile?8:0)|(host::casting?2048:0)|host::channel;return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* out){*out={};return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t,std::uint32_t slot,ability_props* out){*out={};if(slot==0){out->kind=static_cast<unsigned>(ability_kind::shield);out->targets=ability_target_self;out->payload.shield={0,1,1};}return 0;}
std::int32_t sdk_champion_cooldown(std::uint32_t,std::uint32_t,std::int32_t* out){*out=0;return 0;}
std::int32_t sdk_champion_restrictions(std::uint32_t,std::uint8_t* out){host::tick("restrictions");*out=host::restricted?buff_restrictions::move.bits():0;return 0;}
std::int32_t sdk_champion_gems(std::uint32_t,std::uint32_t* out){host::tick("observe");*out=0;return 0;}
std::int32_t sdk_champion_gold(std::uint32_t,std::uint32_t* out){*out=0;return 0;}
std::int32_t sdk_champion_wards(std::uint32_t,ward_resources* out){*out={};return 0;}
std::int32_t sdk_set_priority(std::int32_t){return 0;}
std::int32_t sdk_bc_submitted_gems(std::uint32_t,std::uint32_t* out){*out=0;return 0;}
std::int32_t sdk_vision(std::uint64_t* out){std::memset(out,255,128);return 0;}
std::int32_t sdk_ally_occupancy(std::uint64_t* out){std::memcpy(out,host::occupied,128);host::set(out,host::pos.x,host::pos.y);return 0;}
std::int32_t sdk_enemy_occupancy(std::uint64_t* out){host::zero(out);if(host::enemy)host::set(out,host::foe.x,host::foe.y);return 0;}
std::int32_t sdk_camp_occupancy(std::uint64_t* out){host::tick("scan");++host::scans;if(host::vanish_risk&&host::scans==4)host::camps[0].strength=0;host::zero(out);for(auto c:host::camps)host::set(out,c.pos.x,c.pos.y);return 0;}
std::int32_t sdk_teleport_occupancy(std::uint64_t* out){host::zero(out);return 0;}
std::int32_t sdk_champion_at(std::int32_t x,std::int32_t y,std::uint32_t* out){*out=(host::enemy&&host::foe==vec2{x,y})?1:0;return 0;}
std::int32_t sdk_camp_at(std::int32_t x,std::int32_t y,std::uint32_t* out){for(unsigned i=0;i<host::camps.size();++i)if(host::camps[i].pos==vec2{x,y}){*out=i;return 0;}std::abort();}
std::int32_t sdk_map_camp_info(std::uint32_t h,camp_info* out){auto c=host::camps.at(h);*out={c.pos.x,c.pos.y,static_cast<int>(h)};return 0;}
std::int32_t sdk_map_camp_group_of(std::uint32_t,std::uint32_t* out){*out=0;return 0;}
std::int32_t sdk_camp_state(std::uint32_t h,std::uint32_t* out){host::tick("collect");*out=host::camps.at(h).state;return 0;}
std::int32_t sdk_camp(std::uint32_t h,camp_state* out){auto c=host::camps.at(h);*out={};out->x=c.pos.x;out->y=c.pos.y;out->health=500;out->max_health=1000;out->strength=c.strength;return 0;}
std::int32_t sdk_camp_design(std::int32_t h,camp_design* out){*out={};out->base_stats.base_attack_range=host::camps.at(h).range;return 0;}
std::int32_t sdk_attack(std::uint32_t,std::uint32_t){++host::attacks;host::actions.push_back("attack");if(host::kill)host::enemy=false;return 0;}
std::int32_t sdk_cast(std::uint32_t,std::uint32_t,std::uint32_t,std::int32_t,std::int32_t,std::int32_t* out){++host::casts;host::actions.push_back("cast");if(host::spend_move)host::mobile=false;host::casting=false;*out=1;return 0;}
std::int32_t sdk_move_to(std::int32_t x,std::int32_t y,std::int32_t* out){++host::moves;host::actions.push_back("move");*out=!host::hidden;if(host::throw_move)return static_cast<int>(error_code::invalid_action_move_bad_destination);if(*out){assert(host::inside(x,y));assert(!host::get(host::occupied,x,y));host::pos={x,y};host::mobile=false;}return 0;}
std::int32_t sdk_bc_get_last_error(char* out,std::uint32_t n){if(n)out[0]=0;return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* out){host::zero(out);return 0;}
std::int32_t sdk_Bitboard_Test(const std::uint64_t* b,std::int32_t x,std::int32_t y,std::int32_t* out){*out=host::get(b,x,y);return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t* b,std::int32_t x,std::int32_t y,std::int32_t v){host::set(b,x,y,v);return 0;}
std::int32_t sdk_Bitboard_NumSetBits(const std::uint64_t* b,std::uint32_t* out){*out=0;for(int i=0;i<16;++i)*out+=std::popcount(b[i]);return 0;}
std::int32_t sdk_Bitboard_GetSetBits(const std::uint64_t* b,void* data,std::size_t cap,std::uint32_t* out){host::tick("enumerate");*out=0;auto p=static_cast<vec2*>(data); // reverse SDK order to exercise explicit y/x ranking
for(int y=31;y>=0;--y)for(int x=31;x>=0;--x)if(host::get(b,x,y)&&*out<cap)p[(*out)++]={x,y};return 0;}
std::int32_t sdk_Bitboard_Union(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* out){for(int i=0;i<16;++i)out[i]=a[i]|b[i];return 0;}
std::int32_t sdk_Bitboard_Intersect(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* out){for(int i=0;i<16;++i)out[i]=a[i]&b[i];return 0;}
std::int32_t sdk_Bitboard_Not(const std::uint64_t* a,std::uint64_t* out){for(int i=0;i<16;++i)out[i]=~a[i];return 0;}
std::int32_t sdk_Bitboard_DrawChebyshev(std::uint64_t* out,std::int32_t x,std::int32_t y,float r){for(int j=0;j<32;++j)for(int i=0;i<32;++i)if(std::max(abs(i-x),abs(j-y))<=r)host::set(out,i,j);return 0;}
std::int32_t sdk_Bitboard_ReachableMask(const std::uint64_t* b,std::int32_t x,std::int32_t y,std::uint64_t* out,std::uint16_t d){host::tick("reachable");assert(d==1);host::zero(out);for(int j=y-1;j<=y+1;++j)for(int i=x-1;i<=x+1;++i)if(!host::get(b,i,j))host::set(out,i,j);return 0;}
}}
namespace lp {
void World::init(){if(roster.empty())roster.push_back(self());width=height=32;columns=rows=3;preference={0};if(host::seed_task&&camps.empty()){
 camps.push_back({detail::handle_access::make_camp_group(static_cast<handle_camp_group_t>(0),0,0,10,{})});
 camps.back().lifecycle=1;
 }}
void World::refresh(const Snapshot&,Memory& m){host::memory=&m;if(host::seed_task&&!host::seeded){host::seeded=true;m.task=0;m.task_started=249;m.progressed=249;m.blocked=2;m.last_distance=17;m.exploration=9;}}
int World::chunk(vec2)const{return 0;}
void shop(Memory&){}
void advance_loop(World&,int){}
int choose_altar(World&,const Snapshot&,TurnBudget&,int){++host::work;return -1;}
int choose_camp(World&,const Snapshot&,TurnBudget&,bool,bool){++host::work;return -1;}
bitboard camp_goals(const Objective&,const Snapshot&){++host::work;return {};}
bool explore(World&,TurnBudget&,Memory&){++host::work;return false;}
bool bank(World&,TurnBudget&,Memory&){++host::work;return false;}
bool retreat(TurnBudget&,Memory&){++host::work;return false;}
RouteStatus move_to(bitboard,bool,TurnBudget&,Memory&,bool){++host::work;return RouteStatus::wait;}
}
static void require(bool ok,const char* label){if(!ok){std::cerr<<"FAIL: "<<label<<'\n';std::exit(1);}}
static bool helper(){lp::TurnBudget b{250,2};auto result=lp::spawn_camp_reposition(b);require(b.fields==2,"no field quota");return result;}
int main(){
using namespace host;
reset();require(helper()&&moves==1&&pos==vec2{27,28},"Heart zero exposure y/x move");require(scans==4,"one helper camp scan beyond three observation scans");
reset();{Bot bot;bot.play_turn();require(moves==1&&memory&&memory->state==lp::State::defend,"actual defend dispatch");require(memory->task==-1&&memory->altar==-1&&memory->last_distance==65535&&memory->blocked==0&&work==0,"no task/navigation mutation or economic dependency");}
reset();seed_task=true;{Bot bot;bot.play_turn();require(moves==1&&memory->task==0&&memory->task_started==249&&memory->progressed==249&&memory->blocked==2&&memory->last_distance==17&&memory->exploration==9&&work==0,"existing task/navigation memory preserved");}
reset();enemy=true;require(!helper()&&moves==0,"fresh distant foe veto independent of nearby count");
reset();enemy=true;{Bot bot;bot.play_turn();require(moves==0&&attacks==0,"far visible foe veto");}
reset();enemy=true;foe={26,27};{Bot bot;bot.play_turn();require(attacks==1&&moves==0,"original in-range defense");}
reset();enemy=true;foe={26,27};kill=true;{Bot bot;bot.play_turn();require(attacks==1&&!enemy&&moves==0,"last entry foe killed still vetoes");}
reset();shield=casting=true;hp=600;{Bot bot;bot.play_turn();require(casts==1&&moves==1&&actions==std::vector<std::string>{"cast","move"},"defend cast before move despite fight false");}
reset();shield=casting=spend_move=true;hp=600;{Bot bot;bot.play_turn();require(casts==1&&moves==0,"cast spent mobility");}
for(int mode=0;mode<10;++mode){reset();switch(mode){case 0:camps.clear();break;case 1:camps[0].state=0;break;case 2:camps[0].state=2;break;case 3:camps[0].strength=0;break;case 4:pos={26,27};break;case 5:alive=false;break;case 6:channel=2;break;case 7:mobile=false;break;case 8:restricted=true;break;case 9:camps[0].range=3;break;}require(!helper()&&moves==0,"veto/false camp risk");}
for(int state:{0,2,3}){reset();camps.push_back({{29,29},state==3?0.0f:60.0f,9,static_cast<unsigned>(state==3?1:state)});require(helper()&&pos==vec2{27,28},"inactive camps do not veto safe neighbor");}
for(int flag:{2,4,4096}){reset();channel=flag;require(!helper()&&moves==0,"all channels preserved");}
reset();vanish_risk=true;require(!helper()&&moves==0,"captured camp set must cover origin too");
reset();for(int y=27;y<=29;++y)for(int x=27;x<=29;++x)if(vec2{x,y}!=pos)set(occupied,x,y);require(!helper()&&moves==0,"all in-spawn occupied");
reset();pos={27,28};camps={{{29,29},60,2}};require(!helper()&&moves==0,"only outside spawn safe");
reset();camps.push_back({{29,29},10,2});require(!helper()&&moves==0,"positive but lower incoming refused");
reset();camps.push_back({{23,26},30,4});require(helper()&&pos==vec2{28,28},"multiple covering camps");
for(bool throws:{false,true}){reset();hidden=true;throw_move=throws;auto v=lp::observation_version();require(!helper()&&moves==1&&pos==vec2{27,27}&&lp::observation_version()>v,"one rejected move invalidates without success");}
reset();fuel=lp::Config::reserve;require(!helper()&&scans==0,"fuel entry guard");
// Sweep each occurrence of host query boundaries: a suspension can happen
// during observe, capture, candidate enumeration, final guards or move_checked.
for(const char* name:{"observe","scan","collect","reachable","enumerate","restrictions","alive","champion","fuel"}){
 reset();hook=name;hook_n=100000;helper();int count=hook_seen;
 for(bool roll:{false,true})for(int n=1;n<=count;++n){reset();hook=name;hook_n=n;rollover=roll;helper(); // No atomicity claim inside the final move_checked SDK calls.
 if(!((std::string(name)=="restrictions"||std::string(name)=="champion")&&n==count))require(moves==0,"suspension boundary abort");
 }
}
reset();camps.clear();{Bot bot;bot.play_turn();require(moves==0&&memory->state==lp::State::healing&&scans==3,"healing no helper refresh");}
reset();channel=4;{Bot bot;bot.play_turn();require(moves==0&&memory->state==lp::State::bank&&scans==3,"bank channel no helper refresh");}
reset();camps.clear();hp=1000;{Bot bot;bot.play_turn();require(moves==0&&work>0&&scans==3,"ordinary work no helper refresh");}
std::cout<<"PASS: production spawn camp helper and Bot defend integration\n";
}
