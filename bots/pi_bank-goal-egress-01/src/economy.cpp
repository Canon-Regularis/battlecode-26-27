#include "economy.h"
#include "combat.h"
#include <tuple>
namespace lp {
namespace {
// Only the failed-bank path may omit awake-camp regions from a safe field.
RouteStatus bank_egress(bitboard goals,TurnBudget& budget,Memory& mem) {
    auto current=[&] {return budget.current()&&fuel_remaining()>Config::reserve;};
    auto& me=self();
    if(!current())return RouteStatus::deferred;
    if(!me.is_alive()||channel(me)||!me.can_move()||me.restrictions().contains(buff_restrictions::move))return RouteStatus::wait;
    const auto& s=observe();
    if(!current()||s.round!=budget.round)return RouteStatus::deferred;
    const auto origin=s.pos;
    auto blocked=s.blocked|s.risk;blocked.set(origin,false);goals&=~blocked;
    if(!current())return RouteStatus::deferred;
    if(goals.is_empty())return RouteStatus::invalid_goals;
    if(goals.is_set(origin))return RouteStatus::at_goal;
    if(!budget.admit())return RouteStatus::deferred;

    // Capture once, in incoming_at's enemy-then-camp order. Compare every tile
    // against this same set, rather than mixing refreshed host query epochs.
    struct Threat {vec2 pos;int range;float strength;};
    std::vector<Threat> threats;
    for(const auto& e:s.foes) {
        if(!current())return RouteStatus::deferred;
        auto pos=e.position();auto range=e.attack_range();auto strength=e.strength();
        if(!current())return RouteStatus::deferred;
        threats.push_back({pos,range,strength});
    }
    if(!current())return RouteStatus::deferred;
    const auto camps=vision::camps();
    if(!current())return RouteStatus::deferred;
    for(const auto& c:camps) {
        if(!current())return RouteStatus::deferred;
        bool active=c.is_alive()&&c.is_awake();
        if(!current())return RouteStatus::deferred;
        if(!active)continue;
        auto strength=c.strength();
        if(!current())return RouteStatus::deferred;
        if(!(strength>0))continue;
        auto pos=c.position();auto range=c.attack_range();
        if(!current())return RouteStatus::deferred;
        threats.push_back({pos,range,strength});
    }
    auto incoming=[&](vec2 p) {float damage=0;for(const auto& t:threats)if(cheb(t.pos,p)<=t.range)damage+=t.strength;return damage;};
    const auto origin_incoming=incoming(origin);
    distance_field field;bitboard reached;auto root=around(origin,0);
    if(!current()||!budget.admit())return RouteStatus::deferred;
    ++budget.fields;field.compute_to(blocked,goals,root,reached);
    if(!current())return RouteStatus::deferred;
    if(!reached.is_set(origin))return RouteStatus::no_route_now;
    auto distance=field.get(origin);
    auto best=origin;auto score=std::tuple{distance,origin_incoming,origin.y,origin.x};
    for(auto p:blocked.reachable_tiles(origin,1).positions()) {
        if(!current())return RouteStatus::deferred;
        if(p==origin)continue;
        auto d=field.get(p);auto damage=incoming(p);
        if(d==distance_field::unreachable||d>=distance||!(damage<=origin_incoming))continue;
        auto candidate=std::tuple{d,damage,p.y,p.x};
        if(candidate<score){best=p;score=candidate;}
    }
    if(!current())return RouteStatus::deferred;
    if(best==origin)return RouteStatus::no_route_now;
    if(!me.is_alive()||channel(me)||!me.can_move()||me.restrictions().contains(buff_restrictions::move))return RouteStatus::wait;
    if(!current())return RouteStatus::deferred;
    if(move_checked(best)){mem.blocked=0;mem.last_distance=std::get<0>(score);return RouteStatus::moved;}
    return RouteStatus::wait;
}
}
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
            if(b.current()&&s.round==b.round&&s.camp_hit&&s.incoming>0&&fuel_remaining()>Config::reserve)
                bank_egress(around(altar,1),b,m);
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
    me.submit_gems(altar);invalidate_observations();
    if(me.is_submitting_gems()){m.bank_bag=me.gem_count();m.bank_score=global_submitted_gems(team::ally);return true;}
    return false;
}
}
