// Actual SDK wrappers and production LiveBackend; only host imports are mocked.
#include "../src/recovery_sdk.cpp"
#include <cassert>
#include <iostream>
using namespace cambc;
using namespace lp;
using namespace lp::recovery;
namespace fake {
using Tiles=std::vector<vec2>;
auto& boards(){static std::vector<Tiles> data(1);return data;}
Tiles read(const uint64_t* b){return boards().at(*b);}
void write(uint64_t* b,Tiles v){boards().push_back(std::move(v));*b=boards().size()-1;}
int round=1, exports=0, counts=0, fields=0, actions=0, roll_export=0, roll_field=0, fuel_export=0, malformed=0;
int delayed_fuel_export=0, fuel_checks=0;
bool roll_compute=false;
int fuel=100000;bool targets=false, legal=true, heal_ready=true, visible_full=true, occupied_extra=true;int casts=0,attacks=0;
vec2 origin{40,28};
Tiles all(int w=45,int h=30){Tiles v;for(int y=0;y<h;++y)for(int x=0;x<w;++x)v.push_back({x,y});return v;}
}
namespace cambc::detail {
extern "C" {
int32_t sdk_get_settings(game_settings* p){*p={};return 0;}
int32_t sdk_shared_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_bc_metadata(metadata* p){*p={45,30,6,4,6,1536,3072};return 0;}
int32_t sdk_bc_map_symmetry(int32_t* p){*p=0;return 0;}
int32_t sdk_my_champion(){return 1;} int32_t sdk_my_team(){return 0;}
int32_t sdk_item_info(uint32_t,item_info* p){*p={};return 0;}
int32_t sdk_consumable_info(uint32_t,consumable_info* p){*p={};return 0;}
int32_t sdk_champion_design(int32_t,champion_design* p){*p={};return 0;}
int32_t sdk_draft_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_champion_identity(uint32_t h,champion_identity* p){*p={};p->team=h==3?1:0;return 0;}
int32_t sdk_champion_ability_props(uint32_t h,uint32_t slot,ability_props* p){*p={};if(h==1&&slot==0){p->kind=uint32_t(ability_kind::heal);p->targets=2;p->payload.heal.range=3;p->payload.heal.modifier=1;}return 0;}
int32_t sdk_Bitboard_ImportRawBuffer(uint64_t* b,const uint8_t* in,size_t){uint64_t key;std::memcpy(&key,in,sizeof(key));fake::write(b,fake::boards().at(key));return 0;}
int32_t sdk_Bitboard_Zero(uint64_t* b){fake::write(b,{});return 0;}
int32_t sdk_Bitboard_Set(uint64_t* b,int32_t x,int32_t y,int32_t value){auto v=fake::read(b);if(value)v.push_back({x,y});fake::write(b,v);return 0;}
int32_t sdk_bc_map_mask(int32_t,uint64_t* b){return sdk_Bitboard_Zero(b);}
int32_t sdk_spawn_region(int32_t,aabb* p){*p={0,0,1,1};return 0;}
int32_t sdk_Bitboard_Union(const uint64_t* a,const uint64_t* b,uint64_t* out){auto v=fake::read(a);for(auto p:fake::read(b))if(std::find(v.begin(),v.end(),p)==v.end())v.push_back(p);fake::write(out,v);return 0;}
int32_t sdk_Bitboard_NumSetBits(const uint64_t* b,uint32_t* n){++fake::counts;*n=fake::read(b).size();return 0;}
int32_t sdk_Bitboard_GetSetBits(const uint64_t* b,void* out,size_t cap,uint32_t* n){auto v=fake::read(b);assert(v.size()<=cap);std::copy(v.begin(),v.end(),static_cast<vec2*>(out));*n=v.size();++fake::exports;
 if(fake::malformed==fake::exports&&*n)static_cast<vec2*>(out)[0]={45,0};
 if(fake::roll_export==fake::exports)++fake::round;
 if(fake::fuel_export==fake::exports)fake::fuel=0;
 if(fake::delayed_fuel_export==fake::exports)fake::fuel_checks=2;
 return 0;}
int32_t sdk_Bitboard_ExportLinearBuffer(const uint64_t*,uint8_t* p,size_t n){assert(n==169);std::fill(p,p+n,0);return 0;}
int32_t sdk_Bitboard_DrawChebyshev(uint64_t* b,int32_t x,int32_t y,float r){fake::Tiles v;for(auto p:fake::all())if(std::max(abs(x-p.x),abs(y-p.y))<=r)v.push_back(p);fake::write(b,v);return 0;}
int32_t sdk_vision(uint64_t* b){fake::write(b,fake::visible_full?fake::all():fake::Tiles{{0,0}});return 0;}
int32_t sdk_ally_occupancy(uint64_t* b){fake::Tiles v{fake::origin};if(fake::targets)v.push_back({44,29});fake::write(b,v);return 0;}
int32_t sdk_enemy_occupancy(uint64_t* b){fake::write(b,fake::targets?fake::Tiles{{43,29}}:fake::Tiles{});return 0;}
int32_t sdk_camp_occupancy(uint64_t* b){return sdk_Bitboard_Zero(b);}
int32_t sdk_teleport_occupancy(uint64_t* b){fake::write(b,fake::occupied_extra?fake::Tiles{{20,20}}:fake::Tiles{});return 0;}
int32_t sdk_champion_at(int32_t x,int32_t,uint32_t* h){*h=x==44?2:x==43?3:1;return 0;}
int32_t sdk_champion(uint32_t h,champion_info* p){*p={};p->x=h==1?fake::origin.x:h==2?44:43;p->y=h==1?fake::origin.y:29;p->health=h==1?30:20;p->max_health=100;p->attack_range=3;p->state=1|8|(fake::legal?(16|2048):0);return 0;}
int32_t sdk_champion_restrictions(uint32_t,uint8_t* p){*p=0;return 0;}
int32_t sdk_champion_buff_data(uint32_t,buff_data*,uint32_t,uint32_t* n){*n=0;return 0;}
int32_t sdk_champion_cooldown(uint32_t,uint32_t,int32_t* n){*n=fake::heal_ready?0:1;return 0;}
int32_t sdk_bc_round_number(uint32_t* p){*p=fake::round;return 0;}
int64_t sdk_fuel_remaining(){if(fake::fuel_checks&&!--fake::fuel_checks)fake::fuel=0;return fake::fuel;}
int32_t sdk_DistanceField_ComputeWithExpansionCount(const uint64_t*,const uint64_t*,uint64_t*,uint16_t*,uint16_t max,uint16_t* n){assert(max==65535);++fake::fields;if(fake::roll_compute)++fake::round;*n=1350;return 0;}
int32_t sdk_DistanceField_ExportLinearBuffer(const uint16_t*,uint8_t* out,size_t n){assert(n==2700);auto p=reinterpret_cast<uint16_t*>(out);for(int i=0;i<1350;++i)p[i]=i/45+i%45;if(fake::roll_field)++fake::round;return 0;}
int32_t sdk_champion_ability_heal_against(uint32_t,uint32_t,uint32_t,float* p){*p=30;return 0;}
int32_t sdk_cast(uint32_t,uint32_t,uint32_t,int32_t,int32_t,int32_t* p){++fake::actions;++fake::casts;*p=1;return 0;}
int32_t sdk_attack(uint32_t,uint32_t){++fake::actions;++fake::attacks;return 0;}
}
}
namespace lp {
bitboard static_blocked(){bitboard b;fake::write(b.ptr(),{{7,0},{8,0},{9,0},{44,29}});return b;}
unsigned observation_version(){return 0;}
void invalidate_observations(){}
}
#include "adapter_unused_imports.inc"

