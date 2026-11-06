#include "economic_runtime_sdk.h"
#include <algorithm>
#include <cmath>
namespace lp {
namespace {
int distance(economic::Point a,economic::Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
bool bank_task(economic::Purpose p){return p==economic::Purpose::convert||p==economic::Purpose::observe_access;}
std::uint64_t mix(std::uint64_t a,std::uint64_t b){return (a^b)*1099511628211ull;}
}
std::pair<std::uint64_t,bool> EconomicRuntime::support(const economic::Scene& s,economic::Key key,const action::Ledger& ledger)const {
    using namespace economic;
    std::uint64_t fact=1469598103934665603ull;
    if(bank_task(key.purpose)) {
        if(key.object<0||key.object>=int(s.altars.size()))return {fact,false};
        const auto altar=s.altars[key.object];
        bool safe=bank_position_safe(s),lock=false;unsigned vacancy=0;
        const int range=constants::submit_gems_range;
        if(range<0||range>3)return {fact,false};
        // A changed observation epoch is not evidence. Fingerprint actual
        // altar visibility, physical stands and currently certified safety.
        for(int dy=-range;dy<=range;++dy)for(int dx=-range;dx<=range;++dx) {
            const Point p{altar.x+dx,altar.y+dy};
            if(p!=altar&&s.physical(p))vacancy++;
            fact=mix(fact,(s.seen(p)?1u:0u)|(s.physical(p)?2u:0u));
        }
        for(const auto& l:s.locks)if(l.pos==altar&&!l.allied)lock=true;
        fact=mix(fact,safe);fact=mix(fact,s.seen(altar));fact=mix(fact,lock);
        const Task task{key,Phase::access,{},Evidence::unknown,Reason::none,true};
        const auto choice=choose_bank(s,task,ledger);
        fact=mix(fact,unsigned(choice.stop));
        return {fact?fact:1,(choice.stop==BankStop::action)||
            (choice.stop==BankStop::approach&&safe&&s.seen(altar)&&vacancy&&!lock)};
    }
    const auto choice=select_service(s,{key},ledger);
    fact=mix(fact,unsigned(choice.stop));
    if(choice.stop==ServiceStop::action) {
        fact=mix(fact,unsigned(choice.request.op));fact=mix(fact,unsigned(choice.request.target.key));
        fact=mix(fact,unsigned(choice.request.target.slot));
    }
    return {fact?fact:1,choice.stop==ServiceStop::action||choice.stop==ServiceStop::holding};
}
void EconomicRuntime::blocked(const economic::Scene& s,economic::Key key,economic::Stop stop,economic::Reason reason,const action::Ledger& ledger) {
    const auto fact=support(s,key,ledger).first;
    auto it=std::find_if(failures.begin(),failures.end(),[&](const auto& f){return f.key==key&&f.reason==reason;});
    if(it!=failures.end())it->support=fact;
    else if(failures.size()<economic::Owner::capacity)failures.push_back({key,reason,fact});
    else owner.capacity_failed=true;
    record(key,stop,reason,fact);
}
void EconomicRuntime::reopen(const economic::Scene& s,LiveTurn& turn) {
    if(!s.economy.complete||!s.economy.self.alive||s.economy.self.channel!=economic::Channel::none)return;
    // One bounded revalidation per dispatch. Never run hundreds of service
    // folds merely because the durable failure ledger contains old options.
    if(!failures.empty()) {
        failure_cursor%=unsigned(failures.size());auto it=failures.begin()+failure_cursor;
        if(!bank_task(it->key.purpose)&&it->key.object>=0&&it->key.object<int(s.groups.size())&&
            s.groups[it->key.object].observation.fresh&&s.groups[it->key.object].observation.cycle!=it->key.cycle) {
            failures.erase(it);return;
        }
        const auto current=support(s,it->key,turn.ledger());
        turn.check();if(s.economy.self.epoch!=turn.epoch())throw TurnExpired{};
        if(current.second&&current.first!=it->support&&owner.reopen({it->key,it->reason,current.first,true})) {
            planner.route.reopen(it->key,it->reason,current.first);failures.erase(it);
        } else ++failure_cursor;
    }
}
void EconomicRuntime::record(economic::Key key,economic::Stop stop,economic::Reason reason,std::uint64_t fact,bool work,float damage) {
    if(execution==UINT64_MAX)throw TurnDeferred{};
    economic::Execution result;result.event=++execution;result.key=key;result.stop=stop;result.reason=reason;result.fact=fact;
    result.owned_bracket=work;result.actual_damage=damage;owner.apply(result);
}
std::vector<economic::Candidate> EconomicRuntime::winning_starts(const economic::Scene& s,LiveTurn& turn) {
    using namespace economic;std::vector<Candidate> options;const auto& own=s.economy.self;
    if(!s.economy.complete||!own.alive||own.channel!=Channel::none||own.score>=constants::winning_gems||
        own.bag<constants::winning_gems-own.score||turn.ledger().submit_attempted||!bank_position_safe(s))return options;
    for(unsigned i=0;i<s.altars.size();++i) {
        const auto p=s.altars[i];if(!s.seen(p)||distance(p,own.pos)>constants::submit_gems_range)continue;
        bool enemy_lock=false;for(const auto& lock:s.locks)if(lock.pos==p&&!lock.allied)enemy_lock=true;
        if(enemy_lock)continue;
        Candidate c;c.key={int(i),0,own.pos.y*s.width+own.pos.x,Purpose::convert,Role::carrier};c.anchor=own.pos;
        c.approach=c.service=c.recipient=c.conversion=Evidence::ready;c.conditional=false;c.winning_start=true;
        Task task{c.key,Phase::access,c.anchor,Evidence::ready,Reason::none,true};
        const auto choice=choose_bank(s,task,turn.ledger());
        if(choice.stop==BankStop::action&&(choice.request.op==action::Op::submit||choice.request.op==action::Op::lock_use))options.push_back(c);
    }
    return options;
}
bool EconomicRuntime::wait_access(const economic::Scene& s,const economic::Task& task) {
    if(task.key.object<0||task.key.object>=int(s.altars.size())||s.altars.size()>queues.size()||!bank_position_safe(s))return false;
    return queues[task.key.object].wait(s,unsigned(task.key.object),constants::submit_gems_range);
}
void EconomicRuntime::recover_now(const economic::Scene& scene,World& world,Memory& memory,TurnBudget& budget,
        RecoveryRuntime& cache,LiveTurn& turn,Telemetry& stats) {
    planner.cancel_pending();needs_plan=false;memory.recovering=owner.health_recovery();
    memory.state=memory.recovering?State::healing:State::escape;
    auto outcome=recover(memory.recovering?recovery::Intent::health:recovery::Intent::evasion,world,memory,budget,cache,turn);
    stats.moves+=outcome.moves+outcome.dashes;
    if(outcome.stop_dispatch())++stats.defers;
    if(outcome.status==recovery::Status::stale)++stats.stale;
    if(outcome.status==recovery::Status::channeling)memory.state=State::recall;
    else if(outcome.status==recovery::Status::reached_spawn)memory.state=State::healing;
    (void)scene; // recovery captures its own current owned scene under the shared ledger
}
void EconomicRuntime::play(World& world,Memory& memory,TurnBudget& budget,RecoveryRuntime& recovery,
        LiveTurn& turn,Telemetry& stats) {
    using namespace economic;
    scalar_writes=0;
    Key executed_key;bool executed=false,eligible=false,productive=false;
    const int dispatch_round=turn.ledger().origin.round;
    auto finalize=[&]() noexcept {
        if(!executed)return;
        try {
            const auto state=planner.route.finish_execution(executed_key,dispatch_round,eligible,productive);
            if(state.status==Travel::exhausted)record(executed_key,Stop::exhausted,Reason::route);
            else if(state.status==Travel::capacity)owner.capacity_failed=true;
        }catch(...){owner.capacity_failed=true;}
    };
    struct Finalize {decltype(finalize)& run;~Finalize()noexcept{run();}} finalizer{finalize};
    auto scene=capture.capture(world,turn,owner.task().present&&!bank_task(owner.task().key.purpose)?owner.task().key.object:-1);
    auto finish_optional=[&](){economic_ward(scene,owner.task(),turn);};
    if(!scene.economy.self.alive) {
        if(memory.was_alive) {
            ++memory.life;if(!turn.ledger().reconcile_life(memory.life))return;
            scene.economy.self.epoch=turn.epoch();planner.cancel_pending();planner.route.invalidate_life();needs_plan=false;
        }
        memory.was_alive=false;memory.state=State::dead;owner.update(scene.economy,{},false);
        natural_shop(memory,turn);++stats.dwell[int(memory.state)];return;
    }
    memory.was_alive=true;
    reopen(scene,turn);
    auto directive=owner.update(scene.economy,winning_starts(scene,turn),false);
    if(directive.decision==Decision::protected_channel){memory.state=scene.economy.self.channel==Channel::submit?State::bank:State::recall;++stats.dwell[int(memory.state)];return;}
    if(directive.decision==Decision::recovery){recover_now(scene,world,memory,budget,recovery,turn,stats);return;}
    if(directive.decision==Decision::capacity)return;
    const bool changed=natural_shop(memory,turn);
    if(directive.decision==Decision::healing){memory.state=State::healing;++stats.dwell[int(memory.state)];return;}
    if(!priority_set)initialize_priority(world.slot,turn,priority_set);
    if(changed||scene.economy.self.epoch!=turn.epoch())scene=capture.capture(world,turn,owner.task().present&&!bank_task(owner.task().key.purpose)?owner.task().key.object:-1);
    // Four shared primitives, one optional carried-lock use and one submission
    // are the structural maximum. Every continuation requires a fresh scene.
    for(unsigned decision=0;decision<=6;++decision) {
        turn.check();
        directive=owner.update(scene.economy,winning_starts(scene,turn),false);
        if(directive.decision==Decision::protected_channel){memory.state=State::bank;return;}
        if(directive.decision==Decision::recovery){recover_now(scene,world,memory,budget,recovery,turn,stats);return;}
        if(directive.decision==Decision::healing){memory.state=State::healing;return;}
        if(directive.decision==Decision::capacity||directive.decision==Decision::dead)return;
        RouteResult next;
        if(directive.task.present)next=planner.route.next(directive.task.key,scene.economy.self.pos);
        if(!directive.task.present||needs_plan||next.status==Travel::blocked||next.status==Travel::stale) {
            // A stationary productive action may run before a replacement field.
            // It has the same owner and does not abandon useful camp progress.
            bool local_action=false;
            if(directive.task.present) {
                if(bank_task(directive.task.key.purpose)) {
                    const auto local=choose_bank(scene,directive.task,turn.ledger());
                    local_action=local.stop==BankStop::action||local.stop==BankStop::channel||local.stop==BankStop::complete;
                } else if(!needs_plan) {
                    const auto local=select_service(scene,{directive.task.key},turn.ledger());
                    local_action=local.stop==ServiceStop::action||local.stop==ServiceStop::holding;
                }
            }
            if(!local_action) {
                auto planned=planner.prepare(world,scene,owner,turn,scalar_writes,!needs_plan&&directive.task.present);
                if(planned.status!=PlanStatus::ready) {
                    if(planned.status==PlanStatus::exposed)recover_now(scene,world,memory,budget,recovery,turn,stats);
                    else if(planned.route.status==Travel::exhausted&&planned.directive.task.present)
                        record(planned.directive.task.key,Stop::exhausted,Reason::route);
                    else if(planned.status==PlanStatus::capacity)owner.capacity_failed=true;
                    else ++stats.defers;
                    return;
                }
                directive=planned.directive;next=planned.route;needs_plan=false;
            }
        }
        if(!directive.task.present)return;
        memory.task=bank_task(directive.task.key.purpose)?-1:directive.task.key.object;
        memory.altar=bank_task(directive.task.key.purpose)?directive.task.key.object:-1;
        memory.state=bank_task(directive.task.key.purpose)?State::prepare_bank:State::capture;
        ++stats.dwell[int(memory.state)];
        executed=true;executed_key=directive.task.key;
        eligible=!scene.economy.self.completed&&!scene.economy.self.stunned;
        action::Result issued;action::Request request;bool have_action=false;
        if(bank_task(directive.task.key.purpose)) {
            const auto choice=choose_bank(scene,directive.task,turn.ledger());
            if(choice.stop==BankStop::action){request=choice.request;issued=perform_bank(scene,choice,turn);have_action=true;}
            else if(choice.stop==BankStop::approach) {
                if(next.status==Travel::ready) {
                    ServiceChoice motion;motion.stop=ServiceStop::action;
                    motion.request={turn.epoch(),action::Op::step,{-1,next.next.x,next.next.y,-1,directive.task.key.object,0,directive.task.key.contact},true};
                    if(!scene.physical(next.next)||!bank_position_safe(scene)) {
                        needs_plan=true;return;
                    }
                    // Fresh quiet landing is required as well as current safety.
                    bool safe=true;
                    for(const auto& e:scene.enemies)if(e.alive&&distance(e.pos,next.next)<=e.range+e.move_range)safe=false;
                    for(const auto& c:scene.members)if(!c.passive&&distance(c.pos,next.next)<=c.range&&
                        ((!c.known)||(c.alive&&c.awake&&c.strength>0)))safe=false;
                    if(!safe){blocked(scene,directive.task.key,Stop::access_unavailable,Reason::unsafe,turn.ledger());return;}
                    request=motion.request;issued=perform_service(scene,motion,turn);have_action=true;
                } else if(next.status==Travel::at_goal) {
                    if(wait_access(scene,directive.task)){record(directive.task.key,Stop::holding);return;}
                    blocked(scene,directive.task.key,Stop::access_unavailable,Reason::access,turn.ledger());needs_plan=false;return;
                } else {needs_plan=true;return;}
            } else if(choice.stop==BankStop::channel)return;
            else if(choice.stop==BankStop::allowance)return finish_optional();
            else if(choice.stop==BankStop::complete){record(directive.task.key,Stop::group_settled);return;}
            else {blocked(scene,directive.task.key,Stop::access_unavailable,choice.stop==BankStop::unsafe?Reason::unsafe:Reason::access,turn.ledger());return;}
        } else {
            const auto choice=select_service(scene,{directive.task.key,next.next,next.status==Travel::ready,false},turn.ledger());
            if(choice.stop==ServiceStop::holding){record(directive.task.key,Stop::holding);return finish_optional();}
            if(choice.stop==ServiceStop::action){request=choice.request;issued=perform_service(scene,choice,turn);have_action=true;}
            else if(choice.stop==ServiceStop::allowance||choice.stop==ServiceStop::cooldown)return finish_optional();
            else if(choice.stop==ServiceStop::incomplete){eligible=false;return;}
            else if(choice.stop==ServiceStop::unsafe||choice.stop==ServiceStop::unknown_wake||choice.stop==ServiceStop::unsupported) {
                blocked(scene,directive.task.key,Stop::blocked,choice.stop==ServiceStop::unsafe?Reason::unsafe:choice.stop==ServiceStop::unknown_wake?Reason::hidden:Reason::unsupported,turn.ledger());
                return;
            } else {needs_plan=true;return;}
        }
        if(!have_action||!issued.event||issued.stop==action::Stop::denied){eligible=false;return;}
        turn.check();const auto before=std::move(scene);
        scene=capture.capture(world,turn,!bank_task(directive.task.key.purpose)?directive.task.key.object:-1);
        bool work=false;float damage=0;
        for(const auto& old:before.members)if(old.group==directive.task.key.object&&old.visible&&old.hp_known)
            for(const auto& now:scene.members)if(now.key==old.key&&now.hp_known&&now.hp<old.hp) {
                damage+=old.hp-now.hp;work=true;break;
            }
        if(bank_task(directive.task.key.purpose))for(const auto& old:before.locks)if(!old.allied&&old.pos==before.altars[directive.task.key.object]) {
            const auto current=std::find_if(scene.locks.begin(),scene.locks.end(),[&](const auto& l){return !l.allied&&l.pos==old.pos;});
            if(scene.seen(old.pos)&&(current==scene.locks.end()||current->hits<old.hits))work=true;
        }
        productive|=work;
        const bool started=scene.economy.self.channel==Channel::submit;
        if(!turn.ledger().observe(issued.event,turn.epoch(),started,false,work))return;
        if(request.op==action::Op::step||request.op==action::Op::dash) {
            const bool charged=turn.ledger().charge_contact(issued.event);
            planner.route.motion(issued.event,directive.task.key,before.economy.self.pos,scene.economy.self.pos,issued.accepted(),true,charged);
            if(issued.accepted()) {++stats.moves;planner.cancel_pending();}
            else needs_plan=true;
        }
        if(started){record(directive.task.key,Stop::channel_started);memory.state=State::bank;return;}
        if(work)record(directive.task.key,Stop::work,Reason::none,0,true,damage);
        if(issued.stop!=action::Stop::accepted)return;
    }
    economic_ward(scene,owner.task(),turn);
}
}
