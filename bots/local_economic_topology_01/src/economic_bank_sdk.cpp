#include "economic_bank_sdk.h"
#include <algorithm>
#include <cmath>
#include <climits>
#include <optional>
namespace lp {
namespace {
int distance(economic::Point a,economic::Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
bool banking(economic::Purpose p){return p==economic::Purpose::convert||p==economic::Purpose::observe_access;}
}
bool bank_position_safe(const economic::Scene& s) {
    const auto& own=s.economy.self;
    if(!s.economy.complete||!own.alive||!s.seen(own.pos)||!std::isfinite(own.hp)||own.hp<=0)return false;
    for(const auto& enemy:s.enemies)if(enemy.alive&&distance(enemy.pos,own.pos)<=enemy.range+enemy.move_range)return false;
    for(const auto& camp:s.members)if(!camp.passive&&distance(camp.pos,own.pos)<=camp.range&&
        (!camp.known||(camp.alive&&camp.awake&&camp.strength>0)))return false;
    return true;
}
BankChoice choose_bank(const economic::Scene& s,const economic::Task& task,const action::Ledger& ledger) {
    using namespace economic;using action::Op;
    const auto& own=s.economy.self;
    if(!s.economy.complete||!ledger.current(own.epoch))return {BankStop::blocked};
    if(own.channel!=Channel::none)return {BankStop::channel};
    if(!task.present||!banking(task.key.purpose)||task.key.object<0||task.key.object>=int(s.altars.size()))return {BankStop::blocked};
    if(!own.alive||own.completed||own.stunned)return {BankStop::allowance};
    if(!own.bag)return {BankStop::complete};
    const auto altar=s.altars[task.key.object];
    if(distance(own.pos,altar)>constants::submit_gems_range)return {BankStop::approach};
    if(!s.seen(altar))return {BankStop::hidden};
    if(!bank_position_safe(s))return {BankStop::unsafe};
    const Lock* lock=nullptr;
    for(const auto& current:s.locks)if(current.pos==altar) {
        if(lock||!current.hits)return {BankStop::blocked};
        lock=&current;
    }
    auto action=[&](Op op,int slot=-1) {
        BankChoice choice;choice.stop=BankStop::action;
        choice.request={own.epoch,op,{lock&&!lock->allied?int(lock->hits):-1,altar.x,altar.y,slot,
            task.key.object,task.key.cycle,task.key.contact},op==Op::lock_basic||op==Op::reset};
        return choice;
    };
    if(lock&&!lock->allied) {
        if(lock->hits>INT_MAX)return {BankStop::unsupported};
        if(distance(own.pos,altar)>s.attack_range||s.attack_restricted)return {BankStop::blocked};
        if(ledger.basics>=2||ledger.primitives>=4||ledger.service_rejections>=2)return {BankStop::allowance};
        if(s.can_attack)return action(Op::lock_basic);
        if(!s.can_cast||s.cast_restricted||ledger.casts)return {BankStop::allowance};
        for(unsigned slot=0;slot<s.abilities.size();++slot) {
            const auto& a=s.abilities[slot];
            if(a.kind==AbilityKind::reset&&a.supported&&a.cooldown==0&&
                !(a.exclusive&&ledger.steps+ledger.dashes))return action(Op::reset,int(slot));
        }
        return {BankStop::allowance};
    }
    // Own locks are optional preparation; they never require a purchase or a
    // wait. The current documented lock-placement subset has range two.
    if(!lock&&s.carried_locks&&!s.consumable_restricted&&!ledger.lock_attempted&&distance(own.pos,altar)<=2)
        return action(Op::lock_use);
    if(ledger.submit_attempted)return {BankStop::allowance};
    return action(Op::submit);
}
action::Result perform_bank(const economic::Scene& scene,const BankChoice& choice,LiveTurn& turn) {
    using action::Op;using economic::AbilityKind;
    if(choice.stop!=BankStop::action||choice.request.epoch!=scene.economy.self.epoch)return {action::Stop::denied,0};
    const auto request=choice.request;
    if(request.op!=Op::lock_basic&&request.op!=Op::reset&&request.op!=Op::lock_use&&request.op!=Op::submit)
        return {action::Stop::denied,0};
    economic::Task task{{request.target.task,request.target.cycle,request.target.contact,
        economic::Purpose::convert,economic::Role::carrier},economic::Phase::access,{},economic::Evidence::ready,economic::Reason::none,true};
    const auto expected=choose_bank(scene,task,turn.ledger());
    if(expected.stop!=BankStop::action||expected.request.op!=request.op||expected.request.target!=request.target||
        expected.request.service!=request.service)return {action::Stop::denied,0};
    if(!turn.ledger().handoff(action::Owner::bank,request.epoch))return {action::Stop::sealed,0};
    auto& me=self();const vec2 altar{request.target.x,request.target.y};
    std::optional<altar_lock> enemy_lock;
    std::optional<ability> reset;
    std::optional<consumable> own_lock;
    auto read=[&](auto f){return turn.read(f);};
    auto guard=[&] {
        if(turn.epoch()!=scene.economy.self.epoch||!bank_position_safe(scene))return false;
        const auto actual=read([&]{return me.position();});
        if(actual!=vec2{scene.economy.self.pos.x,scene.economy.self.pos.y}||
            std::max(std::abs(actual.x-altar.x),std::abs(actual.y-altar.y))>constants::submit_gems_range||
            !read([&]{return me.gem_count();})||!read([&]{return vision::visible_tiles().is_set(altar);}))return false;
        // Exactly one fresh all-team snapshot, shared by this operation's
        // checks. No private lock handles or blind submission probes.
        const auto locks=read([]{return vision::altar_locks();});
        bool present=false;
        for(const auto& lock:locks)if(lock.position()==altar) {
            if(present)return false;present=true;
            if(lock.is_enemy())enemy_lock=lock;
        }
        if(request.op==Op::lock_basic||request.op==Op::reset) {
            if(!enemy_lock||enemy_lock->hits_remaining()!=unsigned(request.target.key)||
                !read([&]{return me.attack_tiles().is_set(altar);}))return false;
            if(request.op==Op::lock_basic)return true;
            const int slot=request.target.slot;
            if(slot<0||slot>=int(scene.abilities.size()))return false;
            const auto& metadata=scene.abilities[slot];
            if(metadata.kind!=AbilityKind::reset||!metadata.supported||
                (metadata.exclusive&&turn.ledger().steps+turn.ledger().dashes))return false;
            reset=read([&]{return me.abilities();})[slot];
            return reset->is_attack_reset()&&read([&]{return reset->cooldown();})==0&&
                !read([&]{return me.can_attack();});
        }
        if(enemy_lock)return false;
        if(request.op==Op::submit)return true;
        if(present||std::max(std::abs(actual.x-altar.x),std::abs(actual.y-altar.y))>2)return false;
        own_lock=me.consumables()[consumable_type::altar_lock];
        return read([&]{return own_lock->count();})>0;
    };
    // A normal void return is an acknowledgement only. Root observes the new
    // channel in a fresh scene before the ledger can accept this submission.
    if(request.op==Op::submit)return turn.perform(request,guard,[&]{me.submit_gems(altar);});
    return turn.perform(request,guard,[&]() -> bool {
        if(request.op==Op::lock_basic){me.attack(*enemy_lock);return true;}
        if(request.op==Op::reset)return reset->use();
        return own_lock->use(altar);
    });
}
}
