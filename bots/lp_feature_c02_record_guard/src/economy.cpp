#include "economy.h"
#include "combat.h"
#include "feature_state.h"
namespace lp {
void shop(Memory& m) {
    auto& me=self();bool alive=me.is_alive();if(alive&&channel(me))return;
    if(me.gold_count()<10)return;
    bool spawn=alive&&map::spawn_region(team::ally).is_set(me.position());
    if(alive&&!spawn&&me.champion_name()!=champion_type::tavi)return;
    auto type=me.champion_name();bool caster=type==champion_type::heart_of_ruin||type==champion_type::ren||type==champion_type::prism||type==champion_type::stellar||type==champion_type::willow||type==champion_type::tavi||type==champion_type::cassi;
    auto first=type==champion_type::vesper_vale?item_type::treasure_shard_of_strength:item_type::durability_shard_of_health;
    auto second=caster?item_type::monster_shard_of_focus:item_type::monster_shard_of_strength;
    for(int purchases=0;purchases<40&&fuel_remaining()>15000;++purchases) {
        auto item=m.shop_phase==0?first:m.shop_phase==1?second:(m.shop_phase%2==0?(caster?item_type::power_shard_of_focus:item_type::power_shard_of_strength):item_type::power_shard_of_health);
        auto inventory=me.item_count();int owned=inventory[item]+item.combine_count()*inventory[item.result().value()];
        if(!m.shop_target)m.shop_target=owned+5;
        if(owned>=m.shop_target){++m.shop_phase;m.shop_target=0;--purchases;continue;}
        if(!me.can_buy(item))break;me.buy(item);invalidate_observations();
    }
    if((!alive||spawn)&&me.consumables()[consumable_type::altar_lock].count()==0&&me.can_buy(consumable_type::altar_lock))me.buy(consumable_type::altar_lock);
}
bool bank(World& w,TurnBudget& b,Memory& m) {
    auto& me=self();const auto& s=observe();
    if(s.bag==0){m.altar=-1;m.queue_started=-1;return false;}
    if(m.altar<0||s.round%3==w.slot%3||m.blocked>=3) {int chosen=choose_altar(w,s,b,m.altar);if(chosen>=0)m.altar=chosen;}
    if(m.altar<0)return false;
    auto altar=w.altars[m.altar];
    if(cheb(s.pos,altar)>1){
        auto status=move_to(around(altar,1),true,b,m);observe();
        if(status==RouteStatus::no_route_now||status==RouteStatus::invalid_goals) {
            if(m.blocked>=3){w.altar_retry[m.altar]=s.round+3;m.altar=-1;m.blocked=0;}
            return false;
        }
    }
    if(!b.current()||cheb(s.pos,altar)>1)return false;
    for(const auto& lock:vision::altar_locks(team::enemy))if(lock.position()==altar) {
        fight(w,-1,true);if(me.can_attack()&&me.attack_tiles().is_set(altar))me.attack(lock);return false;
    }
    bool wait=false;
    for(const auto& a:s.allies)if(id(a)!=id(me)&&cheb(a.position(),altar)<=1) {
        if(a.is_submitting_gems())wait=true;
        else if(a.gem_count()>0&&(a.gem_count()>me.gem_count()||(a.gem_count()==me.gem_count()&&id(a)<id(me))))wait=true;
    }
    if(wait) {
        if(m.queue_started<0)m.queue_started=s.round;
        if(s.round-m.queue_started<3){fight(w,-1,true);return false;}
        if(w.altars.size()>1){m.altar=(m.altar+1)%w.altars.size();m.queue_started=-1;return false;}
    }
    m.queue_started=-1;
    bool ownlock=false;for(auto& l:vision::altar_locks(team::ally))if(l.position()==altar)ownlock=true;
    if(!ownlock&&me.consumables()[consumable_type::altar_lock].count()>0)me.consumables()[consumable_type::altar_lock].use(altar);
    if(channel(me))return me.is_submitting_gems();
    if constexpr(Features::channel_guards)if(!channel_start_allowed(me.is_alive(),me.buffs().has_stun(),channel(me),me.has_completed_turn(),me.state().contains(champion_state::submit_gems_started))||!b.current())return false;
    me.submit_gems(altar);invalidate_observations();
    if(me.is_submitting_gems()){m.bank_bag=me.gem_count();if constexpr(Features::bank_record)feature_state().bank_life=m.life;m.bank_score=global_submitted_gems(team::ally);return true;}
    return false;
}
}
