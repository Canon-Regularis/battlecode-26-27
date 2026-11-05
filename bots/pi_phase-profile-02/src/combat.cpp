#include "phase_profile.h"
#include "combat.h"
#include <tuple>
#include <optional>
namespace lp {
bool defend_cast(const Snapshot& s) {
    PPFX_SCOPE(defend_cast)
    auto& me=self();if(!me.can_cast()||channel(me))return false;
    auto current=[&]{return int(round_number())==s.round&&fuel_remaining()>Config::reserve;};
    for(const auto& a:me.abilities())if(ready(a)) {
        if(a.is_shield()&&s.incoming>0&&s.hp<s.max_hp*0.7f&&current()) {bool used=a.use();if(used)invalidate_observations();return used;}
        if(a.is_heal()) {
            const champion* target=nullptr;float best=0;
            for(const auto& ally:s.allies)if(id(ally)!=id(me)&&a.valid_tiles().is_set(ally.position())&&ally.health()<ally.max_health()*0.75f) {
                float v=a.heal_amount(ally);if(incoming_at(ally.position(),s.foes)>=ally.health())v+=10000;
                if(v>best){best=v;target=&ally;}
            }
            if(target&&current()){bool used=a.use(*target);if(used)invalidate_observations();return used;}
        }
    }return false;
}
bool fight(World& w,int task,bool travel) {
    PPFX_SCOPE(fight)
    auto& me=self();if(channel(me)||(!me.can_attack()&&!me.can_cast()))return false;
    const auto& s=observe();const int round=s.round;defend_cast(s);
    auto current=[&]{return int(round_number())==round&&fuel_remaining()>Config::reserve;};
    if(!current())return false;
    const unit* target=nullptr;bool enemy=false;float hp=1e20f;
    // Keep SDK handle wrappers alive through execution, beyond the selection loop.
    std::optional<camp> selected_camp;
    auto reachable=[&](const unit& u,bool is_enemy) {
        if(me.can_attack()&&me.attack_tiles().is_set(u.position()))return true;
        if(me.can_cast())for(const auto& a:me.abilities())if(ready(a)&&(a.is_damage()||a.is_aoe_damage()||a.is_cc())&&
            (is_enemy?a.can_target_enemies():a.can_target_camps())&&a.valid_tiles().is_set(u.position()))return true;
        return false;
    };
    for(const auto& e:s.foes)if(cheb(e.position(),s.pos)<=std::max(3,e.attack_range())&&reachable(e,true)&&e.health()<hp){target=&e;enemy=true;hp=e.health();}
    if(!target&&!travel&&task>=0)for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()&&reachable(c,false)&&c.health()<hp){selected_camp=c;hp=c.health();}
    if(selected_camp)target=&*selected_camp;
    if(!target||!current())return false;
    bool acted=false;
    // Basic attack first lets attack-reset kits realize a second attack in the same turn.
    if(me.can_attack()&&me.attack_tiles().is_set(target->position())) {me.attack(*target);invalidate_observations();acted=true;}
    if(!current()||!target->is_visible()||target->health()<=0)return acted;
    if(me.can_cast()) {
        const ability* best=nullptr;float value=-1;vec2 center=target->position();
        auto abilities=me.abilities();
        for(const auto& a:abilities)if(ready(a)) {
            if(a.is_attack_reset()&&acted&&!me.can_attack()&&me.attack_tiles().is_set(target->position())) {
                float v=me.strength();if(v>value){best=&a;value=v;}continue;
            }
            if(!(a.is_damage()||a.is_aoe_damage()||a.is_cc())||!(enemy?a.can_target_enemies():a.can_target_camps())||!a.valid_tiles().is_set(target->position()))continue;
            float damage=enemy?a.damage_amount(*static_cast<const champion*>(target)):a.damage_amount();
            float v=std::min(hp,damage)+(damage>=hp?10000:0);
            if(a.is_aoe_damage()) {
                float r=a.get<ability_aoe_damage>().radius;
                for(const auto& e:s.foes)if(cheb(e.position(),center)<=r)v+=0.01f;
                if(task>=0)for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()&&cheb(c.position(),center)<=r)v+=0.01f;
            }
            if(v>value){value=v;best=&a;}
        }
        if(best&&current()&&(!best->is_attack_reset()||!me.can_attack())) {
            bool success=best->is_attack_reset()?best->use():(best->can_target_ground()?best->use(center):
                enemy?best->use(*static_cast<const champion*>(target)):best->use(*static_cast<const camp*>(target)));
            if(success)invalidate_observations();acted|=success;
            if(success&&current()&&best->is_attack_reset()&&target->is_visible()&&target->health()>0&&me.can_attack()&&me.attack_tiles().is_set(target->position())){me.attack(*target);invalidate_observations();}
        }
    }
    return acted;
}
void optional_ward(const World& w,int task) {
    auto& me=self();if(!Config::wards||!me.is_alive()||channel(me)||me.ward_cooldown()>0||fuel_remaining()<45000)return;
    const auto& s=observe();if(s.hp<s.max_hp*Config::recovery_high||s.enemies>0)return;
    auto enemyspawn=map::spawn_region(team::enemy).positions();if(enemyspawn.empty())return;
    auto target=task>=0?w.camps[task].anchor:enemyspawn.front();
    auto positions=me.ward_positions();if(!positions.empty()&&cheb(s.pos,positions.front())<6)return;
    auto free=me.ward_placement_tiles()&s.visible&~(s.blocked|vision::ward_tiles());
    auto best=s.pos;int score=-100000;
    for(auto p:free.positions()) {
        auto dx=p.x-s.pos.x,dy=p.y-s.pos.y;int forward=dx*(target.x-s.pos.x)+dy*(target.y-s.pos.y);
        if(forward<=0)continue;int v=cheb(p,s.pos)*100+forward;if(v>score){score=v;best=p;}
    }
    if(best!=s.pos&&int(round_number())==s.round&&fuel_remaining()>Config::reserve){me.place_ward(best);invalidate_observations();}
}
}
