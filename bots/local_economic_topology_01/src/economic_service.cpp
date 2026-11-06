#include "economic_service.h"
#include "config.h"
#include <algorithm>
#include <cmath>
#include <tuple>
#include <type_traits>
namespace lp::economic {
namespace {
int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
struct Endpoint {
    Point pos;
    std::array<bool,128> touched{};
    work::Wide awake,dash,follow,step;
    bool enemy=false,unknown=false,dash_unknown=false,follow_unknown=false,step_unknown=false;
};
struct Threats {
    std::array<Endpoint,25> points{};
    unsigned count=0,contributions=0;
    int dash_slot=-1;
    bool valid=true,capacity=false;
};
int endpoint(Point origin,Point p) {
    const int x=p.x-origin.x+2,y=p.y-origin.y+2;
    if(x<0||y<0||x>=5||y>=5)return -1;
    const int cell=y*5+x;return cell<12?cell+1:cell==12?0:cell;
}
bool connected(const Scene& scene,Point end) {
    const auto origin=scene.economy.self.pos;
    if(!scene.physical(end))return false;
    if(distance(origin,end)==1)return true;
    for(int y=-1;y<=1;++y)for(int x=-1;x<=1;++x)if(x||y) {
        Point middle{origin.x+x,origin.y+y};
        if(scene.physical(middle)&&distance(middle,end)==1)return true;
    }
    return false;
}
Threats threats(const Scene& s,int group,const action::Ledger& ledger) {
    Threats out;const auto origin=s.economy.self.pos;
    out.points[out.count++].pos=origin;
    for(int y=-2;y<=2;++y)for(int x=-2;x<=2;++x)if(x||y)
        out.points[out.count++].pos={origin.x+x,origin.y+y};
    for(unsigned slot=0;slot<s.abilities.size();++slot) {
        const auto& a=s.abilities[slot];
        if(a.kind==AbilityKind::dash&&a.supported&&a.cooldown==0&&s.can_cast&&
            !s.move_restricted&&!ledger.dash_attempted&&!ledger.casts&&!a.exclusive) {
            if(out.dash_slot!=-1){out.dash_slot=-2;break;}
            out.dash_slot=int(slot);
        }
    }
    if(out.dash_slot>=0) {
        const auto& a=s.abilities[out.dash_slot];
        if(a.damaging||a.stunning)for(const auto& c:s.members)if(c.visible&&c.known&&c.alive)
            for(int dy=-a.radius;dy<=a.radius;++dy)for(int dx=-a.radius;dx<=a.radius;++dx) {
                const int p=endpoint(origin,{c.pos.x+dx,c.pos.y+dy});
                if(p>0)out.points[p].touched[c.group]=true;
            }
    }
    work::Domain domain;
    for(auto& p:out.points) {
        for(const auto& e:s.enemies) {
            if(++out.contributions>32768){out.capacity=true;return out;}
            if(e.alive&&distance(e.pos,p.pos)<=e.range+e.move_range)p.enemy=true;
        }
        for(const auto& c:s.members) {
            if(++out.contributions>32768){out.capacity=true;return out;}
            if(c.passive||(c.known&&!c.alive))continue;
            const bool assigned=c.group==group;
            if(!c.known||!c.visible||!c.alive) {
                if(distance(c.pos,p.pos)<=c.range)p.unknown=true;
                if(p.touched[c.group])p.dash_unknown=true;
                if(assigned||p.touched[c.group])p.follow_unknown=true;
                if(assigned)p.step_unknown=true;
                continue;
            }
            if(distance(c.pos,p.pos)>c.range)continue;
            work::Wide strength;
            if(!domain.encode(c.strength,strength)){out.valid=false;return out;}
            if(c.awake) {
                if(!p.awake.add(strength,p.awake)){out.valid=false;return out;}
            } else {
                if(p.touched[c.group]&&!p.dash.add(strength,p.dash)){out.valid=false;return out;}
                if((assigned||p.touched[c.group])&&!p.follow.add(strength,p.follow)){out.valid=false;return out;}
                if(assigned&&!p.step.add(strength,p.step)){out.valid=false;return out;}
            }
        }
        if(!p.dash.add(p.awake,p.dash)||!p.follow.add(p.awake,p.follow)||!p.step.add(p.awake,p.step)) {
            out.valid=false;return out;
        }
    }
    return out;
}
template<class T> struct Arithmetic {
    const work::Domain& domain;bool good=true;
    T atom(float f){T out;if(!domain.encode(f,out))good=false;return out;}
    T add(T a,T b){T out;if(!a.add(b,out))good=false;return out;}
    T subtract(T a,T b){T out;if(!a.subtract(b,out))good=false;return out;}
    T minimum(T a,T b){return a.compare(b)<0?a:b;}
};
struct First {
    action::Op op=action::Op::basic;int key=-1,slot=-1;Point pos;
};
template<class T> struct Plan {
    bool present=false;T work;unsigned removals=0;
    int contact=0;unsigned casts=0,motions=0,operations=0;
    First first;int continuation=-1;
};
template<class T> bool better(const Plan<T>& a,const Plan<T>& b) {
    if(!a.present)return false;
    if(!b.present)return true;
    const int cmp=a.work.compare(b.work);if(cmp)return cmp>0;
    if(a.removals!=b.removals)return a.removals>b.removals;
    if(a.contact!=b.contact)return a.contact>b.contact;
    return std::tuple{a.casts,a.motions,a.operations,a.first.op,a.first.key,a.first.slot,
        a.first.pos.y,a.first.pos.x,a.continuation}<
        std::tuple{b.casts,b.motions,b.operations,b.first.op,b.first.key,b.first.slot,
        b.first.pos.y,b.first.pos.x,b.continuation};
}
template<class T> struct Hit {
    bool present=false;T work;unsigned removals=0;int key=-1;Point pos;
};
template<class T> bool better_hit(const Hit<T>& a,const Hit<T>& b) {
    if(!a.present)return false;
    if(!b.present)return true;
    int cmp=a.work.compare(b.work);if(cmp)return cmp>0;
    return a.removals!=b.removals?a.removals>b.removals:a.key<b.key;
}
bool safe(const Endpoint& p,const work::Wide& hp,const work::Wide& burden,bool unknown) {
    return !p.enemy&&!p.unknown&&!unknown&&hp.compare(burden)>0;
}
template<class T> ServiceChoice fold(const Scene& s,ServiceIntent intent,const action::Ledger& ledger,
                                    const Threats& risk,const work::Domain& domain) {
    Arithmetic<T> math{domain};ServiceChoice out;out.fast_domain=domain.fast;out.contributions=risk.contributions;
    const auto& own=s.economy.self;const auto origin=own.pos;
    work::Wide hp;domain.encode(own.hp,hp);
    const auto& origin_risk=risk.points[0];
    const bool service_safe=safe(origin_risk,hp,origin_risk.step,origin_risk.step_unknown);
    bool unknown=origin_risk.unknown||origin_risk.step_unknown,unsafe=!service_safe;
    const unsigned left=4-ledger.primitives;
    const bool cast=s.can_cast&&!ledger.casts;
    const bool basic=s.can_attack&&ledger.basics<2;
    auto defense=[&](action::Op op,int key,Point pos,int slot) {
        ServiceChoice choice;choice.stop=ServiceStop::action;choice.fast_domain=domain.fast;
        choice.contributions=risk.contributions;
        choice.request={own.epoch,op,{key,pos.x,pos.y,slot,intent.key.object,intent.key.cycle,intent.key.contact},true};
        return choice;
    };
    // Preserve compatible defense priorities. These are actual next actions;
    // no projected absorption/healing is used in any service prefix guard.
    if(cast)for(unsigned slot=0;slot<s.abilities.size();++slot) {
        const auto& a=s.abilities[slot];
        if(!a.supported||a.cooldown||(a.exclusive&&ledger.steps+ledger.dashes>0))continue;
        bool incoming=origin_risk.awake!=work::Wide{};
        for(const auto& e:s.enemies)if(e.alive&&distance(e.pos,origin)<=e.range&&e.strength>0)incoming=true;
        if(a.kind==AbilityKind::shield&&incoming&&own.hp<own.max_hp*0.7f)
            return defense(action::Op::shield,-1,origin,int(slot));
        if(a.kind==AbilityKind::heal&&a.allies&&!a.ground&&a.amount>0) {
            const Champion* target=nullptr;float value=0;
            for(const auto& ally:s.allies)if(ally.alive&&ally.hp<ally.max_hp*0.75f&&distance(ally.pos,origin)<=a.range) {
                float candidate=std::min(a.amount,ally.max_hp-ally.hp);
                double exposure=0;for(const auto& e:s.enemies)if(e.alive&&distance(e.pos,ally.pos)<=e.range)exposure+=e.strength;
                if(exposure>=ally.hp)candidate+=10000;
                if(candidate>value||(candidate==value&&target&&ally.key<target->key)){value=candidate;target=&ally;}
            }
            if(target)return defense(action::Op::heal,target->key,target->pos,int(slot));
        }
    }
    const auto& group=s.groups[intent.key.object].observation;
    if(group.fresh&&group.life==Life::reward&&group.self_occupant) {
        // Leaders' capture control keeps occupying reward tiles while using
        // compatible attacks. Defend in place; never leave a capture to chase.
        const Champion* target=nullptr;
        if(basic)for(const auto& enemy:s.enemies)if(enemy.alive&&enemy.hp>0&&distance(enemy.pos,origin)<=s.attack_range)
            if(!target||std::tuple{enemy.hp,enemy.key}<std::tuple{target->hp,target->key})target=&enemy;
        if(target) {
            out.stop=ServiceStop::action;out.enemy=true;
            out.request={own.epoch,action::Op::basic,{target->key,target->pos.x,target->pos.y,-1,
                intent.key.object,intent.key.cycle,intent.key.contact},true};
        } else out.stop=ServiceStop::holding;
        return out;
    }
    int reset=-1;
    for(unsigned slot=0;slot<s.abilities.size();++slot) {
        const auto& a=s.abilities[slot];
        if(cast&&a.supported&&!a.cooldown&&a.kind==AbilityKind::reset&&
            (!a.exclusive||ledger.steps+ledger.dashes==0)&&reset<0)reset=int(slot);
    }
    Plan<T> best;
    auto keep=[&](Plan<T> plan){if(plan.operations<=left&&better(plan,best))best=plan;};
    auto first=[&](action::Op op,int key,Point p,int slot=-1){return First{op,key,slot,p};};
    auto single=[&](const Hit<T>& h,First action,unsigned casts=0) {
        if(h.present&&h.work.compare(T{})>0)keep({true,h.work,h.removals,0,casts,0,1,action,-1});
    };
    const T basic_amount=math.atom(s.basic);
    Hit<T> prior_basic;
    std::array<Hit<T>,2> prior_spell{};
    std::array<Hit<T>,25> post_basic{};
    std::array<Hit<T>,25> step_basic{};
    std::array<T,25> dash_work{};
    std::array<unsigned,25> dash_removals{};
    std::array<bool,25> dash_hp_unknown{};
    for(const auto& c:s.members)if(c.group==intent.key.object&&c.visible&&c.known&&c.alive) {
        if(!c.hp_known){unknown=true;continue;}
        const T health=math.atom(c.hp);
        if(health.compare(T{})<=0)continue;
        const auto bwork=math.minimum(health,basic_amount);
        Hit<T> b{service_safe&&basic&&distance(c.pos,origin)<=s.attack_range,bwork,
            unsigned(basic_amount.compare(health)>=0),int(c.key),c.pos};
        single(b,first(action::Op::basic,b.key,b.pos));
        if(service_safe&&reset>=0&&ledger.basics<2&&distance(c.pos,origin)<=s.attack_range) {
            if(!basic&&left>=2) {
                if(bwork.compare(T{})>0)keep({true,bwork,unsigned(basic_amount.compare(health)>=0),0,1,0,2,
                    first(action::Op::reset,int(c.key),c.pos,reset),int(c.key)});
            } else if(basic&&ledger.basics==0) {
                auto combined=math.minimum(health,math.add(basic_amount,basic_amount));
                if(bwork.compare(health)<0)keep({true,combined,unsigned(combined.compare(health)>=0),0,1,0,3,
                    first(action::Op::basic,int(c.key),c.pos),int(c.key)});
                if(prior_basic.present)keep({true,math.add(bwork,prior_basic.work),b.removals+prior_basic.removals,
                    0,1,0,3,first(action::Op::basic,prior_basic.key,prior_basic.pos),int(c.key)});
                if(prior_basic.present)keep({true,math.add(bwork,prior_basic.work),b.removals+prior_basic.removals,
                    0,1,0,3,first(action::Op::basic,int(c.key),c.pos),prior_basic.key});
            }
        }
        for(unsigned slot=0;slot<s.abilities.size();++slot) {
            const auto& a=s.abilities[slot];
            auto pair=[&](const Hit<T>& bh,const Hit<T>& sh) {
                if(!bh.present||!sh.present||left<2)return;
                const auto value_pair=math.add(bh.work,sh.work);
                keep({true,value_pair,bh.removals+sh.removals,0,1,0,2,
                    first(action::Op::basic,bh.key,bh.pos),sh.key});
                keep({true,value_pair,bh.removals+sh.removals,0,1,0,2,
                    first(action::Op::cast,sh.key,sh.pos,int(slot)),bh.key});
            };
            // The current target need not be spell-reachable for its basic
            // to pair with an earlier spell-reachable distinct target.
            pair(b,prior_spell[slot]);
            if(!service_safe||!cast||!a.supported||a.cooldown||!a.camps||a.ground||
                (a.kind!=AbilityKind::damage&&a.kind!=AbilityKind::cc)||
                (a.exclusive&&(ledger.steps+ledger.dashes>0))||distance(c.pos,origin)>a.range)continue;
            const auto amount=math.atom(a.amount),value=math.minimum(health,amount);
            Hit<T> spell{true,value,unsigned(amount.compare(health)>=0),int(c.key),c.pos};
            if(value.compare(T{})<=0)continue;
            single(spell,first(action::Op::cast,spell.key,spell.pos,int(slot)),1);
            if(b.present&&left>=2) {
                const auto combined=math.minimum(health,math.add(basic_amount,amount));
                if(b.work.compare(health)<0)keep({true,combined,unsigned(combined.compare(health)>=0),0,1,0,2,
                    first(action::Op::basic,b.key,b.pos),spell.key});
                if(spell.work.compare(health)<0)keep({true,combined,unsigned(combined.compare(health)>=0),0,1,0,2,
                    first(action::Op::cast,spell.key,spell.pos,int(slot)),b.key});
            }
            if(basic&&left>=2) {
                pair(prior_basic,spell);
            }
            if(better_hit(spell,prior_spell[slot]))prior_spell[slot]=spell;
        }
        if(better_hit(b,prior_basic))prior_basic=b;
        for(unsigned p=1;p<risk.count;++p) {
            if(distance(c.pos,risk.points[p].pos)<=s.attack_range) {
                Hit<T> hit{true,bwork,unsigned(basic_amount.compare(health)>=0),int(c.key),c.pos};
                if(better_hit(hit,step_basic[p]))step_basic[p]=hit;
            }
            T remaining=health;
            if(risk.dash_slot>=0) {
                const auto& a=s.abilities[risk.dash_slot];
                if(a.damaging&&distance(c.pos,risk.points[p].pos)<=a.radius) {
                    const auto value=math.minimum(health,math.atom(a.amount));
                    dash_work[p]=math.add(dash_work[p],value);
                    dash_removals[p]+=unsigned(value.compare(health)>=0);
                    remaining=math.subtract(health,value);
                }
            }
            if(distance(c.pos,risk.points[p].pos)<=s.attack_range&&remaining.compare(T{})>0) {
                Hit<T> hit{true,math.minimum(basic_amount,remaining),unsigned(basic_amount.compare(remaining)>=0),int(c.key),c.pos};
                if(better_hit(hit,post_basic[p]))post_basic[p]=hit;
            }
        }
    }
    // Unknown assigned HP in a dash footprint cannot silently disappear from
    // its nominal work, unlike unrelated incidental groups used only for risk.
    if(risk.dash_slot>=0)for(const auto& c:s.members)if(c.group==intent.key.object&&c.visible&&c.alive&&!c.hp_known)
        for(unsigned p=1;p<risk.count;++p)if(distance(c.pos,risk.points[p].pos)<=s.abilities[risk.dash_slot].radius)dash_hp_unknown[p]=true;
    for(unsigned p=1;p<risk.count;++p) {
        const auto& point=risk.points[p];const int d=distance(origin,point.pos);
        if(!s.physical(point.pos))continue;
        const bool contact=intent.has_contact&&point.pos==intent.contact;
        const bool awake_safe=safe(point,hp,point.awake,false);
        const bool quiet=awake_safe&&point.awake==work::Wide{};
        const bool step_safe=safe(point,hp,point.step,point.step_unknown);
        if(d==1&&s.can_move&&s.move_range>=1&&!ledger.step_attempted&&ledger.steps+ledger.dashes<2) {
            // A ranged walk spends the basic; only an available reset can
            // support the priced walk -> reset -> basic continuation.
            const bool after_basic=ledger.basics<2&&step_basic[p].present&&
                ((!s.ranged&&basic)||(s.ranged&&reset>=0&&!s.abilities[reset].exclusive));
            const unsigned casts=s.ranged?1:0,operations=s.ranged?3:2;
            if(awake_safe&&step_safe&&after_basic&&step_basic[p].work.compare(T{})>0&&operations<=left)
                keep({true,step_basic[p].work,step_basic[p].removals,contact?1:0,casts,1,operations,
                    first(action::Op::step,-1,point.pos),step_basic[p].key});
            else if(contact&&quiet)keep({true,T{},0,1,0,1,1,first(action::Op::step,-1,point.pos),-1});
            unknown|=point.step_unknown;unsafe|=!awake_safe||!step_safe;
        }
        if(risk.dash_slot<0||!cast||ledger.dash_attempted||ledger.steps+ledger.dashes>=2)continue;
        const auto& dash=s.abilities[risk.dash_slot];
        if(d>dash.range||!connected(s,point.pos)||dash_hp_unknown[p])continue;
        const bool dash_safe=safe(point,hp,point.dash,point.dash_unknown);
        const bool follow_safe=safe(point,hp,point.follow,point.follow_unknown);
        unknown|=point.dash_unknown||point.follow_unknown;
        unsafe|=!dash_safe;
        if(!dash_safe)continue;
        const auto begin=first(action::Op::dash,-1,point.pos,risk.dash_slot);
        if(dash_work[p].compare(T{})>0||(contact&&quiet))
            keep({true,dash_work[p],dash_removals[p],contact?1:0,1,1,1,begin,-1});
        if(basic&&post_basic[p].present&&follow_safe&&left>=2)
            keep({true,math.add(dash_work[p],post_basic[p].work),dash_removals[p]+post_basic[p].removals,
                contact?1:0,1,1,2,begin,post_basic[p].key});
    }
    if(!math.good){out.stop=ServiceStop::unsupported;return out;}
    if(best.present) {
        out.stop=ServiceStop::action;
        out.request={own.epoch,best.first.op,{best.first.key,best.first.pos.x,best.first.pos.y,best.first.slot,
            intent.key.object,intent.key.cycle,intent.key.contact},true};
        if constexpr(std::is_same_v<T,work::Wide>)out.nominal_work=best.work;
        else if(!domain.canonical(best.work,out.nominal_work)){out.stop=ServiceStop::unsupported;return out;}
        out.removals=best.removals;return out;
    }
    out.stop=unknown?ServiceStop::unknown_wake:unsafe?ServiceStop::unsafe:
        !basic&&!cast?ServiceStop::allowance:ServiceStop::no_contact;
    return out;
}
}
ServiceChoice select_service(const Scene& s,ServiceIntent intent,const action::Ledger& ledger) {
    ServiceChoice out;
    if(!s.economy.complete||!ledger.current(s.economy.self.epoch)||!s.economy.self.alive||
        s.economy.self.completed||s.economy.self.stunned||s.economy.self.channel!=Channel::none||
        s.economy.self.danger||intent.recovering||
        s.economy.self.hp<=s.economy.self.max_hp*Config::recovery_low){out.stop=ServiceStop::incomplete;return out;}
    if(s.members.size()>256||s.groups.size()>128||s.enemies.size()>32||s.allies.size()>32||
        ledger.primitives>4||ledger.basics>2||ledger.casts>1||ledger.steps>1||ledger.dashes>1||ledger.steps+ledger.dashes>2) {
        out.stop=ServiceStop::capacity;return out;
    }
    if(ledger.primitives==4||ledger.service_rejections>=2){out.stop=ServiceStop::allowance;return out;}
    if(intent.key.object<0||intent.key.object>=int(s.groups.size())){out.stop=ServiceStop::incomplete;return out;}
    const auto& group=s.groups[intent.key.object].observation;
    if((group.fresh&&group.cycle>=0&&group.cycle!=intent.key.cycle)||s.economy.self.max_hp<=0||
        s.attack_range<0||s.attack_range>16384){out.stop=ServiceStop::incomplete;return out;}
    for(const auto& c:s.members)if(c.group<0||c.group>=int(s.groups.size())||c.range<0||c.range>16384) {
        out.stop=ServiceStop::incomplete;return out;
    }
    for(const auto& e:s.enemies)if(e.range<0||e.move_range<0||e.range>16384||e.move_range>16384) {
        out.stop=ServiceStop::incomplete;return out;
    }
    for(const auto& a:s.abilities)if(a.supported&&a.kind==AbilityKind::dash&&
        (a.range<1||a.range>2||a.radius<0||a.radius>1)){out.stop=ServiceStop::unsupported;return out;}
    work::Domain domain;domain.observe(s.basic);domain.observe(s.economy.self.hp);
    domain.observe(s.economy.self.max_hp);
    for(const auto& a:s.abilities)if(a.supported)domain.observe(a.amount);
    for(const auto& c:s.members) {
        if(c.hp_known)domain.observe(c.hp);
        if(c.known&&c.alive&&!c.passive)domain.observe(c.strength);
    }
    if(!domain.valid){out.stop=ServiceStop::unsupported;return out;}
    const auto risk=threats(s,intent.key.object,ledger);
    if(!risk.valid){out.stop=ServiceStop::unsupported;return out;}
    if(risk.capacity){out.stop=ServiceStop::capacity;return out;}
    if(domain.fast)return fold<work::Small>(s,intent,ledger,risk,domain);
    return fold<work::Wide>(s,intent,ledger,risk,domain);
}
}
