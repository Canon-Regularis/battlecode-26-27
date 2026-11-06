// Actual production transaction + SDK wrappers; only engine imports are mocked.
#include "live_turn.h"
#include <iostream>
#include <stdexcept>
using namespace lp;
namespace fake {
int round=10, actions=0, state_reads=0;
std::uint32_t state=1|8|16|2048;
std::uint8_t restrictions=0;
std::uint64_t fuel=100000;
bool move_result=true,roll_action=false,roll_read=false,error_action=false;
unsigned revision=1;
void committed(){++actions;if(roll_action)++round;}
}
namespace cambc::detail {extern "C" {
int32_t sdk_bc_get_last_error(char*,uint32_t){return 0;}
int32_t sdk_get_settings(game_settings* p){*p={};return 0;}
int32_t sdk_shared_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_bc_metadata(metadata* p){*p={45,30,6,4,6,1536,3072};return 0;}
int32_t sdk_bc_map_symmetry(int32_t* p){*p=0;return 0;}
int32_t sdk_my_champion(){return 1;}
int32_t sdk_my_team(){return 0;}
int32_t sdk_item_info(uint32_t,item_info* p){*p={};return 0;}
int32_t sdk_consumable_info(uint32_t,consumable_info* p){*p={};return 0;}
int32_t sdk_champion_design(int32_t,champion_design* p){*p={};return 0;}
int32_t sdk_draft_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_read_draft_memory(int32_t,void*,uint32_t){return 0;}
int32_t sdk_spawn_region(int32_t,aabb* p){*p={};return 0;}
int32_t sdk_Bitboard_Zero(uint64_t* p){*p=0;return 0;}
int32_t sdk_Bitboard_Set(uint64_t*,int32_t,int32_t,int32_t){return 0;}
int32_t sdk_bc_map_mask(int32_t,uint64_t* p){*p=0;return 0;}
int32_t sdk_camp_buffs(uint32_t,camp_buff_data*,uint32_t,uint32_t* n){*n=0;return 0;}
int32_t sdk_champion_identity(uint32_t,champion_identity* p){*p={};return 0;}
int32_t sdk_champion_ability_props(uint32_t,uint32_t,ability_props* p){*p={};p->kind=uint32_t(ability_kind::shield);return 0;}
int32_t sdk_champion(uint32_t,champion_info* p){*p={};p->state=fake::state;p->health=100;p->max_health=100;
    ++fake::state_reads;if(fake::roll_read)++fake::round;return 0;}
int32_t sdk_champion_restrictions(uint32_t,uint8_t* p){*p=fake::restrictions;return 0;}
int32_t sdk_champion_buff_data(uint32_t,buff_data*,uint32_t,uint32_t* n){*n=0;return 0;}
int32_t sdk_bc_round_number(uint32_t* p){*p=fake::round;return 0;}
int64_t sdk_fuel_remaining(){return int64_t(fake::fuel);}
int32_t sdk_move_to(int32_t,int32_t,int32_t* result){fake::committed();*result=fake::move_result;
    if(fake::error_action)return int32_t(error_code::api_not_found);return 0;}
int32_t sdk_cast(uint32_t,uint32_t,uint32_t,int32_t,int32_t,int32_t* result){fake::committed();*result=1;return 0;}
int32_t sdk_attack(uint32_t,uint32_t){fake::committed();return 0;}
int32_t sdk_recall(){fake::committed();return 0;}
int32_t sdk_cancel_channel(){fake::committed();return 0;}
int32_t sdk_submit_gems(int32_t,int32_t){fake::committed();return 0;}
}}
namespace lp {
unsigned observation_version(){return fake::revision;}
void invalidate_observations(){++fake::revision;}
}
int checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
struct Context {
    action::Ledger ledger;Memory memory;LiveTurn turn{ledger,memory,1};
    Context(){CHECK(ledger.begin(turn.epoch(),fake::fuel));CHECK(ledger.handoff(action::Owner::service,turn.epoch()));}
    action::Result step(){return turn.perform({turn.epoch(),action::Op::step,{},true},[]{return true;},[]{return self().move_absolute({3,4});});}
    action::Result shield(){return turn.perform({turn.epoch(),action::Op::shield,{},false},[]{return true;},[]{return self().abilities()[0].use();});}
    void observe(action::Result r){CHECK(ledger.observe(r.event,turn.epoch()));}
};
void reset(){++fake::round;fake::actions=0;fake::state_reads=0;fake::state=1|8|16|2048;
    fake::restrictions=0;fake::fuel=100000;fake::move_result=true;
    fake::roll_action=fake::roll_read=fake::error_action=false;}
int main(){try{
    reset();{Context c;auto r=c.step();CHECK(r.accepted());c.observe(r);
        CHECK(c.ledger.handoff(action::Owner::bank,c.turn.epoch()));
        CHECK(c.step().stop==action::Stop::denied&&fake::actions==1);
        auto shield=c.shield();CHECK(shield.accepted());c.observe(shield);
        CHECK(c.ledger.handoff(action::Owner::recovery,c.turn.epoch()));
        CHECK(c.shield().stop==action::Stop::denied&&c.ledger.casts==1&&fake::actions==2);
        CHECK(c.ledger.queries_issued==c.ledger.queries_completed&&c.ledger.queries_issued>0);}
    for(auto flag:{4u,32u,4096u}) { // completed turn, own submission, teleport
        reset();Context c;fake::state|=flag;
        CHECK(c.step().stop==action::Stop::denied&&fake::actions==0);
    }
    reset();{Context c;fake::restrictions=1;
        CHECK(c.step().stop==action::Stop::denied&&fake::actions==0&&c.ledger.step_attempted);
        CHECK(c.ledger.service_rejections==0);}
    reset();{Context c;fake::move_result=false;auto r=c.step();CHECK(r.stop==action::Stop::refused);
        CHECK(fake::actions==1&&c.ledger.service_rejections==1&&c.ledger.steps==0);
        c.observe(r);CHECK(c.ledger.handoff(action::Owner::recovery,c.turn.epoch()));
        CHECK(c.step().stop==action::Stop::denied);}
    reset();{Context c;fake::roll_action=true;auto r=c.step();
        CHECK(r.accepted()&&!c.ledger.open&&c.ledger.steps==1&&fake::actions==1);
        CHECK(!c.ledger.observe(r.event,c.turn.epoch()));}
    reset();{Context c;fake::roll_read=true;bool expired=false;
        try{c.step();}catch(TurnExpired){expired=true;}
        CHECK(expired&&!c.ledger.open&&fake::actions==0&&c.ledger.service_rejections==0);}
    reset();{Context c;fake::error_action=true;bool error=false;
        try{c.step();}catch(cambc::error){error=true;}
        CHECK(error&&!c.ledger.open&&fake::actions==1&&c.ledger.at(action::Op::step).uncertain==1);}
    reset();{Context c;fake::fuel=100;bool deferred=false;
        try{c.step();}catch(TurnDeferred){deferred=true;}
        CHECK(deferred&&fake::actions==0&&!c.ledger.step_attempted&&c.ledger.service_rejections==0);}
    std::cout<<"PASS: "<<checks<<" actual-SDK shared-transaction assertions\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
