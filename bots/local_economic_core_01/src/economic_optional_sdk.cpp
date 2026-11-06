#include "economic_optional_sdk.h"
#include <climits>
#include <optional>
namespace lp {
namespace {
bool protected_state(champion_state state) {
    return state.contains(champion_state::recalling)||state.contains(champion_state::submitting_gems)||
        state.contains(champion_state::teleporting);
}
bool acknowledge(action::Result result,LiveTurn& turn) {
    if(!result.accepted())return false;
    turn.check();return turn.ledger().observe(result.event,turn.epoch());
}
}
bool initialize_priority(int slot,LiveTurn& turn,bool& initialized) {
    if(initialized)return false;
    if(!turn.ledger().handoff(action::Owner::optional,turn.epoch()))return false;
    auto result=turn.perform({turn.epoch(),action::Op::priority,{}},[]{return true;},
        [&]{self().set_priority(80-slot*5);});
    // Save the known return before a freshness check can cross/throw. A
    // successful priority mutation must not be reissued on a later turn.
    initialized=result.accepted();
    return acknowledge(result,turn);
}
bool natural_shop(Memory& memory,LiveTurn& turn) {
    turn.check();auto& me=self();auto read=[&](auto f){return turn.read(f);};
    auto state=read([&]{return me.state();});if(protected_state(state))return false;
    bool alive=state.contains(champion_state::alive);
    if(read([&]{return me.gold_count();})<10)return false;
    const auto type=read([&]{return me.champion_name();});
    bool spawn=alive&&read([&]{return map::spawn_region(team::ally).is_set(me.position());});
    if(alive&&!spawn&&type!=champion_type::tavi)return false;
    if(!turn.ledger().handoff(action::Owner::optional,turn.epoch()))return false;
    bool changed=false;
    bool caster=type==champion_type::heart_of_ruin||type==champion_type::ren||type==champion_type::prism||
        type==champion_type::stellar||type==champion_type::willow||type==champion_type::tavi||type==champion_type::cassi;
    auto first=type==champion_type::vesper_vale?item_type::treasure_shard_of_strength:item_type::durability_shard_of_health;
    auto second=caster?item_type::monster_shard_of_focus:item_type::monster_shard_of_strength;
    // 40 accepted item operations + at most one phase normalization per buy.
    // The original 15000 guard is provisional until whole-WASM measurement.
    for(unsigned visit=0;visit<80&&turn.ledger().at(action::Op::item_buy).admitted<40&&fuel_remaining()>15000;++visit) {
        if(memory.shop_phase<0||memory.shop_phase==INT_MAX||memory.shop_target<0)break;
        auto item=memory.shop_phase==0?first:memory.shop_phase==1?second:
            memory.shop_phase%2==0?(caster?item_type::power_shard_of_focus:item_type::power_shard_of_strength):item_type::power_shard_of_health;
        const auto inventory=read([&]{return me.item_count();});
        const auto combined=item.result();if(!combined||item.combine_count()==0)break;
        std::uint64_t units=std::uint64_t(inventory[item])+std::uint64_t(item.combine_count())*inventory[*combined];
        if(units>INT_MAX-5)break;
        if(!memory.shop_target)memory.shop_target=int(units)+5;
        if(units>=unsigned(memory.shop_target)){++memory.shop_phase;memory.shop_target=0;continue;}
        if(!read([&]{return me.can_buy(item);}))break;
        auto result=turn.perform({turn.epoch(),action::Op::item_buy,{}},[&]{return read([&]{return me.can_buy(item);});},[&]{me.buy(item);});
        if(!result.accepted())break;
        turn.check();const auto after=read([&]{return me.item_count();});
        std::uint64_t after_units=std::uint64_t(after[item])+std::uint64_t(item.combine_count())*after[*combined];
        if(!turn.ledger().observe(result.event,turn.epoch(),false,false,after_units>units))return changed;
        changed=true;if(after_units<=units)return changed; // no fabricated progress or further optional mutation
    }
    if((!alive||spawn)&&fuel_remaining()>15000&&turn.ledger().at(action::Op::consumable_buy).admitted==0&&
        read([&]{return me.consumables()[consumable_type::altar_lock].count();})==0&&read([&]{return me.can_buy(consumable_type::altar_lock);})) {
        auto result=turn.perform({turn.epoch(),action::Op::consumable_buy,{}},[&] {
            return read([&]{return me.consumables()[consumable_type::altar_lock].count();})==0&&read([&]{return me.can_buy(consumable_type::altar_lock);});
        },[&]{me.buy(consumable_type::altar_lock);});
        if(result.accepted()) {
            turn.check();const auto count=read([&]{return me.consumables()[consumable_type::altar_lock].count();});
            turn.ledger().observe(result.event,turn.epoch(),false,false,count>0);changed=true;
        }
    }
    return changed;
}
bool economic_ward(const economic::Scene& scene,const economic::Task& task,LiveTurn& turn) {
    using economic::Channel;const auto& own=scene.economy.self;
    if(!Config::wards||!scene.economy.complete||!own.alive||own.completed||own.stunned||own.channel!=Channel::none||
        scene.ward_restricted||own.hp<own.max_hp*Config::recovery_high||fuel_remaining()<45000||
        turn.ledger().at(action::Op::ward).admitted)return false;
    for(const auto& e:scene.enemies)if(e.alive&&std::max(std::abs(e.pos.x-own.pos.x),std::abs(e.pos.y-own.pos.y))<=6)return false;
    turn.check();if(own.epoch!=turn.epoch())throw TurnExpired{};
    auto read=[&](auto f){return turn.read(f);};auto& me=self();
    if(read([&]{return me.ward_cooldown();})>0)return false;
    const auto enemyspawn=read([]{return map::spawn_region(team::enemy).positions();});if(enemyspawn.empty())return false;
    const vec2 origin{own.pos.x,own.pos.y};
    auto target=task.present?vec2{task.anchor.x,task.anchor.y}:enemyspawn.front();
    const auto positions=read([&]{return me.ward_positions();});
    if(!positions.empty()&&cheb(origin,positions.front())<6)return false;
    auto blocked=read([]{return static_blocked()|vision::champion_tiles()|vision::camp_tiles()|vision::teleport_tiles();});
    auto free=read([&]{return me.ward_placement_tiles()&vision::visible_tiles()&~(blocked|vision::ward_tiles());});
    const auto cells=read([&]{return free.positions();});
    if(cells.size()>16384)throw TurnDeferred{};
    std::optional<vec2> best;std::int64_t score=INT64_MIN;
    for(auto p:cells) {
        std::int64_t forward=std::int64_t(p.x-origin.x)*(target.x-origin.x)+std::int64_t(p.y-origin.y)*(target.y-origin.y);
        if(forward<=0)continue;
        auto value=std::int64_t(cheb(p,origin))*100+forward;
        if(!best||value>score){score=value;best=p;}
    }
    turn.check();if(own.epoch!=turn.epoch()||!best)return false;
    if(!turn.ledger().handoff(action::Owner::optional,own.epoch))return false;
    auto result=turn.perform({own.epoch,action::Op::ward,{-1,best->x,best->y}},[&]{return read([&]{return me.ward_cooldown();})==0&&read([&]{return me.ward_placement_tiles().is_set(*best);});},[&]{return me.place_ward(*best);});
    if(result.event&&(result.accepted()||result.stop==action::Stop::refused)) {
        turn.check();turn.ledger().observe(result.event,turn.epoch());
    }
    return result.accepted();
}
}
