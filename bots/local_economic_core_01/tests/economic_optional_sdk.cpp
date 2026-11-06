// Actual production shopping/priority transaction with strict public-SDK host.
#include "economic_optional_sdk.h"
#include <iostream>
#include <stdexcept>
using namespace lp;
namespace fake {
int round=10,priority=0,buys=0,locks=0;unsigned revision=1;
uint32_t flags=0,gold=100000;uint64_t fuel=100000;
bool progress=true,roll=false,deny_items=false;
std::array<uint32_t,84> items{};
auto& ordered(){static std::vector<uint32_t> values;return values;}
}
namespace cambc::detail {extern "C" {
int32_t sdk_bc_get_last_error(char*,uint32_t){return 0;}
int32_t sdk_get_settings(game_settings* p){*p={};return 0;}
int32_t sdk_shared_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_bc_metadata(metadata* p){*p={16,16,2,2,2,256,512};return 0;}
int32_t sdk_bc_map_symmetry(int32_t* p){*p=0;return 0;}
int32_t sdk_my_champion(){return 1;}int32_t sdk_my_team(){return 0;}
int32_t sdk_draft_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_read_draft_memory(int32_t,void*,uint32_t){return 0;}
int32_t sdk_champion_identity(uint32_t,champion_identity* p){*p={0,int(champion_type::vesper_vale)};return 0;}
int32_t sdk_champion_design(int32_t,champion_design* p){*p={};return 0;}
int32_t sdk_champion_ability_props(uint32_t,uint32_t,ability_props* p){*p={};return 0;}
int32_t sdk_spawn_region(int32_t,aabb* p){*p={0,0,1,1};return 0;}
int32_t sdk_Bitboard_Zero(uint64_t* p){std::fill_n(p,32,0);return 0;}
int32_t sdk_Bitboard_Set(uint64_t* p,int32_t x,int32_t y,int32_t value){const int cell=y*16+x;const uint64_t mask=uint64_t(1)<<(cell%64);if(value)p[cell/64]|=mask;else p[cell/64]&=~mask;return 0;}
int32_t sdk_bc_map_mask(int32_t,uint64_t* p){return sdk_Bitboard_Zero(p);}
int32_t sdk_champion(uint32_t,champion_info* p){*p={};p->state=fake::flags;return 0;}
int32_t sdk_champion_gold(uint32_t,uint32_t* p){*p=fake::gold;return 0;}
int32_t sdk_champion_items(uint32_t,uint32_t* p){std::copy(fake::items.begin(),fake::items.end(),p);return 0;}
int32_t sdk_champion_consumables(uint32_t,uint32_t* p){std::fill_n(p,4,0);p[2]=fake::locks;return 0;}
int32_t sdk_item_info(uint32_t id,item_info* p){*p={};p->cost=10;p->purchasable=id%2==0;p->combine_count=id%2==0?5:0;p->result=id+1;return 0;}
int32_t sdk_consumable_info(uint32_t,consumable_info* p){*p={10,1};return 0;}
int32_t sdk_champion_can_shop(uint32_t,int32_t consumable,int32_t* p){*p=consumable||!fake::deny_items;return 0;}
int32_t sdk_buy_item(uint32_t id,uint32_t count) {
    if(count!=1||id%2||fake::gold<10)throw std::runtime_error("invalid buy");
    ++fake::buys;fake::ordered().push_back(id);fake::gold-=10;
    if(fake::progress&&++fake::items[id]>=5){fake::items[id]-=5;++fake::items[id+1];}
    if(fake::roll)++fake::round;return 0;
}
int32_t sdk_buy_consumable(uint32_t id){if(id!=2||fake::locks)throw std::runtime_error("invalid lock buy");++fake::locks;fake::gold-=10;return 0;}
int32_t sdk_set_priority(int32_t p){fake::priority=p;if(fake::roll)++fake::round;return 0;}
int32_t sdk_bc_round_number(uint32_t* p){*p=fake::round;return 0;}
int64_t sdk_fuel_remaining(){return int64_t(fake::fuel);}
}}
namespace lp {unsigned observation_version(){return fake::revision;}void invalidate_observations(){++fake::revision;}bitboard static_blocked(){throw std::runtime_error("unexpected ward work");}}
int checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
void reset(){++fake::round;fake::revision=1;fake::priority=fake::buys=fake::locks=0;fake::flags=0;fake::gold=100000;fake::items={};fake::ordered().clear();fake::progress=true;fake::roll=fake::deny_items=false;}
struct Context {Memory memory;action::Ledger ledger;LiveTurn turn{ledger,memory,1};Context(){CHECK(ledger.begin(turn.epoch(),fake::fuel));}};
int main(){try {
    reset();{Context c;bool initialized=false;CHECK(initialize_priority(2,c.turn,initialized)&&fake::priority==70&&initialized);CHECK(!initialize_priority(2,c.turn,initialized));
        CHECK(c.ledger.casts==0&&c.ledger.primitives==0&&c.ledger.at(action::Op::priority).accepted==1);}
    reset();{Context c;CHECK(natural_shop(c.memory,c.turn));CHECK(fake::buys==40&&fake::locks==1);
        CHECK(c.ledger.at(action::Op::item_buy).observed==40&&c.ledger.at(action::Op::consumable_buy).observed==1);
        CHECK(c.ledger.primitives==0&&c.ledger.casts==0&&c.ledger.basics==0);
        for(unsigned i=0;i<5;++i)CHECK(fake::ordered()[i]==uint32_t(item_type::treasure_shard_of_strength));
        for(unsigned i=5;i<10;++i)CHECK(fake::ordered()[i]==uint32_t(item_type::monster_shard_of_strength));
        CHECK(!natural_shop(c.memory,c.turn)&&fake::buys==40&&fake::locks==1); // same shared entry allowance
    }
    for(auto channel:{2u,4u,4096u}) {reset();Context c;fake::flags=1|channel;CHECK(!natural_shop(c.memory,c.turn)&&fake::buys==0&&fake::locks==0);}
    reset();{Context c;fake::gold=50;CHECK(natural_shop(c.memory,c.turn));CHECK(fake::buys==5&&fake::locks==0&&fake::gold==0);}
    reset();{Context c;fake::deny_items=true;CHECK(natural_shop(c.memory,c.turn)&&fake::buys==0&&fake::locks==1);}
    reset();{Context c;fake::progress=false;CHECK(natural_shop(c.memory,c.turn));CHECK(fake::buys==1&&c.memory.shop_phase==0);
        CHECK(!c.ledger.pending.in_flight&&c.ledger.at(action::Op::item_buy).observed==0&&c.ledger.at(action::Op::item_buy).accepted==1&&fake::locks==0);}
    reset();{Context c;fake::items[uint32_t(item_type::treasure_shard_of_strength)]=UINT32_MAX;
        CHECK(natural_shop(c.memory,c.turn)&&fake::buys==0&&fake::locks==1);}
    for(bool priority:{false,true}) {reset();Context c;fake::roll=true;bool caught=false,initialized=false;
        try{if(priority)initialize_priority(0,c.turn,initialized);else natural_shop(c.memory,c.turn);}catch(TurnExpired){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::buys==(priority?0:1));
        CHECK(initialized==priority);
        CHECK(c.ledger.pending.reduced&&!c.ledger.pending.in_flight&&!c.ledger.pending.after_observed);}
    reset();{Context c;economic::Scene s;s.economy.complete=true;s.economy.self.alive=true;s.economy.self.channel=economic::Channel::submit;
        CHECK(!economic_ward(s,{},c.turn));} // protected channel performs no ward query
    std::cout<<"PASS: "<<checks<<" actual-SDK optional entry/mutation assertions\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
#include "optional_sdk_unused.inc"
