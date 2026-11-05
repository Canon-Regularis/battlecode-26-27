// Actual SDK wrappers + explicit scripted native host, not an engine simulation.
#include "combat.h"
#include <cassert>
#include <cmath>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <tuple>
using namespace cambc;
using namespace lp;
namespace {
struct CampData {vec2 pos;float hp;bool visible=true;bool tile_visible=true;};
struct Host {
    int round=1013, fuel=100000, stage=0, dash=5, reset=0;
    int moves=0, refreshes=0, observations=0, invalidations=0, resets=0, dashes=0;
    int geometry=0, hidden_queries=0, action_errors=0, death_error=0;
    int reset_kind=1;bool reset_self=true, movement_exclusive=false;
    bool move=true, attack=true, cast=true, alive=true, channel=false;
    bool foe_alive=true;
    bool spend_move=true, reset_success=true, restore_attack=true;
    unsigned restrictions=0;
    champion_type name=champion_type::vesper_vale;
    vec2 pos{16,0}; float strength=145, hp=980, max_hp=1700;
    std::map<int,CampData> camps;
    std::vector<std::string> actions, queries;
    std::function<void(const std::string&)> hook;
} h;
int assertions=0, scenarios=0;
void check(bool ok) {++assertions;if(!ok)throw std::runtime_error("scenario " + std::to_string(scenarios) + ", assertion " + std::to_string(assertions));}
void event(std::string tag) {h.queries.push_back(tag);if(h.hook)h.hook(tag);}
constexpr int words=64;
void setbit(std::uint64_t* b,int x,int y) {if(x>=0&&x<64&&y>=0&&y<64)b[y]|=std::uint64_t(1)<<x;}
bool bit(const std::uint64_t* b,int x,int y) {return x>=0&&x<64&&y>=0&&y<64&&((b[y]>>x)&1);}
}
namespace cambc::detail {extern "C" {
std::int32_t sdk_get_settings(game_settings* o) {*o={};return 0;}
std::int32_t sdk_bc_metadata(metadata* o) {*o={64,64,8,8,8,512,8192};return 0;}
std::int32_t sdk_my_team() {return 0;}
std::int32_t sdk_my_champion() {return 6;} // Rebuild cached_self per fixture.
std::int32_t sdk_bc_map_symmetry(std::int32_t* o) {*o=0;return 0;}
std::int32_t sdk_bc_map_mask(std::int32_t,std::uint64_t* o) {std::fill_n(o,words,0);return 0;}
std::int32_t sdk_spawn_region(std::int32_t,aabb* o) {*o={0,0,0,0};return 0;}
std::int32_t sdk_item_info(std::uint32_t,item_info* o) {*o={};return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* o) {*o={};return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* o) {std::fill_n(o,words,0);return 0;}
std::int32_t sdk_Bitboard_ImportRawBuffer(std::uint64_t* o,const std::uint8_t* in,std::size_t n) {std::memcpy(o,in,n);return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t* o,int x,int y,int v) {if(v)setbit(o,x,y);else o[y]&=~(std::uint64_t(1)<<x);return 0;}
std::int32_t sdk_Bitboard_Test(const std::uint64_t* b,int x,int y,int* o) {*o=bit(b,x,y);event("range");return 0;}
std::int32_t sdk_Bitboard_DrawChebyshev(std::uint64_t* o,int x,int y,float r) {
    for(int j=0;j<64;++j)for(int i=0;i<64;++i)if(std::max(std::abs(x-i),std::abs(y-j))<=r)setbit(o,i,j);
    if(h.stage==1&&x==h.pos.x&&y==h.pos.y&&r==3)++h.geometry;
    event("geometry");return 0;
}
std::int32_t sdk_Bitboard_Union(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* o) {for(int i=0;i<words;++i)o[i]=a[i]|b[i];return 0;}
std::int32_t sdk_Bitboard_Intersect(const std::uint64_t* a,const std::uint64_t* b,std::uint64_t* o) {for(int i=0;i<words;++i)o[i]=a[i]&b[i];return 0;}
std::int32_t sdk_Bitboard_Not(const std::uint64_t* a,std::uint64_t* o) {for(int i=0;i<words;++i)o[i]=~a[i];return 0;}
std::int32_t sdk_Bitboard_IsZero(const std::uint64_t* a,int* o) {*o=std::all_of(a,a+words,[](auto x){return x==0;});return 0;}
std::int32_t sdk_Bitboard_NumSetBits(const std::uint64_t* a,std::uint32_t* o) {*o=0;for(int i=0;i<words;++i)*o+=__builtin_popcountll(a[i]);return 0;}
std::int32_t sdk_Bitboard_GetSetBits(const std::uint64_t* a,void* dest,std::size_t n,std::uint32_t* count) {auto* o=static_cast<position*>(dest);*count=0;for(int y=0;y<64;++y)for(int x=0;x<64;++x)if(bit(a,x,y)){assert(*count<n);o[(*count)++]={x,y};}return 0;}
std::int32_t sdk_bc_round_number(std::uint32_t* o) {*o=h.round;return 0;}
std::int64_t sdk_fuel_remaining() {return h.fuel;}
std::int32_t sdk_champion_identity(std::uint32_t,champion_identity* o) {*o={};o->type=int(h.name);event("identity");return 0;}
std::int32_t sdk_champion(std::uint32_t id,champion_info* o) {
    if(id==7&&!h.foe_alive)return int(error_code::api_not_in_vision);
    *o={};o->x=h.pos.x;o->y=h.pos.y;o->health=h.hp;o->max_health=h.max_hp;o->strength=h.strength;o->attack_range=h.name==champion_type::vendetta?1:3;
    o->state=(h.alive?champion_state::alive.bits():0)|(h.move?champion_state::can_move.bits():0)|
        (h.attack?champion_state::can_attack.bits():0)|(h.cast?champion_state::can_cast.bits():0)|
        (h.channel?champion_state::recalling.bits():0);
    event("actor");return 0;
}
std::int32_t sdk_champion_restrictions(std::uint32_t,std::uint8_t* o) {*o=h.restrictions;event("restrictions");return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t,std::uint32_t slot,ability_props* o) {
    *o={};o->kind=slot==0?h.reset_kind:6;o->cooldown=8;o->targets=slot==0?(h.reset_self?ability_target_mask::self.bits():0):ability_target_mask::ground.bits();
    if(slot==0&&h.movement_exclusive)o->attributes=ability_attribute_exclusive_with_movement;
    o->payload.dash.range=2;return 0;
}
std::int32_t sdk_champion_cooldown(std::uint32_t,std::uint32_t slot,int* o) {*o=slot==0?h.reset:h.dash;event(slot==0?"cooldown":"dash_cooldown");return 0;}
std::int32_t sdk_camp(std::uint32_t id,camp_state* o) {
    auto& c=h.camps.at(id);
    if(!c.visible||!c.tile_visible){event("unavailable:"+std::to_string(id));return int(error_code::api_not_in_vision);}
    if(c.hp<=0){event("unavailable:"+std::to_string(id));return int(error_code::api_not_found);}
    *o={};o->x=c.pos.x;o->y=c.pos.y;o->health=c.hp;o->max_health=2400;o->strength=60;
    event("camp:"+std::to_string(id));return 0;
}
std::int32_t sdk_camp_state(std::uint32_t id,std::uint32_t* o) {
    auto& c=h.camps.at(id);
    if(h.stage>0&&h.death_error)return h.death_error;
    if(!c.tile_visible||(c.hp>0&&!c.visible)){++h.hidden_queries;throw std::runtime_error("hidden live state queried");}
    *o=c.hp<=0?0:1;event("life:"+std::to_string(id));return 0;
}
std::int32_t sdk_is_visible(int x,int y,int* o) {*o=1;for(auto& [id,c]:h.camps)if(c.pos==vec2{x,y})*o=c.tile_visible;event("vision");return 0;}
std::int32_t sdk_attack(std::uint32_t kind,std::uint32_t target) {
    assert(kind==std::uint32_t(entity_kind::camp)||kind==std::uint32_t(entity_kind::champion));
    if(h.stage>0&&((h.round!=1013&&h.round!=1044)||h.fuel<=5000))throw std::runtime_error("stale attack");
    assert(h.attack);h.actions.push_back("basic:"+std::to_string(target));
    h.attack=false;if(h.spend_move)h.move=false;
    if(kind==std::uint32_t(entity_kind::champion))h.foe_alive=false;
    if(kind==std::uint32_t(entity_kind::camp))h.camps.at(target).hp=std::max(0.f,h.camps.at(target).hp-h.strength);
    h.stage=h.stage==0?1:3;event("basic");return 0;
}
std::int32_t sdk_cast(std::uint32_t slot,std::uint32_t,std::uint32_t,int,int,int* o) {
    if((h.round!=1013&&h.round!=1044)||h.fuel<=5000)throw std::runtime_error("stale reset");
    h.actions.push_back(slot==0?"reset":"dash");if(slot==0)++h.resets;else ++h.dashes;
    *o=h.reset_success;
    if(*o){h.cast=false;h.reset=8;if(h.restore_attack)h.attack=true;h.stage=2;}
    event("reset");return 0;
}
std::int32_t sdk_bc_get_last_error(char* o,std::uint32_t n) {if(n)*o=0;return 0;}
std::int32_t sdk_camp_design(std::int32_t,camp_design* o) {*o={};o->base_stats.base_attack_range=4;return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* o) {*o={};return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* o) {*o=0;return 0;}
std::int32_t sdk_read_draft_memory(std::int32_t,void*,std::uint32_t) {std::abort();}
std::int32_t sdk_shared_memory_size(std::uint32_t* o) {*o=0;return 0;}
// Non-reset spell paths compile but these fixtures never select a damaging/healing spell.
std::int32_t sdk_champion_ability_damage(std::uint32_t,std::uint32_t,float*) {std::abort();}
std::int32_t sdk_champion_ability_damage_against(std::uint32_t,std::uint32_t,std::uint32_t,float*) {std::abort();}
std::int32_t sdk_champion_ability_heal_against(std::uint32_t,std::uint32_t,std::uint32_t,float*) {std::abort();}
}}
namespace lp {
Snapshot snapshot;
const Snapshot& observe() {++h.observations;return snapshot;}
void invalidate_observations() {++h.invalidations;}
float incoming_at(vec2,const std::vector<champion>&) {return 0;}
void World::refresh(const Snapshot&,Memory&) {++h.refreshes;}
bitboard camp_goals(const Objective&,const Snapshot&) {return {};}
RouteStatus move_to(bitboard,bool,TurnBudget&,Memory&,bool) {++h.moves;return RouteStatus::wait;}
}
// Only the caller's unrelated dependencies are substituted. Its entire returned
// body is extracted by run_kill_reset.py. No predicates or combat bodies copied.
class Bot {
public:
    World world;Memory memory;
    struct {int moves=0,defers=0;} stats;
    void abandon(int) {memory.task=-1;}
    Facts facts(const Snapshot&,bool) {return {};}
    void camp_action(TurnBudget&);
};
#include "../src/combat.cpp"
#include ".kill-reset-build/camp_action.inc"
namespace {
camp wrapper(int id,int group) {return detail::handle_access::make_camp(handle_camp_t(id),handle_camp_group_t(group),camp_type::elk,h.camps.at(id).pos);}
Bot fixture(bool second=false) {
    ++scenarios;h=Host{};
    if(second){h.round=1044;h.pos={32,5};h.strength=175;h.hp=h.max_hp=2200;}
    h.camps=second?std::map<int,CampData>{{90,{{32,2},120}},{34,{{31,2},2400}}}:
        std::map<int,CampData>{{64,{{13,1},120}},{54,{{13,3},1847.52880859375f}},{48,{{13,2},2400}},
            {40,{{19,1},348.0723571777344f}},{42,{{18,1},1061.63134765625f}}};
    std::vector<int> members=second?std::vector<int>{34,36,38,90}:std::vector<int>{48,50,52,54,62,64,97,99,101};
    int group=second?12:16;std::vector<camp> camps;
    for(int id:members){if(!h.camps.count(id))h.camps[id]={{0,0},2400,false,false};camps.push_back(wrapper(id,group));}
    detail::cached_self=detail::handle_access::make_champion(handle_champion_t(6));
    // require_self uses the cached authenticated identity, separate from cached_self.
    Bot b;b.memory.task=0;
    b.world.camps.push_back(Objective{detail::handle_access::make_camp_group(handle_camp_group_t(group),0,0,0,std::move(camps)),{}, {}, {}});
    b.world.camps[0].lifecycle=1;
    snapshot=Snapshot{};snapshot.round=h.round;snapshot.pos=h.pos;snapshot.alive=true;
    h.queries.clear();return b;
}
void run(Bot& b) {TurnBudget budget{h.round};b.camp_action(budget);check(h.hidden_queries==0);check(h.resets<=1);check(h.dashes==0);}
void terminal() {check(h.moves==0);check(h.refreshes==0);check(h.observations==2);}
void actions(std::initializer_list<std::string> expected) {check(h.actions==std::vector<std::string>(expected));}
}
int main() {
    try {
        auto b=fixture();run(b);actions({"basic:64","reset","basic:54"});terminal();check(h.geometry==1);check(h.camps.at(40).hp==348.0723571777344f);check(h.camps.at(42).hp==1061.63134765625f);
        b=fixture(true);run(b);actions({"basic:90","reset","basic:34"});terminal();check(h.geometry==1);
        // Stable ties follow cached membership (48 precedes 54).
        b=fixture();h.camps.at(48).hp=h.camps.at(54).hp;run(b);actions({"basic:64","reset","basic:48"});terminal();
        // The unmodified surviving-target scheduler still resets onto that target.
        b=fixture();h.camps.at(64).hp=300;run(b);actions({"basic:64","reset","basic:64"});terminal();check(h.camps.at(54).hp==1847.52880859375f);
        for(int mode=0;mode<3;++mode) {
            b=fixture();
            for(int id:{48,54}) {if(mode==0)h.camps.at(id).hp=0;if(mode==1)h.camps.at(id).visible=false;if(mode==2)h.camps.at(id).pos={50,50};}
            run(b);actions({"basic:64"});terminal();
        }
        // No first target, no first basic, invalid task, and travel.
        b=fixture();for(auto& [id,c]:h.camps)c.visible=false;run(b);actions({});
        b=fixture();h.attack=false;run(b);actions({});
        b=fixture();b.memory.task=-1;run(b);actions({});check(h.observations==0);
        b=fixture();check(!fight(b.world,999));actions({});
        b=fixture();check(!fight(b.world,0,true));actions({});
        // Enemy priority: no camp continuation, with or without travel.
        for(bool travel:{false,true}) {
            b=fixture();snapshot.foes.push_back(detail::handle_access::make_champion(handle_champion_t(7)));
            check(fight(b.world,0,travel));actions({"basic:7"});check(h.resets==0);
        }
        // Losing the selected sibling never triggers a second retarget.
        for(bool after_reset:{false,true}) {
            b=fixture();int reads=0;
            h.hook=[&](const std::string& tag){
                if((after_reset&&tag=="reset")||(!after_reset&&h.stage==1&&tag=="camp:54"&&++reads==3))h.camps.at(54).visible=false;
            };
            run(b);if(after_reset)actions({"basic:64","reset"});else actions({"basic:64"});terminal();
        }
        // Selected target death/range loss and actor changes after reset prevent
        // the extra basic without retrying reset or choosing the remaining sibling.
        for(int mode=0;mode<6;++mode) {
            b=fixture();h.hook=[mode](const std::string& tag){if(tag!="reset")return;
                if(mode==0)h.camps.at(54).hp=0;if(mode==1)h.camps.at(54).pos={50,50};
                if(mode==2)h.channel=true;if(mode==3)h.alive=false;
                if(mode==4)h.restrictions=buff_restrictions::attack.bits();if(mode==5)h.restrictions=buff_restrictions::cast.bits();
            };
            run(b);actions({"basic:64","reset"});terminal();
        }
        // A hidden live target is never inferred dead. Killed but unobserved also declines.
        for(bool live:{false,true}) {
            b=fixture();if(live)h.camps.at(64).hp=300;
            h.hook=[](const std::string& tag){if(tag=="basic"){h.camps.at(64).visible=false;h.camps.at(64).tile_visible=false;}};
            run(b);actions({"basic:64"});terminal();
        }
        // Expected visibility-query failures decline; unrelated SDK errors propagate.
        for(auto code:{error_code::api_not_in_vision,error_code::api_not_found,error_code::api_value_out_of_range}) {
            b=fixture();h.death_error=int(code);bool threw=false;
            try {run(b);}catch(const error& e){threw=true;check(e.code()==code);}
            check(threw==(code==error_code::api_value_out_of_range));actions({"basic:64"});
        }
        // Visibility-like codes from self/metadata or actions are unrelated errors.
        for(const std::string tag:{"identity","restrictions","reset"}) {
            b=fixture();h.hook=[tag](const std::string& q){if(h.stage>0&&q==tag)throw error(error_code::api_not_found,"injected unrelated error");};
            bool threw=false;try {run(b);}catch(const error& e){threw=true;check(e.code()==error_code::api_not_found);}check(threw);
        }
        // Boundary changes after the first basic isolate continuation legality.
        for(int mode=0;mode<9;++mode) {
            b=fixture();h.hook=[mode](const std::string& tag){if(tag!="basic")return;
                if(mode==0)h.reset=1;if(mode==1)h.cast=false;if(mode==2)h.channel=true;
                if(mode==3)h.restrictions=buff_restrictions::cast.bits();if(mode==4)h.restrictions=buff_restrictions::attack.bits();
                if(mode==5)h.alive=false;if(mode==6)h.attack=true;if(mode==7)h.name=champion_type::ren;
                if(mode==8)h.move=true;
            };
            run(b);check(h.resets==0);check(h.actions.front()=="basic:64");if(mode!=8)terminal();
        }
        // Metadata and walking compatibility are required in addition to cooldown zero.
        for(int mode=0;mode<3;++mode) {
            b=fixture();if(mode==0)h.reset_kind=0;if(mode==1)h.reset_self=false;if(mode==2)h.movement_exclusive=true;
            detail::cached_self=detail::handle_access::make_champion(handle_champion_t(6));
            run(b);actions({"basic:64"});terminal();
        }
        b=fixture();h.channel=true;run(b);actions({});
        // Dash readiness is not a competing gate when movement is spent.
        for(int dash:{5,0}) {b=fixture();h.dash=dash;run(b);actions({"basic:64","reset","basic:54"});terminal();}
        b=fixture();h.spend_move=false;h.dash=5;run(b);check(h.resets==0);check(h.moves==1);
        // Vendetta melee kill refresh remains outside this extension.
        b=fixture();h.name=champion_type::vendetta;h.spend_move=false;h.camps.at(64).pos={15,0};h.reset=h.dash=5;
        h.hook=[](const std::string& tag){if(tag=="basic")h.reset=h.dash=0;};
        {std::vector<camp> members;for(const auto& c:b.world.camps[0].group.camps())members.push_back(wrapper(int(static_cast<handle_camp_t>(c)),16));
        b.world.camps[0].group=detail::handle_access::make_camp_group(handle_camp_group_t(16),0,0,0,std::move(members));}
        run(b);actions({"basic:64"});check(h.move);check(h.resets==0);check(h.moves==1);check(h.dash==0);
        for(bool success:{false,true}) {
            b=fixture();h.reset_success=success;h.restore_attack=false;run(b);actions({"basic:64","reset"});terminal();check(h.resets==1);
        }
        // Exhaustive scripted invalidation at every host query in the bounded work,
        // including candidate scanning, validation, reset and final can_attack.
        b=fixture();run(b);auto trace=h.queries;
        auto first=std::find(trace.begin(),trace.end(),"identity");
        check(first!=trace.end());
        for(bool rollover:{false,true})for(std::size_t offset=std::distance(trace.begin(),first);offset<trace.size();++offset) {
            if(trace[offset]=="basic")continue; // The extra action has already happened.
            b=fixture();std::size_t index=0;bool invalidated=false;std::size_t actions_at_invalidation=0;
            h.hook=[&](const std::string&){
                if(index++==offset){invalidated=true;actions_at_invalidation=h.actions.size();if(rollover)++h.round;else h.fuel=5000;}
            };
            run(b);check(invalidated);check(h.actions.size()==actions_at_invalidation);terminal();
        }
        // Fuel must be strictly greater than reserve, with no tuned admission floor.
        b=fixture();h.fuel=5001;run(b);actions({"basic:64","reset","basic:54"});terminal();
        for(bool rollover:{false,true}) {
            b=fixture();h.hook=[rollover](const std::string& tag){if(tag=="basic"){if(rollover)++h.round;else h.fuel=5000;}};
            run(b);actions({"basic:64"});terminal();
        }
        // Complete scan has one HP read per visible, in-range candidate: live SDK
        // info queries are visibility, position, health; lifecycle is separate.
        b=fixture();int c48=0,c54=0,l48=0,l54=0;
        h.hook=[&](const std::string& tag){if(h.stage!=1)return;
            if(tag=="camp:48")++c48;if(tag=="camp:54")++c54;if(tag=="life:48")++l48;if(tag=="life:54")++l54;
        };
        run(b);check(c48==3&&l48==1);check(c54==5&&l54==2);check(h.geometry==1);terminal();
        for(int id:{50,52,62,97,99,101})check(std::count(h.queries.begin(),h.queries.end(),"unavailable:"+std::to_string(id))==2); // Original selection + one continuation pass.
        check(std::none_of(h.queries.begin(),h.queries.end(),[](const auto& tag){return tag=="camp:40"||tag=="camp:42";}));
        b=fixture();h.fuel=5000;check(!fight(b.world,0));actions({});
    } catch(const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;}
    std::cout<<scenarios<<" scenarios, "<<assertions<<" assertions passed\n";
}
