// Real EconomicCapture + public SDK; strict scripted raw host, no game.
#include "economic_scene_sdk.h"
#include "economic_service_sdk.h"
#include "economic_fields_sdk.h"
#include "economic_plan_sdk.h"
#include "economic_runtime_sdk.h"
#include <iostream>
#include <stdexcept>
#include <queue>
using namespace lp;using namespace lp::economic;
namespace fake {
using Tiles=std::vector<vec2>;
auto& boards(){static std::vector<Tiles> values(1);return values;}
Tiles board(const uint64_t* p){return boards().at(*p);}
void board(uint64_t* p,Tiles v){boards().push_back(std::move(v));*p=boards().size()-1;}
struct Camp {unsigned key;vec2 pos;float hp=300,strength=0;bool visible=true,awake=false;camp_type type=camp_type::gem_cluster;};
auto& camps(){static std::vector<Camp> values;return values;}
Camp& camp_at(unsigned key){for(auto& c:camps())if(c.key==key)return c;throw std::runtime_error("unexpected camp identity");}
int round=10,mode=0,actions=0,camp_reads=0,camp_identities=0,designs=0,environment=0,lock_reads=0;
int lifecycle=1,cooldown=0,timer=5,channel_timer=5;
int fields=0,field_exports=0;bool roll_field=false,roll_compute=false;
int priorities=0,ward_queries=0,recoveries=0;bool roll_priority=false;uint32_t gold=0;
uint32_t gems=0,carried_locks=0,lock_hits=0;
bool enemy_lock=false,lock_result=true,submit_starts=true,roll_submit=false;
int lock_uses=0,submissions=0,lock_attacks=0,submit_error=0;
vec2 bank_altar{8,7};
auto& walls(){static Tiles values{{1,1}};return values;}
unsigned revision=1;
uint32_t flags=1|8|16|2048;
uint64_t fuel=100000;
vec2 origin{7,7};float health=1000;
bool extra_occupancy=false,roll_locks=false,revise_locks=false,error_locks=false,broken_sleep=false;
Tiles all(){Tiles out;for(int y=0;y<16;++y)for(int x=0;x<16;++x)out.push_back({x,y});return out;}
}
namespace cambc::detail {extern "C" {
int32_t sdk_bc_get_last_error(char*,uint32_t){return 0;}
int32_t sdk_get_settings(game_settings* p){*p={};p->submit_gems_range=1;p->capture_time=5;p->submit_gem_duration_multiplier=0.1;p->submit_gem_minimum_duration=1;p->winning_gems=1000;p->altar_lock_hits=5;return 0;}
int32_t sdk_shared_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_bc_metadata(metadata* p){*p={16,16,2,2,2,256,512};return 0;}
int32_t sdk_bc_map_symmetry(int32_t* p){*p=0;return 0;}
int32_t sdk_my_champion(){return 1;}int32_t sdk_my_team(){return 0;}
int32_t sdk_item_info(uint32_t,item_info* p){*p={};return 0;}
int32_t sdk_consumable_info(uint32_t,consumable_info* p){*p={};return 0;}
int32_t sdk_champion_design(int32_t,champion_design* p){*p={};p->base_stats.base_move_speed=1;return 0;}
int32_t sdk_draft_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_read_draft_memory(int32_t,void*,uint32_t){return 0;}
int32_t sdk_spawn_region(int32_t,aabb* p){*p={0,0,1,1};return 0;}
int32_t sdk_Bitboard_Zero(uint64_t* p){fake::board(p,{});return 0;}
int32_t sdk_Bitboard_ImportRawBuffer(uint64_t* p,const uint8_t* raw,size_t){uint64_t key;std::memcpy(&key,raw,sizeof(key));fake::board(p,fake::boards().at(key));return 0;}
int32_t sdk_Bitboard_Set(uint64_t* p,int32_t x,int32_t y,int32_t value){auto v=fake::board(p);std::erase(v,vec2{x,y});if(value)v.push_back({x,y});fake::board(p,v);return 0;}
int32_t sdk_Bitboard_DrawChebyshev(uint64_t* p,int32_t x,int32_t y,float r){auto v=fake::board(p);for(auto t:fake::all())if(std::max(std::abs(t.x-x),std::abs(t.y-y))<=r&&std::find(v.begin(),v.end(),t)==v.end())v.push_back(t);fake::board(p,v);return 0;}
int32_t sdk_Bitboard_Intersect(const uint64_t* a,const uint64_t* b,uint64_t* p){auto v=fake::board(a),other=fake::board(b);std::erase_if(v,[&](auto t){return std::find(other.begin(),other.end(),t)==other.end();});fake::board(p,v);return 0;}
int32_t sdk_Bitboard_Union(const uint64_t* a,const uint64_t* b,uint64_t* p){auto v=fake::board(a);for(auto t:fake::board(b))if(std::find(v.begin(),v.end(),t)==v.end())v.push_back(t);fake::board(p,v);return 0;}
int32_t sdk_Bitboard_Not(const uint64_t* a,uint64_t* p){auto v=fake::all(),other=fake::board(a);std::erase_if(v,[&](auto t){return std::find(other.begin(),other.end(),t)!=other.end();});fake::board(p,v);return 0;}
int32_t sdk_Bitboard_IsZero(const uint64_t* p,int32_t* result){*result=fake::board(p).empty();return 0;}
int32_t sdk_Bitboard_ExportLinearBuffer(const uint64_t* p,uint8_t* bytes,size_t size){if(size!=32)throw std::runtime_error("wrong packed export size");std::fill_n(bytes,size,0);for(auto t:fake::board(p)){const int cell=t.y*16+t.x;bytes[cell/8]|=1u<<(cell%8);}return 0;}
int32_t sdk_Bitboard_NumSetBits(const uint64_t* p,uint32_t* n){*n=fake::board(p).size();return 0;}
int32_t sdk_Bitboard_GetSetBits(const uint64_t* p,void* out,size_t cap,uint32_t* n){auto v=fake::board(p);if(cap<v.size())throw std::runtime_error("short SDK coordinate buffer");std::copy(v.begin(),v.end(),static_cast<vec2*>(out));*n=v.size();return 0;}
int32_t sdk_Bitboard_Test(const uint64_t* p,int32_t x,int32_t y,int32_t* result){auto v=fake::board(p);*result=std::find(v.begin(),v.end(),vec2{x,y})!=v.end();return 0;}
int32_t sdk_bc_map_mask(int32_t,uint64_t* p){return sdk_Bitboard_Zero(p);}
int32_t sdk_vision(uint64_t* p){++fake::environment;fake::board(p,fake::all());return 0;}
int32_t sdk_camp_occupancy(uint64_t* p){++fake::environment;fake::Tiles v;for(auto c:fake::camps())if(c.visible&&c.hp>0)v.push_back(c.pos);fake::board(p,v);return 0;}
int32_t sdk_awake_camp_occupancy(uint64_t* p){fake::Tiles v;for(auto c:fake::camps())if(c.visible&&c.hp>0&&c.awake)v.push_back(c.pos);fake::board(p,v);return 0;}
int32_t sdk_asleep_camp_occupancy(uint64_t* p){fake::Tiles v;for(auto c:fake::camps())if(c.visible&&c.hp>0&&!c.awake&&!fake::broken_sleep)v.push_back(c.pos);fake::board(p,v);return 0;}
int32_t sdk_ally_occupancy(uint64_t* p){fake::board(p,{fake::origin});return 0;}
int32_t sdk_enemy_occupancy(uint64_t* p){return sdk_Bitboard_Zero(p);}
int32_t sdk_teleport_occupancy(uint64_t* p){fake::board(p,fake::extra_occupancy?fake::Tiles{{6,7}}:fake::Tiles{});return 0;}
int32_t sdk_champion_identity(uint32_t,champion_identity* p){*p={0,int(champion_type::vesper_vale)};return 0;}
int32_t sdk_champion_ability_props(uint32_t,uint32_t slot,ability_props* p){*p={};if(slot==0){p->kind=uint32_t(ability_kind::attack_reset);}return 0;}
int32_t sdk_champion_cooldown(uint32_t,uint32_t,int32_t* p){*p=fake::cooldown;return 0;}
int32_t sdk_champion(uint32_t,champion_info* p){*p={};p->state=fake::flags;p->x=fake::origin.x;p->y=fake::origin.y;p->health=fake::health;p->max_health=1000;p->strength=100;p->attack_range=1;return 0;}
int32_t sdk_champion_restrictions(uint32_t,uint8_t* p){*p=0;return 0;}
int32_t sdk_champion_buff_data(uint32_t,buff_data*,uint32_t,uint32_t* p){*p=0;return 0;}
int32_t sdk_champion_gems(uint32_t,uint32_t* p){*p=fake::gems;return 0;}
int32_t sdk_champion_gold(uint32_t,uint32_t* p){*p=fake::gold;return 0;}
int32_t sdk_champion_items(uint32_t,uint32_t* p){std::fill_n(p,enum_map<item_type>{}.size(),0);return 0;}
// Public logical enum index 1 maps to raw engine inventory/action ID 2.
int32_t sdk_champion_consumables(uint32_t,uint32_t* p){std::fill_n(p,4,0);p[2]=fake::carried_locks;return 0;}
int32_t sdk_champion_channel_time(uint32_t,int32_t* p){*p=fake::channel_timer;return 0;}
int32_t sdk_bc_submitted_gems(uint32_t,uint32_t* p){*p=0;return 0;}
int32_t sdk_champion_at(int32_t x,int32_t y,uint32_t* p){if(vec2{x,y}!=fake::origin)throw std::runtime_error("unexpected champion tile");*p=1;return 0;}
int32_t sdk_camp_at(int32_t x,int32_t y,uint32_t* p){++fake::camp_identities;for(auto& c:fake::camps())if(c.visible&&c.hp>0&&c.pos==vec2{x,y}){*p=c.key;return 0;}return int32_t(error_code::api_not_found);}
int32_t sdk_map_camp_info(uint32_t key,camp_info* p){auto& c=fake::camp_at(key);*p={c.pos.x,c.pos.y,int(c.type)};return 0;}
int32_t sdk_map_camp_group_of(uint32_t,uint32_t* p){*p=0;return 0;}
int32_t sdk_camp_state(uint32_t key,uint32_t* p){auto& c=fake::camp_at(key);if(!c.visible)return int32_t(error_code::api_not_in_vision);*p=c.hp<=0?0:c.awake?1:2;return 0;}
int32_t sdk_camp(uint32_t key,camp_state* p){++fake::camp_reads;auto& c=fake::camp_at(key);if(!c.visible)return int32_t(error_code::api_not_in_vision);*p={c.pos.x,c.pos.y,c.hp,300,c.strength,0,{0,0}};return 0;}
int32_t sdk_camp_design(int32_t type,camp_design* p){++fake::designs;*p={};p->base_stats.base_health=300;p->base_stats.base_attack_range=1;p->base_stats.base_strength=type==int(camp_type::wolf)?20:0;return 0;}
int32_t sdk_camp_buffs(uint32_t,camp_buff_data*,uint32_t,uint32_t* p){*p=0;return 0;}
int32_t sdk_camp_group_state(uint32_t,uint32_t* p){*p=fake::lifecycle;return 0;}
int32_t sdk_camp_group_cooldown(uint32_t,int32_t* p){*p=5;return 0;}
int32_t sdk_camp_group_capture_state(uint32_t,camp_group_capture_state* p){*p={fake::timer,4};return 0;}
int32_t sdk_altar_locks(altar_lock_info* rows,uint32_t cap,uint32_t* n){
    ++fake::lock_reads;*n=fake::lock_hits?1:0;
    if(rows&&cap&&fake::lock_hits)rows[0]={uint32_t(entity_kind::altar_lock),90,uint32_t(fake::enemy_lock?1:0),fake::bank_altar.x,fake::bank_altar.y,fake::lock_hits};
    if(fake::roll_locks)++fake::round;if(fake::revise_locks)lp::invalidate_observations();return fake::error_locks?int32_t(error_code::api_not_found):0;
}
int32_t sdk_bc_round_number(uint32_t* p){*p=fake::round;return 0;}
int64_t sdk_fuel_remaining(){return int64_t(fake::fuel);}
int32_t sdk_attack(uint32_t kind,uint32_t key){
    if(kind==uint32_t(entity_kind::altar_lock)) {
        if(key!=90||!fake::lock_hits||!fake::enemy_lock)throw std::runtime_error("unexpected lock target");
        ++fake::lock_attacks;--fake::lock_hits;
    } else {
        if(kind!=uint32_t(entity_kind::camp))throw std::runtime_error("unexpected attack category");
        fake::camp_at(key).hp=std::max(0.0f,fake::camp_at(key).hp-100);
    }
    ++fake::actions;fake::flags&=~16u;return 0;
}
int32_t sdk_cast(uint32_t,uint32_t,uint32_t,int32_t,int32_t,int32_t* result){++fake::actions;fake::flags|=16u;fake::flags&=~2048u;fake::cooldown=10;*result=1;return 0;}
int32_t sdk_set_priority(int32_t){++fake::priorities;if(fake::roll_priority)++fake::round;return 0;}
int32_t sdk_move_to(int32_t x,int32_t y,int32_t* accepted){
    if(std::max(std::abs(x-fake::origin.x),std::abs(y-fake::origin.y))!=1)throw std::runtime_error("unexpected move distance");
    ++fake::actions;fake::origin={x,y};fake::flags&=~8u;*accepted=1;return 0;
}
int32_t sdk_use_consumable(uint32_t kind,int32_t x,int32_t y,int32_t* accepted){
    if(kind!=2||vec2{x,y}!=fake::bank_altar||!fake::carried_locks||fake::lock_hits)
        throw std::runtime_error("unexpected lock placement");
    ++fake::lock_uses;++fake::actions;*accepted=fake::lock_result;
    if(*accepted){--fake::carried_locks;fake::lock_hits=5;fake::enemy_lock=false;}return 0;
}
int32_t sdk_submit_gems(int32_t x,int32_t y){
    if(vec2{x,y}!=fake::bank_altar||!fake::gems)throw std::runtime_error("unexpected submission");
    ++fake::submissions;++fake::actions;
    if(fake::submit_error)return fake::submit_error;
    if(fake::lock_hits&&fake::enemy_lock)throw std::runtime_error("blind submission into enemy lock");
    if(fake::submit_starts){fake::flags|=4u;fake::channel_timer=2;}
    if(fake::roll_submit)++fake::round;return 0;
}
int32_t sdk_champion_wards(uint32_t,ward_resources* p){++fake::ward_queries;*p={};p->cooldown=1;return 0;}
int32_t sdk_DistanceField_ComputeWithExpansionCount(const uint64_t* walls,const uint64_t* roots,uint64_t* visited,uint16_t* output,uint16_t maximum,uint16_t* count) {
    if(maximum!=65535)throw std::runtime_error("limited field used as complete");
    ++fake::fields;std::fill_n(output,256,65535);std::array<bool,256> blocked{};
    for(auto p:fake::board(walls))blocked[p.y*16+p.x]=true;
    std::queue<vec2> queue;fake::Tiles reached;
    for(auto p:fake::board(roots))if(!blocked[p.y*16+p.x]&&output[p.y*16+p.x]!=0){output[p.y*16+p.x]=0;queue.push(p);reached.push_back(p);}
    while(!queue.empty()) {
        auto p=queue.front();queue.pop();
        for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx)if(dx||dy) {
            vec2 q{p.x+dx,p.y+dy};if(q.x<0||q.y<0||q.x>=16||q.y>=16)continue;
            const int cell=q.y*16+q.x;if(blocked[cell]||output[cell]!=65535)continue;
            output[cell]=output[p.y*16+p.x]+1;queue.push(q);reached.push_back(q);
        }
    }
    *count=reached.size();fake::board(visited,reached);if(fake::roll_compute)++fake::round;return 0;
}
int32_t sdk_DistanceField_ExportLinearBuffer(const uint16_t* input,uint8_t* output,size_t size) {
    if(size!=512)throw std::runtime_error("wrong uint16 field export size");
    ++fake::field_exports;std::memcpy(output,input,size);if(fake::roll_field)++fake::round;return 0;
}
}}
namespace lp {unsigned observation_version(){return fake::revision;}void invalidate_observations(){++fake::revision;}bitboard static_blocked(){bitboard out;fake::board(out.ptr(),fake::walls());return out;}}
namespace lp {
#ifndef LP_TEST_REAL_BANK
bool bank_position_safe(const economic::Scene& s){return s.economy.complete&&s.economy.self.alive;}
BankChoice choose_bank(const economic::Scene&,const economic::Task&,const action::Ledger&){return {};}
action::Result perform_bank(const economic::Scene&,const BankChoice&,LiveTurn&){throw std::runtime_error("unexpected bank mutation in gem-dispatch fixture");}
#endif
recovery::Outcome recover(recovery::Intent,World&,Memory&,TurnBudget&,RecoveryRuntime&,LiveTurn&){++fake::recoveries;return {recovery::Status::incomplete};}
}
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
void reset(unsigned count=49) {
    ++fake::round;fake::revision=1;fake::flags=1|8|16|2048;fake::origin={7,7};fake::health=1000;
    fake::actions=fake::camp_reads=fake::camp_identities=fake::designs=fake::environment=fake::lock_reads=0;
    fake::extra_occupancy=fake::roll_locks=fake::revise_locks=fake::error_locks=fake::broken_sleep=false;
    fake::lifecycle=1;fake::cooldown=0;fake::camps().clear();
    fake::fields=fake::field_exports=0;fake::roll_compute=fake::roll_field=false;fake::walls()={{1,1}};
    fake::priorities=fake::ward_queries=fake::recoveries=0;fake::roll_priority=false;fake::gold=0;
    fake::gems=fake::carried_locks=fake::lock_hits=0;fake::enemy_lock=fake::roll_submit=false;
    fake::lock_result=fake::submit_starts=true;fake::lock_uses=fake::submissions=fake::lock_attacks=fake::submit_error=0;
    fake::bank_altar={8,7};
    fake::camps().push_back({100,{8,7},30});
    for(int y=4;y<=10&&fake::camps().size()<count;++y)for(int x=8;x<=14&&fake::camps().size()<count;++x)
        if(vec2{x,y}!=vec2{8,7})fake::camps().push_back({100+unsigned(fake::camps().size()),{x,y}});
}
World world() {
    World w;w.width=w.height=16;w.altars.push_back({1,1});std::vector<camp> members;
    for(auto& c:fake::camps())members.push_back(cambc::detail::handle_access::make_camp(static_cast<handle_camp_t>(c.key),static_cast<handle_camp_group_t>(0),c.type,c.pos));
    auto group=cambc::detail::handle_access::make_camp_group(static_cast<handle_camp_group_t>(0),20,343,10,std::move(members));
    w.camps.push_back({group,{8,7},{},{}});return w;
}
struct Context {
    action::Ledger ledger;Memory memory;LiveTurn turn{ledger,memory,1};World w=world();EconomicCapture capture;
    Context(){CHECK(ledger.begin(turn.epoch(),fake::fuel));}
    Scene read(){return capture.capture(w,turn,0);}
    action::Result basic(const Scene& s) {
        ServiceChoice choice;choice.stop=ServiceStop::action;
        choice.request={s.economy.self.epoch,action::Op::basic,{100,8,7,-1,0,0,0},true};
        return perform_service(s,choice,turn);
    }
    action::Result reset() {
        CHECK(ledger.handoff(action::Owner::service,turn.epoch()));
        return turn.perform({turn.epoch(),action::Op::reset,{-1,0,0,0,0,0,0},true},[]{return true;},[]{return self().abilities()[0].use();});
    }
    void next(){ledger.finish();++fake::round;CHECK(ledger.begin(turn.epoch(),fake::fuel));}
};
int main(){try {
    reset();{Context c;auto before=c.read();CHECK(before.members.size()==49&&fake::camp_reads==49&&fake::camp_identities==49&&fake::designs==1);
        CHECK(before.members[0].hp==30&&before.members[0].hp_epoch==before.economy.self.epoch);
        auto first=c.basic(before);CHECK(first.accepted());int reads=fake::camp_reads,ids=fake::camp_identities;
        auto after=c.read();CHECK(fake::camp_reads==reads&&fake::camp_identities==ids);
        CHECK(!after.members[0].alive&&after.members[0].hp==0&&before.members[0].hp==30);
        CHECK(after.members[1].hp_epoch==before.economy.self.epoch&&after.members[1].unchanged_event==first.event);
        CHECK(c.ledger.observe(first.event,c.turn.epoch()));auto reset_result=c.reset();CHECK(reset_result.accepted());
        reads=fake::camp_reads;ids=fake::camp_identities;auto reset_after=c.read();
        CHECK(fake::camp_reads==reads&&fake::camp_identities==ids&&reset_after.can_attack);
        CHECK(reset_after.members[1].hp_epoch==before.economy.self.epoch&&reset_after.members[1].unchanged_event==reset_result.event);
        CHECK(fake::lock_reads==6); // one all-team wrapper snapshot/capture, count + fill
    }
    reset();{fake::camps()[0].hp=300;Context c;auto before=c.read();auto r=c.basic(before);CHECK(r.accepted());
        fake::extra_occupancy=true;int reads=fake::camp_reads,ids=fake::camp_identities;auto after=c.read();
        CHECK(fake::camp_reads==reads+49&&fake::camp_identities==ids+49&&after.members[0].hp==200);
        CHECK(after.members[1].unchanged_event==0&&after.members[1].hp_epoch==after.economy.self.epoch);
    }
    reset(2);{fake::camps()[0].type=camp_type::wolf;fake::camps()[0].hp=300;fake::camps()[0].strength=20;Context c;
        auto before=c.read();CHECK(fake::camp_reads==3);auto r=c.basic(before);CHECK(r.accepted());
        int reads=fake::camp_reads;auto after=c.read();CHECK(fake::camp_reads==reads+3); // harmful basic must be full
        CHECK(c.ledger.observe(r.event,c.turn.epoch()));auto reset_result=c.reset();CHECK(reset_result.accepted());
        fake::camps()[0].strength=60;reads=fake::camp_reads;auto changed=c.read();
        CHECK(fake::camp_reads==reads+1&&changed.members[0].strength==60&&changed.members[0].hp_epoch==after.economy.self.epoch);
    }
    reset(2);{fake::camps()[1].type=camp_type::wolf;fake::camps()[1].visible=false;fake::camps()[1].strength=20;Context c;
        auto s=c.read();CHECK(!s.members[1].known&&!s.members[1].hp_known&&!s.members[1].passive);
        ServiceIntent in;in.key={0,0,0,Purpose::gems,Role::worker};
        CHECK(select_service(s,in,c.ledger).stop==ServiceStop::unknown_wake);
    }
    for(int failure=0;failure<3;++failure) {
        reset(2);Context c;fake::lifecycle=3;CHECK(c.read().groups[0].observation.cycle==0);c.next();fake::lifecycle=1;
        fake::roll_locks=failure==0;fake::revise_locks=failure==1;fake::error_locks=failure==2;bool caught=false;
        try{c.read();}catch(TurnExpired){caught=true;}catch(cambc::error){caught=true;}
        CHECK(caught);fake::roll_locks=fake::revise_locks=fake::error_locks=false;c.next();
        auto coherent=c.read();CHECK(coherent.groups[0].observation.cycle==1); // no partial lifecycle publication
    }
    for(auto channel:{4u,4096u,2u}) {
        reset();Context c;fake::flags|=channel;auto s=c.read();
        CHECK(s.economy.complete&&s.economy.self.channel!=Channel::none&&s.economy.self.channel_timer==5);
        CHECK(fake::designs==0&&fake::environment==0&&fake::camp_reads==0&&fake::lock_reads==0&&c.ledger.captures==1);
    }
    reset();{Context c;fake::flags=0;auto dead=c.read();CHECK(!dead.economy.self.alive&&fake::designs==0);
        auto charged=c.ledger.queries_issued;CHECK(charged>0&&c.ledger.reconcile_life(++c.memory.life));
        CHECK(c.ledger.queries_issued==charged&&c.ledger.captures==1);
    }
    reset(2);{Context c;fake::broken_sleep=true;bool caught=false;
        try{c.read();}catch(const std::runtime_error&){caught=true;}
        CHECK(caught&&fake::actions==0&&c.ledger.captures==1);
    }
    reset();{Context c;EconomicFields fields;unsigned writes=0;auto s=c.read();
        CHECK(fields.prepare_delivery(c.w,c.turn,writes)==FieldStatus::ready&&fake::fields==1&&fake::field_exports==1);
        CHECK(fields.delivery()[0].status==DeliveryStatus::finite&&fields.delivery()[0].walk_edges==6);
        CHECK(fields.start_origin(c.w,s,c.turn)==FieldStatus::deferred); // no simultaneous second field
        c.next();s=c.read();fake::walls().insert(fake::walls().end(),{{0,0},{7,0},{8,0},{15,15}});
        CHECK(fields.start_origin(c.w,s,c.turn)==FieldStatus::planning&&fake::fields==2&&fake::field_exports==2);
        writes=4094;CHECK(fields.continue_origin(c.turn,s.economy.self.pos,writes)==FieldStatus::planning);
        CHECK(!fields.origin().complete&&fields.origin().blocked.size()==1);
        c.next();writes=0;CHECK(fields.continue_origin(c.turn,s.economy.self.pos,writes)==FieldStatus::ready);
        const auto& f=fields.origin();CHECK(f.blocked.size()==256&&f.covered.size()==256&&f.distances[7*16+7]==0&&f.conditional);
        for(unsigned cell:{0u,7u,8u,255u})CHECK(f.blocked[cell]);
        CHECK(!f.blocked[7*16+7]&&f.blocked[7*16+8]&&f.distances[7*16+8]==65535&&f.distances[7*16+6]==1);
        Route route;Key key{0,0,0,Purpose::gems,Role::worker};
        CHECK(route.start(fields.take_origin(),key,{{6,6}},false).status==Travel::planning);
        writes=0;auto next=route.continue_plan(c.turn.epoch(),s.economy.self.pos,writes);
        CHECK(next.status==Travel::ready&&next.next==Point{6,6}&&next.conditional&&fake::fields==2);
        CHECK(route.next(key,s.economy.self.pos).conditional); // retain the hypothesis label
    }
    reset(2);{Context c;EconomicFields fields;c.w.altars.clear();unsigned writes=0;
        CHECK(fields.prepare_delivery(c.w,c.turn,writes)==FieldStatus::ready&&fake::fields==0&&fields.delivery()[0].status==DeliveryStatus::no_altar);
        auto s=c.read();fake::walls().push_back({7,7});CHECK(fields.start_origin(c.w,s,c.turn)==FieldStatus::unavailable&&fake::fields==0);
    }
    for(bool reservation:{false,true}) {
        reset(2);Context c;EconomicFields fields;fake::origin=reservation?vec2{6,7}:vec2{8,7};fake::extra_occupancy=reservation;
        auto s=c.read();CHECK(fields.start_origin(c.w,s,c.turn)==FieldStatus::unavailable&&fake::fields==0);
    }
    for(bool in_compute:{false,true}) {
        reset(2);Context c;EconomicFields fields;auto s=c.read();fake::roll_compute=in_compute;fake::roll_field=!in_compute;bool caught=false;
        try{fields.start_origin(c.w,s,c.turn);}catch(TurnExpired){caught=true;}
        CHECK(caught&&fake::fields==1&&!fields.origin().complete&&!fields.origin_pending());
    }
    reset(2);{Context c;EconomicFields fields;auto s=c.read();s.members[1].passive=false;s.members[1].known=false;s.members[1].pos={9,9};s.members[1].range=1;
        CHECK(fields.start_origin(c.w,s,c.turn)==FieldStatus::planning);unsigned writes=0;
        CHECK(fields.continue_origin(c.turn,s.economy.self.pos,writes)==FieldStatus::ready);
        CHECK(!fields.origin().covered[9*16+9]&&!fields.origin().blocked[9*16+9]); // optimistic, explicitly unknown
    }
    reset();{Context c;EconomicPlanner planner;Owner owner;auto s=c.read();unsigned writes=0;
        auto first=planner.prepare(c.w,s,owner,c.turn,writes);
        CHECK(first.status==PlanStatus::deferred&&fake::fields==1); // delivery job owns this turn's field
        c.next();s=c.read();writes=0;auto selected=planner.prepare(c.w,s,owner,c.turn,writes);
        CHECK(selected.status==PlanStatus::ready&&selected.directive.decision==Decision::task);
        CHECK(selected.directive.task.key.object==0&&selected.directive.task.key.purpose==Purpose::gems);
        CHECK(selected.route.status==Travel::at_goal&&fake::fields==2&&fake::field_exports==2);
        CHECK(planner.route.accepted_path().size()==1); // origin is already a useful attack contact
        auto choice=select_service(s,{selected.directive.task.key},c.ledger);
        CHECK(choice.stop==ServiceStop::action&&choice.request.op==action::Op::basic);
        const auto target=unsigned(choice.request.target.key);
        const auto before_hp=fake::camp_at(target).hp;
        auto result=perform_service(s,choice,c.turn);CHECK(result.accepted());
        auto after=c.read();CHECK(fake::camp_at(target).hp==std::max(0.0f,before_hp-100)&&c.ledger.observe(result.event,c.turn.epoch()));
        CHECK(after.economy.self.epoch==c.turn.epoch()&&fake::camp_at(target).hp<before_hp);
        CHECK(fake::fields==2&&fake::actions==1); // real useful service, no per-action recompute
    }
    reset();{Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(fake::fields==1&&fake::actions==0&&fake::priorities==1&&fake::recoveries==0);
        c.next();TurnBudget next_budget{fake::round,c.ledger};
        float before=0;for(const auto& camp:fake::camps())before+=camp.hp;
        runtime.play(c.w,c.memory,next_budget,recovery,c.turn,stats);
        float after=0;for(const auto& camp:fake::camps())after+=camp.hp;
        CHECK(fake::fields==2&&fake::priorities==1&&fake::recoveries==0);
        CHECK(c.ledger.basics==2&&c.ledger.casts==1&&fake::actions==3&&before-after==200);
        CHECK(c.ledger.pending.after_observed&&c.ledger.open&&c.memory.state==State::capture);
    }
    reset(1);{
        fake::camps()[0].type=camp_type::wolf;fake::camps()[0].strength=1000;fake::camps()[0].hp=300;
        Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        c.next();TurnBudget next_budget{fake::round,c.ledger};runtime.play(c.w,c.memory,next_budget,recovery,c.turn,stats);
        CHECK(fake::fields==2&&fake::actions==0); // asleep group cannot safely be woken
        c.next();TurnBudget unchanged{fake::round,c.ledger};runtime.play(c.w,c.memory,unchanged,recovery,c.turn,stats);
        CHECK(fake::actions==0); // changed round alone does not reopen useful service
        fake::camps()[0].strength=0;c.next();TurnBudget cleared{fake::round,c.ledger};
        runtime.play(c.w,c.memory,cleared,recovery,c.turn,stats);
        CHECK(fake::actions>0&&fake::camps()[0].hp<300); // fresh clearance reopens the failed role
    }
    for(auto channel:{4u,4096u,2u}) {
        reset();Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;fake::flags|=channel;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(fake::priorities==0&&fake::actions==0&&fake::fields==0&&fake::ward_queries==0);
        CHECK(fake::recoveries==(channel==2u?1:0)); // recall uses reviewed recovery owner, submit/teleport stay protected
    }
    reset();{Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;fake::flags=0;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(c.memory.life==1&&!c.memory.was_alive&&c.memory.state==State::dead&&fake::actions==0&&fake::priorities==0);
        c.next();TurnBudget next_budget{fake::round,c.ledger};runtime.play(c.w,c.memory,next_budget,recovery,c.turn,stats);
        CHECK(c.memory.life==1&&fake::fields==0&&fake::recoveries==0);
    }
    for(bool home:{false,true}) {
        reset();Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;fake::health=100;
        if(home)fake::origin={0,0};TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(fake::recoveries==(home?0:1)&&fake::actions==0&&fake::priorities==0&&fake::fields==0);
        if(home)CHECK(c.memory.state==State::healing);
    }
    reset();{Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;fake::gold=400;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(fake::recoveries==0&&fake::fields==1&&fake::priorities==1); // no compulsory 300-gold recall
    }
    reset();{Context c;EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;fake::roll_priority=true;bool caught=false;
        TurnBudget budget{fake::round,c.ledger};try{runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);}catch(TurnExpired){caught=true;}
        CHECK(caught&&fake::priorities==1&&!c.ledger.open&&fake::actions==0);
        fake::roll_priority=false;c.next();TurnBudget next_budget{fake::round,c.ledger};runtime.play(c.w,c.memory,next_budget,recovery,c.turn,stats);
        CHECK(fake::priorities==1&&fake::fields==1); // accepted config return survives rollover
    }
#ifdef LP_TEST_REAL_BANK
    reset(1);{
        fake::camps()[0].pos={12,12};fake::origin={6,7};fake::gems=20;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto before=c.read();CHECK(choose_bank(before,task,c.ledger).stop==BankStop::approach);
        ServiceChoice motion;motion.stop=ServiceStop::action;
        motion.request={before.economy.self.epoch,action::Op::step,{-1,7,7,-1,0,0,119},true};
        auto moved=perform_service(before,motion,c.turn);CHECK(moved.accepted());
        auto after=c.read();CHECK(after.economy.self.pos==Point{7,7}&&c.ledger.observe(moved.event,c.turn.epoch()));
        auto choice=choose_bank(after,task,c.ledger);CHECK(choice.stop==BankStop::action&&choice.request.op==action::Op::submit);
        auto issued=perform_bank(after,choice,c.turn);auto started=c.read();
        CHECK(c.ledger.observe(issued.event,c.turn.epoch(),started.economy.self.channel==Channel::submit));
        CHECK(c.ledger.steps==1&&c.ledger.at(action::Op::submit).accepted==1&&fake::actions==2);
    }
    reset(1);{
        fake::camps()[0].pos={12,12};fake::gems=1000;fake::carried_locks=1;
        Context c;c.w.altars={fake::bank_altar};EconomicRuntime runtime;RecoveryRuntime recovery;Telemetry stats;
        TurnBudget budget{fake::round,c.ledger};runtime.play(c.w,c.memory,budget,recovery,c.turn,stats);
        CHECK(fake::fields==0&&fake::lock_uses==1&&fake::submissions==1&&fake::actions==2);
        CHECK(c.ledger.submit_attempted&&c.ledger.at(action::Op::submit).accepted==1&&c.memory.state==State::bank);
    }
    for(bool enemy:{false,true}) {
        reset(1);fake::camps()[0].pos={12,12};fake::gems=20;fake::carried_locks=1;
        fake::lock_hits=enemy?2:0;fake::enemy_lock=enemy;Context c;c.w.altars={fake::bank_altar};
        Task task{{0,0,7*16+7,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        const std::vector<action::Op> expected=enemy?
            std::vector<action::Op>{action::Op::lock_basic,action::Op::reset,action::Op::lock_basic,action::Op::lock_use,action::Op::submit}:
            std::vector<action::Op>{action::Op::lock_use,action::Op::submit};
        for(auto op:expected) {
            auto s=c.read();CHECK(bank_position_safe(s));auto choice=choose_bank(s,task,c.ledger);
            if(choice.stop!=BankStop::action||choice.request.op!=op)
                std::cerr<<"bank sequence enemy="<<enemy<<" expected="<<int(op)<<" stop="<<int(choice.stop)
                         <<" op="<<int(choice.request.op)<<" basics="<<c.ledger.basics<<" casts="<<c.ledger.casts
                         <<" lock_hits="<<fake::lock_hits<<" cooldown="<<fake::cooldown<<'\n';
            CHECK(choice.stop==BankStop::action&&choice.request.op==op);
            auto issued=perform_bank(s,choice,c.turn);CHECK(issued.event!=0);
            auto after=c.read();const bool started=after.economy.self.channel==Channel::submit;
            CHECK(c.ledger.observe(issued.event,c.turn.epoch(),started,false,op==action::Op::lock_basic));
            CHECK(op==action::Op::submit?started:issued.accepted());
        }
        CHECK(fake::submissions==1&&fake::lock_uses==1&&fake::carried_locks==0);
        CHECK(fake::lock_attacks==(enemy?2:0)&&c.ledger.basics==(enemy?2u:0u)&&c.ledger.casts==(enemy?1u:0u));
        CHECK(choose_bank(c.read(),task,c.ledger).stop==BankStop::channel);
    }
    for(bool normal_start:{false,true}) {
        reset(1);fake::camps()[0].pos={12,12};fake::gems=20;fake::submit_starts=normal_start;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();Champion ally;ally.key=2;ally.alive=ally.channel=true;ally.timer=1;ally.pos={7,8};s.allies.push_back(ally);
        auto choice=choose_bank(s,task,c.ledger);CHECK(choice.stop==BankStop::action&&choice.request.op==action::Op::submit);
        auto issued=perform_bank(s,choice,c.turn);CHECK(issued.stop==action::Stop::acknowledged);
        auto after=c.read();CHECK(c.ledger.observe(issued.event,c.turn.epoch(),normal_start));
        CHECK(c.ledger.at(action::Op::submit).accepted==(normal_start?1u:0u));
        CHECK(normal_start?c.ledger.open:!c.ledger.open); // void return without a channel seals continuation
        CHECK(fake::submissions==1); // an allied channel did not force courtesy-wait
    }
    for(int code:{45,125}) {
        reset(1);fake::camps()[0].pos={12,12};fake::gems=20;fake::submit_error=code;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();auto choice=choose_bank(s,task,c.ledger);bool caught=false;
        try{perform_bank(s,choice,c.turn);}catch(cambc::error){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::submissions==1&&c.ledger.submit_attempted);
    }
    reset(1);{
        fake::camps()[0].pos={12,12};fake::gems=20;fake::carried_locks=1;fake::lock_result=false;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();auto choice=choose_bank(s,task,c.ledger);auto issued=perform_bank(s,choice,c.turn);
        CHECK(issued.stop==action::Stop::refused&&fake::lock_uses==1&&fake::carried_locks==1);
        auto after=c.read();CHECK(c.ledger.observe(issued.event,c.turn.epoch()));
        choice=choose_bank(after,task,c.ledger);CHECK(choice.stop!=BankStop::action||choice.request.op!=action::Op::lock_use);
    }
    reset(1);{
        fake::camps()[0].pos={12,12};fake::gems=20;fake::roll_submit=true;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();auto choice=choose_bank(s,task,c.ledger);auto issued=perform_bank(s,choice,c.turn);
        CHECK(issued.stop==action::Stop::acknowledged&&!c.ledger.open&&fake::submissions==1);
    }
    for(bool rollover:{false,true}) {
        reset(1);fake::camps()[0].pos={12,12};fake::gems=20;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();auto choice=choose_bank(s,task,c.ledger);fake::roll_locks=rollover;fake::error_locks=!rollover;
        bool caught=false;try{perform_bank(s,choice,c.turn);}catch(TurnExpired){caught=true;}catch(cambc::error){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::submissions==0&&fake::actions==0);
    }
    reset(1);{
        fake::camps()[0].pos={12,12};fake::gems=20;
        Context c;c.w.altars={fake::bank_altar};Task task{{0,0,119,Purpose::convert,Role::carrier},Phase::access,{7,7},Evidence::ready,Reason::none,true};
        auto s=c.read();s.visible[s.local({8,7})]=0;CHECK(choose_bank(s,task,c.ledger).stop==BankStop::hidden);
        s.visible[s.local({8,7})]=1;s.members[0].passive=false;s.members[0].known=false;s.members[0].pos={7,8};s.members[0].range=1;
        CHECK(!bank_position_safe(s)&&choose_bank(s,task,c.ledger).stop==BankStop::unsafe);
        s.members[0].known=true;s.members[0].awake=false;CHECK(bank_position_safe(s));
        s.members[0].awake=true;s.members[0].strength=100;CHECK(!bank_position_safe(s));
    }
#endif
    std::cout<<"PASS: "<<checks<<" actual-SDK economic capture/field/owner/route/service/dispatch assertions\n";
#ifndef LP_TEST_REAL_BANK
    std::cout<<"LIMIT: bank test double (Pi module pending), recovery takeover test double; no full game/fuel claim\n";
#endif
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
#include "capture_sdk_unused.inc"
