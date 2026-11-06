#include "economic_owner.h"
#include "config.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <tuple>
namespace lp::economic {
namespace {
bool add(std::uint64_t& sum,std::uint64_t value) {
    if(value>UINT64_MAX-sum)return false;
    sum+=value;return true;
}
bool available(Evidence e){return e==Evidence::ready||e==Evidence::unknown;}
Rate rate(const Candidate& c,std::uint64_t bag) {
    if(!c.estimate_priced)return {};
    std::uint64_t time=c.approach_hops;
    if(!add(time,c.work_turns)||!add(time,c.capture_turns))return {};
    std::uint64_t value=c.own_gold;
    if(c.key.purpose!=Purpose::gold) {
        if(!add(time,c.delivery_hops)||!add(time,c.tribute_turns))return {};
        value=bag;if(!add(value,c.own_gems))return {};
    }
    return {value,std::max(std::uint64_t(1),time),true};
}
bool same_mode(Key a,Key b) {
    return a.object==b.object&&a.cycle==b.cycle&&a.purpose==b.purpose&&a.role==b.role;
}
bool valid(const Candidate& c) {
    if(!available(c.approach)||!available(c.service)||!available(c.recipient))return false;
    if(c.key.purpose==Purpose::gems&&!available(c.conversion))return false;
    if((c.key.purpose==Purpose::convert||c.key.purpose==Purpose::observe_access)&&!available(c.conversion))return false;
    return c.key.object>=0;
}
bool bank(const Candidate& c){return c.key.purpose==Purpose::convert||c.key.purpose==Purpose::observe_access;}
bool access_key(Key a,Key b) {
    auto access=[](Purpose p){return p==Purpose::convert||p==Purpose::observe_access;};
    return access(a.purpose)&&access(b.purpose)&&a.object==b.object&&a.cycle==b.cycle&&a.contact==b.contact;
}
bool useful_role(const Candidate& c,const Observation& o) {
    if(bank(c))return true;
    for(const auto& g:o.groups)if(g.object==c.key.object&&g.fresh&&g.cycle==c.key.cycle&&g.life==Life::reward) {
        if(g.self_occupant)return true;
        if(g.allied_holder&&(!g.holder_departing||g.capture_timer<=g.earliest_departure))return false;
    }
    return true;
}
bool tie_less(const Candidate& a,Rate ar,const Candidate& b,Rate br) {
    // BankNow wins an exact rate tie. Conditional access is not a BankNow rate.
    bool ab=bank(a)&&!a.conditional,bb=bank(b)&&!b.conditional;
    if(ab!=bb)return ab;
    return std::tuple{ar.time,a.approach_hops,a.anchor.y,a.anchor.x,a.key.object,a.key.contact}<
           std::tuple{br.time,b.approach_hops,b.anchor.y,b.anchor.x,b.key.object,b.key.contact};
}
}
int compare(Rate a,Rate b) {
    if(!a.priced||!b.priced||!a.time||!b.time)return 0;
    if((!a.value||b.time<=UINT64_MAX/a.value)&&(!b.value||a.time<=UINT64_MAX/b.value)) {
        auto left=a.value*b.time,right=b.value*a.time;
        return left<right?-1:left>right?1:0;
    }
    bool reverse=false;
    for(unsigned i=0;i<128;++i) {
        const auto aq=a.value/a.time,bq=b.value/b.time;
        if(aq!=bq){int order=aq<bq?-1:1;return reverse?-order:order;}
        const auto ar=a.value%a.time,br=b.value%b.time;
        if(!ar||!br) {
            int order=!ar?(!br?0:-1):1;
            return reverse?-order:order;
        }
        a={a.time,ar,true};b={b.time,br,true};reverse=!reverse;
    }
    // Euclid on two uint64 operands terminates in fewer than 128 steps.
    return 0;
}
bool Owner::suppress(Key key,Reason reason,std::uint64_t fact) {
    for(auto& s:suppressed)if(s.key==key&&s.reason==reason) {s.fact=fact;return true;}
    if(suppressed.size()>=capacity){capacity_failed=true;return false;}
    suppressed.push_back({key,reason,fact});return true;
}
bool Owner::excluded(const Candidate& c)const {
    // Changed round, scene revision, new commitment or death never removes an
    // exclusion. Only reopen's addressed positive evidence can do so.
    for(const auto& s:suppressed)if(s.key==c.key||access_key(s.key,c.key))return true;
    return false;
}
bool Owner::reopen(const Change& change) {
    if(!change.positive||change.addresses==Reason::none||!change.fact)return false;
    bool removed=false;
    for(auto it=suppressed.begin();it!=suppressed.end();) {
        if((it->key==change.key||access_key(it->key,change.key))&&it->reason==change.addresses&&it->fact!=change.fact) {
            it=suppressed.erase(it);removed=true;
        } else ++it;
    }
    return removed;
}
bool Owner::refresh_contact(const Candidate& candidate) {
    if(!current.present||!same_mode(current.key,candidate.key)||!valid(candidate)||excluded(candidate))return false;
    current.key.contact=candidate.key.contact;current.anchor=candidate.anchor;
    current.evidence=candidate.conditional?Evidence::unknown:Evidence::ready;
    return true;
}
const GroupObservation* Owner::group(const Observation& o)const {
    for(const auto& g:o.groups)if(g.object==current.key.object)return &g;
    return nullptr;
}
bool Owner::reconcile_task(const Observation& o) {
    if(!current.present)return false;
    if(current.key.purpose==Purpose::convert||current.key.purpose==Purpose::observe_access) {
        if(!o.self.bag){current={};return false;}
        return true;
    }
    const auto* g=group(o);
    if(!g||!g->fresh)return true;
    if(g->cycle!=current.key.cycle||g->life==Life::respawning) {
        current={};return false; // group settled, without claiming our receipt
    }
    if(g->life!=Life::reward)return true;
    if(g->self_occupant) {
        current.key.role=g->contested?Role::defender:Role::holder;
        current.phase=Phase::hold;return true;
    }
    const bool adequate=g->allied_holder&&(!g->holder_departing||g->capture_timer<=g->earliest_departure);
    if(adequate) {
        // Suppress the worker as well as the new recipient role. A subsequent
        // ranking pass cannot recreate the same unneeded helper immediately.
        suppress(current.key,Reason::role_satisfied,g->role_fact);
        current={};return false;
    }
    current.key.role=g->allied_holder?Role::takeover:Role::recipient;
    current.phase=Phase::contact;return true;
}
void Owner::apply(const Execution& result) {
    if(!result.event||result.event<=last_execution)return;
    last_execution=result.event;
    if(result.owned_bracket) {
        if(std::isfinite(result.actual_damage)&&result.actual_damage>0)confirmed_damage+=result.actual_damage;
        if(result.observed_gold_receipt)++observed_gold_receipts;
        if(result.observed_gem_receipt)++observed_gem_receipts;
    }
    if(!current.present||!same_mode(result.key,current.key))return;
    switch(result.stop) {
    case Stop::group_settled:current={};break;
    case Stop::blocked:case Stop::unsupported:case Stop::exhausted:case Stop::access_unavailable:
        suppress(current.key,result.reason==Reason::none?Reason::exhausted:result.reason,result.fact);
        current={};break;
    case Stop::holding:current.phase=Phase::hold;break;
    case Stop::work:current.phase=Phase::service;break;
    case Stop::channel_started:current.phase=Phase::deliver;break;
    // Cooldown, spent allowance and resource/epoch deferral cannot consume a
    // semantic option, erase partial work or renew an attempt.
    default:break;
    }
}
Directive Owner::update(const Observation& o,const std::vector<Candidate>& candidates,bool complete_options) {
    Directive out;
    const auto& self=o.self;
    if(!o.complete){out.decision=Decision::deferred;out.task=current;out.needs_conversion=held_bag>0;return out;}
    held_bag=self.bag;out.needs_conversion=held_bag>0;
    if(observed) {
        if(previous.bag>self.bag) {
            if(!self.alive)out.disposition=Disposition::loss;
            else if(previous.channel==Channel::submit&&self.score>previous.score)
                out.disposition=Disposition::possible_deposit;
            else out.disposition=Disposition::unknown;
        } else if(previous.bag!=self.bag||previous.gold!=self.gold)out.disposition=Disposition::resources_changed;
    }
    previous=self;observed=true;
    if(!self.alive){out.decision=Decision::dead;out.task=current;return out;}
    if(!std::isfinite(self.hp)||!std::isfinite(self.max_hp)||self.hp<0||self.max_hp<=0) {
        out.decision=Decision::deferred;out.task=current;return out;
    }
    if(self.hp<=self.max_hp*Config::recovery_low)recovering=true;
    if(self.hp>=self.max_hp*Config::recovery_high)recovering=false;
    // Submission and teleport ownership precede low-HP/danger recovery.
    if(self.channel==Channel::submit||self.channel==Channel::teleport) {
        out.decision=Decision::protected_channel;out.task=current;return out;
    }
    if(recovering||self.danger||self.channel==Channel::recall) {
        if(current.present)current.phase=Phase::suspended;
        out.decision=(self.spawn&&recovering&&!self.danger&&self.channel==Channel::none)?Decision::healing:Decision::recovery;
        out.task=current;return out;
    }
    if(capacity_failed){out.decision=Decision::capacity;out.task=current;return out;}
    // A positively observed new group cycle retires obsolete exclusions. Fog
    // alone never supplies a new cycle number or retires an attempt.
    for(const auto& g:o.groups)if(g.fresh&&g.cycle>=0)
        suppressed.erase(std::remove_if(suppressed.begin(),suppressed.end(),[&](auto s){
            if(s.key.purpose==Purpose::convert||s.key.purpose==Purpose::observe_access||s.key.object!=g.object)return false;
            if(s.key.cycle!=g.cycle)return true;
            const bool inadequate=!g.allied_holder||(g.holder_departing&&g.capture_timer>g.earliest_departure);
            return s.reason==Reason::role_satisfied&&g.life==Life::reward&&inadequate&&g.role_fact&&g.role_fact!=s.fact;
        }),suppressed.end());
    for(const auto& c:candidates)if(bank(c)&&held_bag>0&&c.winning_start&&
        !c.conditional&&c.conversion==Evidence::ready&&valid(c)&&!excluded(c)) {
        current={c.key,Phase::access,c.anchor,Evidence::ready,Reason::none,true};
        out.decision=Decision::task;out.task=current;return out;
    }
    reconcile_task(o);
    if(current.present) {
        if(current.phase==Phase::suspended)current.phase=Phase::contact;
        out.decision=Decision::task;out.task=current;return out;
    }
    if(!complete_options){out.decision=Decision::deferred;return out;}
    const Candidate *winner=nullptr,*unpriced=nullptr,*access=nullptr;
    Rate winning;
    bool have_gem_candidate=false;
    for(const auto& c:candidates)if(valid(c)&&useful_role(c,o)&&!excluded(c)&&c.key.purpose==Purpose::gems&&c.own_gems>0)
        have_gem_candidate=true;
    // A carried bag gets finite untried access work before conditional new
    // gem farming. Exhausted access then permits independent earned-gold work.
    bool bankable=false;
    for(const auto& c:candidates)if(bank(c)&&valid(c)&&!excluded(c)&&held_bag>0) {
        if(c.key.purpose==Purpose::convert&&!c.conditional&&c.conversion==Evidence::ready)bankable=true;
        if(!access||std::tuple{c.approach_hops,c.anchor.y,c.anchor.x,c.key.object,c.key.contact}<
                    std::tuple{access->approach_hops,access->anchor.y,access->anchor.x,access->key.object,access->key.contact})access=&c;
        if(c.winning_start&&!c.conditional&&c.conversion==Evidence::ready){winner=&c;break;}
    }
    if(!winner&&held_bag>0&&!bankable&&access)winner=access;
    if(!winner)for(const auto& c:candidates) {
        if(!valid(c)||!useful_role(c,o)||excluded(c))continue;
        if(bank(c)) {if(!held_bag||c.conditional||c.conversion!=Evidence::ready)continue;}
        else if(c.key.purpose==Purpose::gems) {
            if(!o.has_altars||!c.own_gems||(held_bag&&!bankable))continue;
        } else if(c.key.purpose==Purpose::gold) {
            if(!c.own_gold||(o.has_altars&&have_gem_candidate&&(!held_bag||bankable)))continue;
        } else continue;
        const auto r=rate(c,held_bag);
        if(!r.priced) {
            if(!unpriced||std::tuple{c.anchor.y,c.anchor.x,c.key.object,c.key.contact}<
                          std::tuple{unpriced->anchor.y,unpriced->anchor.x,unpriced->key.object,unpriced->key.contact})unpriced=&c;
            continue;
        }
        if(!winner||compare(r,winning)>0||(compare(r,winning)==0&&tie_less(c,r,*winner,winning))) {
            winner=&c;winning=r;
        }
    }
    if(!winner)winner=unpriced;
    if(winner) {
        current={winner->key,bank(*winner)?Phase::access:Phase::contact,
                 winner->anchor,winner->conditional?Evidence::unknown:Evidence::ready,Reason::none,true};
        out.decision=Decision::task;out.task=current;
    }
    return out;
}
}
