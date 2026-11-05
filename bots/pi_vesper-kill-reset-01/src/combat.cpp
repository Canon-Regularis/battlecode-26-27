#include "combat.h"
#include <tuple>
#include <optional>
namespace lp {
bool defend_cast(const Snapshot& s) {
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
namespace {
// Bounded continuation of a camp basic kill, never a new combat dispatch.
void vesper_kill_reset(World& w,int task,int round,const camp& killed,vec2 last_position) {
    auto& me=self();
    auto current=[&]{return int(round_number())==round&&fuel_remaining()>Config::reserve;};
    // Only camp queries may decline on expected visibility/entity loss.
    // Self, metadata and action errors propagate.
    auto query=[&](auto get,bool visibility_loss=false)->std::optional<decltype(get())> {
        if(!current())return std::nullopt;
        try {
            auto value=get();
            if(current())return value;
        } catch(const error& e) {
            if(!visibility_loss||(e.code()!=error_code::api_not_in_vision&&e.code()!=error_code::api_not_found))throw;
        }
        return std::nullopt;
    };
    if(task<0||task>=int(w.camps.size()))return;
    auto name=query([&]{return me.champion_name();});
    if(!name||*name!=champion_type::vesper_vale)return;
    auto actor_ok=[&](bool after_reset) {
        auto state=query([&]{return me.state();});
        if(!state||state->is_dead()||state->contains(champion_state::recalling)||
            state->contains(champion_state::submitting_gems)||state->contains(champion_state::teleporting))return false;
        if(!after_reset&&(state->contains(champion_state::can_attack)||
            state->contains(champion_state::can_move)||!state->contains(champion_state::can_cast)))return false;
        auto restrictions=query([&]{return me.restrictions();});
        return restrictions&&!restrictions->contains(buff_restrictions::attack)&&!restrictions->contains(buff_restrictions::cast);
    };
    if(!actor_ok(false))return;
    // A dead camp has no live info record. Its last tile must still be in vision
    // before asking the separate, visibility-checked lifecycle API for proof.
    auto visible=query([&]{return vision::in_vision(last_position);});
    if(!visible||!*visible)return;
    auto dead=query([&]{return killed.is_dead();},true);
    if(!dead||!*dead)return;
    auto abilities=query([&]{return me.abilities();});
    if(!abilities)return;
    const ability* reset=nullptr;
    for(const auto& a:*abilities)if(a.is_attack_reset()&&a.can_target_self()) {
        auto available=query([&]{return ready(a);});
        if(!available)return;
        if(*available){reset=&a;break;}
    }
    if(!reset)return;
    auto geometry=query([&]{return me.attack_tiles();});
    if(!geometry)return;
    std::optional<camp> sibling;float hp=1e20f;
    for(const auto& c:w.camps[task].group.camps()) {
        auto seen=query([&]{return c.is_visible();},true);
        if(!seen)return;
        if(!*seen)continue;
        auto alive=query([&]{return c.is_alive();},true);
        if(!alive)return;
        if(!*alive)continue;
        auto position=query([&]{return c.position();},true);
        if(!position)return;
        auto in_range=query([&]{return geometry->is_set(*position);});
        if(!in_range)return;
        if(!*in_range)continue;
        auto health=query([&]{return c.health();},true);
        if(!health)return;
        if(*health>0&&*health<hp){sibling=c;hp=*health;}
    }
    if(!sibling)return;
    auto target_ok=[&] {
        auto seen=query([&]{return sibling->is_visible();},true);
        if(!seen||!*seen)return false;
        auto alive=query([&]{return sibling->is_alive();},true);
        if(!alive||!*alive)return false;
        auto position=query([&]{return sibling->position();},true);
        if(!position)return false;
        auto in_range=query([&]{return geometry->is_set(*position);});
        return in_range&&*in_range;
    };
    auto available=query([&]{return ready(*reset);});
    if(!available||!*available||!actor_ok(false)||!target_ok()||!current())return;
    if(!reset->use())return;
    invalidate_observations();
    if(!current()||!actor_ok(true)||!target_ok())return;
    auto attack=query([&]{return me.can_attack();});
    if(!attack||!*attack||!current())return;
    me.attack(*sibling); // SDK attack is void and propagates errors.
    invalidate_observations();
}
}
bool fight(World& w,int task,bool travel) {
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
    if(!target&&!travel&&task>=0&&task<int(w.camps.size()))for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()&&reachable(c,false)&&c.health()<hp){selected_camp=c;hp=c.health();}
    if(selected_camp)target=&*selected_camp;
    if(!target||!current())return false;
    bool acted=false;std::optional<vec2> camp_basic_position;
    // Capture the already-required position query; dead camps have no live record.
    auto basic_position=[&]{camp_basic_position=target->position();return *camp_basic_position;};
    // Basic attack first lets attack-reset kits realize a second attack in the same turn.
    if(me.can_attack()&&me.attack_tiles().is_set(basic_position())) {
        me.attack(*target);invalidate_observations();acted=true;
    }
    if(!current())return acted;
    if(!target->is_visible()||target->health()<=0) {
        if(acted&&selected_camp&&!enemy&&!travel&&camp_basic_position)
            vesper_kill_reset(w,task,round,*selected_camp,*camp_basic_position);
        return acted;
    }
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