int main(){
    // Pure production conversion, independent of host packing and map metadata.
    for(auto [w,h]:{std::pair{45,30},std::pair{5,3}}){
        std::vector<vec2> sparse;for(int i:{0,7,8,9,w-1,w,w*h-1})sparse.push_back({i%w,i/w});
        for(auto coords:{std::vector<vec2>{},fake::all(w,h),sparse}){
            auto bytes=scalar_tiles(w,h,coords);assert(bytes.size()==size_t(w*h));
            for(int i=0;i<w*h;++i)assert(bytes[i]==(std::find(coords.begin(),coords.end(),vec2{i%w,i/w})!=coords.end()));
        }
    }
    auto invalid=[](int w,int h,std::vector<vec2> v){try{scalar_tiles(w,h,v);assert(false);}catch(Halt e){assert(e.status==Status::incomplete);}};
    for(auto [w,h]:{std::pair{0,1},std::pair{-1,2},std::pair{1,0},std::pair{16385,1},std::pair{2147483647,2147483647}})invalid(w,h,{});
    for(auto p:{vec2{-1,0},vec2{0,-1},vec2{45,0},vec2{0,30}})invalid(45,30,{p});
    invalid(5,3,std::vector<vec2>(16,{0,0}));assert(scalar_tiles(128,128,std::vector<vec2>{}).size()==16384);
    World world;world.width=45;world.height=30;Memory memory;TurnBudget budget{fake::round};RecoveryRuntime cache;
    LiveBackend backend(world,memory,budget,cache);
    // Exercise the actual checked positions() export + production scalar helper on both shapes.
    for(auto [w,h]:{std::pair{45,30},std::pair{5,3}}){
        fake::Tiles sparse;for(int i:{0,7,8,9,w-1,w,w*h-1})sparse.push_back({i%w,i/w});
        for(auto coords:{fake::Tiles{},fake::all(w,h),sparse}){
            bitboard source;fake::write(source.ptr(),coords);
            assert(backend.scalar(source,w,h)==scalar_tiles(w,h,coords));
        }
    }
    {bitboard bad;fake::write(bad.ptr(),fake::Tiles(16,{0,0}));
     try{backend.scalar(bad,5,3);assert(false);}catch(Halt e){assert(e.status==Status::incomplete);}
     int before=fake::exports;
     try{backend.scalar(bad,0,3);assert(false);}catch(Halt e){assert(e.status==Status::incomplete);}
     assert(fake::exports==before);}
    assert(backend.prepare(backend.turn)==Status::ready);
    assert(fake::fields==1&&budget.fields==1);assert(cache.terrain->blocked.size()==1350&&cache.terrain->spawn.size()==1350&&cache.terrain->home.size()==1350);
    assert(cache.terrain->blocked[1349]&&cache.terrain->spawn[0]&&!cache.terrain->spawn[1349]);
    bitboard board;auto old=board.export_linear_buffer();assert(old.size()==169);auto parent_admission=[](const auto& visible,const auto& occupied){
        return visible.size()!=1350||occupied.size()!=1350?Status::incomplete:Status::ready;
    };
    assert(parent_admission(old,old)==Status::incomplete); // Same length guard as parent capture.
    Scene scene;assert(backend.capture(scene)==Status::ready);assert(scene.visible.size()==1350&&scene.occupied.size()==1350);
    assert(scene.occupied[20*45+20]);for(int i=1;i<=7;++i)assert(!scene.occupied[20*45+20+i]);
    assert(!scene.occupied[scene.terrain->index(scene.pos)]);assert(scene.visible[1349]&&!scene.occupied[1349]);
    auto plan=select_plan(scene);assert(plan.complete&&plan.raw>0&&plan.first.kind==Kind::step);
    auto saved=scene.visible;fake::visible_full=false;fake::occupied_extra=false;
    Scene newer;assert(backend.capture(newer)==Status::ready);
    assert(!newer.visible[1349]&&!newer.occupied[20*45+20]);
    assert(scene.visible==saved&&scene.occupied[20*45+20]&&scene.terrain->blocked[1349]);
    fake::visible_full=true;fake::occupied_extra=true;
    // Both defense masks: distant rows, final cell out of range, then final cell in range.
    fake::targets=true;assert(backend.defend(scene));assert(fake::attacks==1&&fake::casts==0); // ally (44,29) outside range; foe (43,29) inside
    fake::origin={41,28};Scene end;assert(backend.capture(end)==Status::ready);assert(backend.defend(end));assert(fake::casts==1);
    for(bool heal:{false,true}){
        fake::origin=heal?vec2{41,28}:vec2{40,28};fake::heal_ready=heal;
        fake::delayed_fuel_export=fake::exports+1;
        try{backend.defend(end);assert(false);}catch(Halt e){assert(e.status==Status::incomplete);}
        assert(fake::actions==2);fake::delayed_fuel_export=0;fake::fuel=100000;
    }
    fake::heal_ready=true;fake::legal=false;assert(!backend.defend(end));assert(fake::actions==2);fake::legal=true;fake::targets=false;
    // Malformed and stale conversion never reach controller actions or publish partial static cache.
    for(int offset:{1,2})for(int mode=0;mode<4;++mode){
        RecoveryRuntime fresh;TurnBudget b{fake::round};fake::malformed=mode==0?fake::exports+offset:0;fake::roll_export=mode==1?fake::exports+offset:0;fake::fuel_export=mode==2?fake::exports+offset:0;fake::delayed_fuel_export=mode==3?fake::exports+offset:0;
        auto result=recover(Intent::health,world,memory,b,fresh);assert(result.stop_dispatch()&&!fresh.terrain&&fake::actions==2);
        fake::malformed=fake::roll_export=fake::fuel_export=fake::delayed_fuel_export=0;fake::fuel=100000;
    }
    {World bad;bad.width=2147483647;bad.height=2147483647;
     RecoveryRuntime fresh;TurnBudget b{fake::round};
     assert(recover(Intent::health,bad,memory,b,fresh).status==Status::incomplete&&!fresh.terrain&&fake::actions==2);}
    {RecoveryRuntime fresh;TurnBudget b{fake::round,Config::max_fields};int fields=fake::fields;
     assert(recover(Intent::health,world,memory,b,fresh).status==Status::initialization_deferred&&!fresh.terrain&&fake::fields==fields);}
    // Completed static full field/export survives rollover, and is reused next round.
    for(bool at_compute:{false,true}) {
    RecoveryRuntime completed;TurnBudget b{fake::round};fake::roll_compute=at_compute;fake::roll_field=!at_compute;int before=fake::fields;
    auto stale=recover(Intent::health,world,memory,b,completed);assert(stale.status==Status::stale&&completed.terrain&&fake::fields==before+1&&fake::actions==2);fake::roll_field=0;fake::roll_compute=false;
    TurnBudget next{fake::round};LiveBackend reuse(world,memory,next,completed);assert(reuse.prepare(reuse.turn)==Status::ready&&fake::fields==before+1&&next.fields==0);
    for(int offset:{1,2})for(int mode=0;mode<4;++mode){TurnBudget dyn{fake::round};fake::malformed=mode==0?fake::exports+offset:0;fake::roll_export=mode==1?fake::exports+offset:0;fake::fuel_export=mode==2?fake::exports+offset:0;fake::delayed_fuel_export=mode==3?fake::exports+offset:0;
        auto result=recover(Intent::health,world,memory,dyn,completed);assert(result.stop_dispatch()&&fake::actions==2);
        fake::malformed=fake::roll_export=fake::fuel_export=fake::delayed_fuel_export=0;fake::fuel=100000;
    }
    }
    assert(fake::counts==fake::exports);std::cout<<"PASS: production coordinate conversion, real SDK wrappers and LiveBackend capture/planner/defense/rollover (mock host)\n";
}
