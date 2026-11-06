#include "economic_plan_sdk.h"
#include <algorithm>
namespace lp {
namespace {
PlanStatus status(FieldStatus value) {
    switch(value) {
    case FieldStatus::ready:return PlanStatus::ready;
    case FieldStatus::planning:return PlanStatus::planning;
    case FieldStatus::deferred:return PlanStatus::deferred;
    case FieldStatus::exposed:return PlanStatus::exposed;
    case FieldStatus::unavailable:return PlanStatus::unavailable;
    case FieldStatus::capacity:return PlanStatus::capacity;
    case FieldStatus::stale:return PlanStatus::stale;
    }
    return PlanStatus::capacity;
}
bool bank(economic::Purpose p){return p==economic::Purpose::convert||p==economic::Purpose::observe_access;}
bool same_semantic(economic::Key a,economic::Key b) {
    return a.object==b.object&&a.cycle==b.cycle&&a.purpose==b.purpose&&a.role==b.role;
}
}
void EconomicPlanner::cancel_pending() {
    fields.cancel_pending();route.cancel_job();candidates={};frozen={};have_frozen=false;stage=Stage::field;selected={};
}
EconomicPlan EconomicPlanner::prepare(World& world,const economic::Scene& scene,economic::Owner& owner,
        LiveTurn& turn,unsigned& writes,bool repair) {
    using namespace economic;
    turn.check();if(scene.economy.self.epoch!=turn.epoch())throw TurnExpired{};
    if(!scene.economy.complete)return {PlanStatus::deferred};
    if(have_frozen&&(scene.economy.self.epoch.actor!=frozen.economy.self.epoch.actor||
        scene.economy.self.epoch.life!=frozen.economy.self.epoch.life||scene.economy.self.pos!=frozen.economy.self.pos)) {
        cancel_pending();return {PlanStatus::stale};
    }
    if(stage==Stage::field) {
        auto delivery=fields.prepare_delivery(world,turn,writes);
        if(delivery!=FieldStatus::ready)return {status(delivery)};
        if(!have_frozen) {
            settings=ranking_settings(scene,turn);
            auto started=fields.start_origin(world,scene,turn);
            if(started!=FieldStatus::planning&&started!=FieldStatus::ready)return {status(started)};
            frozen=scene;have_frozen=true;
        }
        const auto progress=fields.continue_origin(turn,scene.economy.self.pos,writes);
        if(progress!=FieldStatus::ready)return {status(progress)};
        candidates.begin(frozen,fields.origin(),settings);stage=Stage::candidates;
    }
    if(stage==Stage::candidates) {
        const auto progress=candidates.continue_build(frozen,fields.origin(),fields.delivery(),writes);
        turn.check();if(scene.economy.self.epoch!=turn.epoch())throw TurnExpired{};
        if(progress==CandidatesStatus::planning)return {PlanStatus::planning};
        if(progress!=CandidatesStatus::ready){cancel_pending();return {progress==CandidatesStatus::stale?PlanStatus::stale:PlanStatus::capacity};}
        // Positive lifecycle/role changes invalidate the affected old options.
        // A completed old graph never certifies a new target cycle/role.
        auto options=candidates.options();
        options.erase(std::remove_if(options.begin(),options.end(),[&](const auto& c) {
            if(bank(c.key.purpose))return false;
            if(c.key.object<0||c.key.object>=int(scene.groups.size()))return true;
            const auto& now=scene.groups[c.key.object].observation;
            const auto& before=frozen.groups[c.key.object].observation;
            return now.fresh&&(now.cycle!=c.key.cycle||now.life==Life::respawning||
                (now.life==Life::reward&&(before.life!=Life::reward||now.role_fact!=before.role_fact||now.self_occupant!=before.self_occupant)));
        }),options.end());
        // A graph intentionally carried to a later epoch supplies conditional
        // geometry, never an executable BankNow or current winning start.
        if(scene.economy.self.epoch!=frozen.economy.self.epoch)for(auto& c:options)if(bank(c.key.purpose)) {
            c.conditional=true;c.conversion=Evidence::unknown;c.estimate_priced=false;c.winning_start=false;
        }
        if(scene.economy.self.bag!=frozen.economy.self.bag)for(auto& c:options)if(c.key.purpose==Purpose::gems) {
            auto bag=scene.economy.self.bag;
            if(c.own_gems>UINT64_MAX-bag||!settings.duration_supported||
                !tribute_turns(bag+c.own_gems,settings.tribute,c.tribute_turns))c.estimate_priced=false;
        }
        selected=owner.update(scene.economy,options,true);
        if(selected.decision!=Decision::task) {
            const auto directive=selected;cancel_pending();
            return {directive.decision==Decision::no_task?PlanStatus::no_task:PlanStatus::deferred,directive};
        }
        const Candidate* match=nullptr;
        for(const auto& c:options)if(same_semantic(c.key,selected.task.key)){match=&c;break;}
        if(!match){cancel_pending();return {PlanStatus::stale};}
        // Refresh only contact geometry for the committed role. Utility changes
        // do not steal a still-useful commitment.
        const bool preserve_contact=repair&&route.retains(selected.task.key);
        if(!preserve_contact&&!owner.refresh_contact(*match)){cancel_pending();return {PlanStatus::unavailable};}
        selected.task=owner.task();
        const auto started=route.start(fields.take_origin(),selected.task.key,{selected.task.anchor},repair);
        frozen={};candidates={};have_frozen=false;
        if(started.status!=Travel::planning) {
            stage=Stage::field;
            return {started.status==Travel::capacity?PlanStatus::capacity:PlanStatus::unavailable,selected,started};
        }
        stage=Stage::extract;
    }
    if(!owner.task().present||owner.task().key!=selected.task.key){cancel_pending();return {PlanStatus::stale};}
    auto progress=route.continue_plan(turn.epoch(),scene.economy.self.pos,writes);
    turn.check();if(scene.economy.self.epoch!=turn.epoch())throw TurnExpired{};
    if(progress.status==Travel::planning)return {PlanStatus::planning,selected,progress};
    stage=Stage::field;
    const auto ready=progress.status==Travel::ready||progress.status==Travel::at_goal;
    return {ready?PlanStatus::ready:progress.status==Travel::stale?PlanStatus::stale:
        progress.status==Travel::capacity?PlanStatus::capacity:PlanStatus::unavailable,selected,progress};
}
}
