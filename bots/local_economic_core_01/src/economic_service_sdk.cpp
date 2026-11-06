#include "economic_service_sdk.h"
#include <algorithm>
#include <cmath>
#include <optional>
namespace lp {
action::Result perform_service(const economic::Scene& scene,const economic::ServiceChoice& choice,LiveTurn& turn) {
    using action::Op;using economic::AbilityKind;
    if(choice.stop!=economic::ServiceStop::action||choice.request.epoch!=scene.economy.self.epoch)
        return {action::Stop::denied,0};
    const auto request=choice.request;
    if(!turn.ledger().handoff(action::Owner::service,request.epoch))return {action::Stop::sealed,0};
    std::optional<camp> target;
    std::optional<champion> ally;
    std::optional<ability> spell;
    auto& me=self();const vec2 destination{request.target.x,request.target.y};
    auto read=[&](auto f){return turn.read(f);};
    return turn.perform(request,[&] {
        if(turn.epoch()!=scene.economy.self.epoch)return false;
        auto actual=read([&]{return me.position();});
        if(actual!=vec2{scene.economy.self.pos.x,scene.economy.self.pos.y})return false;
        const auto op=request.op;
        if(op==Op::step) {
            if(std::max(std::abs(destination.x-actual.x),std::abs(destination.y-actual.y))!=1||
                !scene.physical({destination.x,destination.y}))return false;
            return read([&]{return me.base_stats();}).base_move_speed>=1;
        }
        if(op==Op::basic||op==Op::cast) {
            if(request.target.task<0||request.target.task>=int(scene.groups.size()))return false;
            bool member=false;
            for(const auto& row:scene.members)if(int(row.key)==request.target.key&&row.group==request.target.task&&
                row.visible&&row.known&&row.alive&&row.hp_known&&row.pos==economic::Point{destination.x,destination.y})member=true;
            if(!member)return false;
            target=read([&]{return vision::camp_at(destination);});
            if(unsigned(static_cast<handle_camp_t>(*target))!=unsigned(request.target.key))return false;
            if(!read([&]{return target->state();}).is_alive()||read([&]{return target->health();})<=0)return false;
            if(op==Op::basic)return read([&]{return me.attack_tiles().is_set(destination);});
        }
        if(op==Op::heal) {
            ally=read([&]{return vision::champion_at(destination);});
            if(id(*ally)!=request.target.key||!read([&]{return ally->is_ally();})||!read([&]{return ally->is_alive();}))return false;
        }
        const auto slot=request.target.slot;
        auto abilities=read([&]{return me.abilities();});
        if(slot<0||slot>=int(abilities.size())||slot>=int(scene.abilities.size()))return false;
        spell=abilities[slot];const auto& metadata=scene.abilities[slot];
        if(!metadata.supported||read([&]{return spell->cooldown();})!=0)return false;
        const bool kind=(op==Op::reset&&metadata.kind==AbilityKind::reset&&spell->is_attack_reset())||
            (op==Op::shield&&metadata.kind==AbilityKind::shield&&spell->is_shield())||
            (op==Op::heal&&metadata.kind==AbilityKind::heal&&spell->is_heal())||
            (op==Op::dash&&metadata.kind==AbilityKind::dash&&spell->is_dash())||
            (op==Op::cast&&((metadata.kind==AbilityKind::damage&&spell->is_damage())||
                           (metadata.kind==AbilityKind::cc&&spell->is_cc())));
        if(!kind||(metadata.exclusive&&turn.ledger().steps+turn.ledger().dashes>0))return false;
        if(op==Op::cast&&!spell->can_target_camps())return false;
        if(op==Op::heal&&!spell->can_target_allies())return false;
        if(op==Op::reset)return !read([&]{return me.can_attack();});
        if(op==Op::shield)return true;
        if(op==Op::dash&&(!scene.physical({destination.x,destination.y})||metadata.exclusive))return false;
        return read([&]{return spell->valid_tiles().is_set(destination);});
    },[&]() -> bool {
        switch(request.op) {
        case Op::step:return me.move_absolute(destination);
        case Op::basic:me.attack(*target);return true;
        case Op::reset:case Op::shield:return spell->use();
        case Op::heal:return spell->use(*ally);
        case Op::dash:return spell->use(destination);
        case Op::cast:return spell->use(*target);
        default:return false;
        }
    });
}
}
