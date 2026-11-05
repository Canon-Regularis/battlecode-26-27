#include "recovery.h"
#include <array>
#include <cmath>
#include <queue>
namespace lp::recovery {
namespace {
constexpr std::array<Point,8> directions{{{-1,-1},{0,-1},{1,-1},{-1,0},{1,0},{-1,1},{0,1},{1,1}}};
Point add(Point a,Point b){return {a.x+b.x,a.y+b.y};}
bool valid(const Scene& s) {
    if(!s.terrain)return false;
    const auto& t=*s.terrain;int n=t.width*t.height;
    return t.width>0&&t.height>0&&n<=Limits::cells&&t.inside(s.pos)&&
        int(t.blocked.size())==n&&int(t.spawn.size())==n&&int(t.home.size())==n&&
        int(s.visible.size())==n&&int(s.occupied.size())==n&&s.enemies.size()<=Limits::enemies&&
        s.camps.size()<=Limits::camps&&s.groups<=Limits::groups;
}
float risk(const Scene& s,Point p,bool response=false) {
    float v=0;for(auto e:s.enemies)if(distance(e.pos,p)<=e.range+(response?1:0))v+=e.strength;
    if(!response)for(auto c:s.camps)if(c.known&&c.alive&&c.awake&&distance(c.pos,p)<=c.range)v+=c.strength;
    return v;
}
struct Effect {bool known=true;std::vector<int> waking;};
Effect effect(const Scene& s,Point p) {
    Effect e;if(!s.dash.damage&&!s.dash.stun)return e;
    for(int y=p.y-s.dash.radius;y<=p.y+s.dash.radius;++y)
        for(int x=p.x-s.dash.radius;x<=p.x+s.dash.radius;++x) {
            Point q{x,y};if(s.terrain->inside(q)&&!s.visible[s.terrain->index(q)]){e.known=false;return e;}
        }
    // All enemy passive/retaliation interactions are initially unsupported.
    for(auto foe:s.enemies)if(distance(foe.pos,p)<=s.dash.radius){e.known=false;return e;}
    std::array<bool,Limits::groups> hit{};
    for(auto c:s.camps)if(c.known&&c.alive&&distance(c.pos,p)<=s.dash.radius) {
        if(c.group<0||c.group>=s.groups){e.known=false;return e;}
        hit[c.group]=true;
    }
    for(int i=0;i<int(s.camps.size());++i){auto c=s.camps[i];
        if(c.group>=0&&c.group<s.groups&&hit[c.group]) {
            if(!c.known||(!s.dash.damage&&s.dash.stun)){e.known=false;return e;}
            if(c.alive&&!c.awake&&c.strength>0)e.waking.push_back(i);
        }
    }
    return e;
}
float extra(const Scene& s,const Effect& e,Point p){float v=0;for(int i:e.waking){auto c=s.camps[i];if(distance(c.pos,p)<=c.range)v+=c.strength;}return v;}
struct Feature {float present=0,response=0;int nearest=100000;};
struct Features {
    Point origin;std::array<Feature,49> values{};
    explicit Features(const Scene& s):origin(s.pos) {
        for(int dy=-3;dy<=3;++dy)for(int dx=-3;dx<=3;++dx) {
            Point p{s.pos.x+dx,s.pos.y+dy};if(!s.terrain->inside(p))continue;
            auto& f=values[(dy+3)*7+dx+3];f.present=risk(s,p);f.response=risk(s,p,true);
            for(auto e:s.enemies)f.nearest=std::min(f.nearest,distance(p,e.pos));
        }
    }
    const Feature& at(Point p)const{return values[(p.y-origin.y+3)*7+p.x-origin.x+3];}
};
using Rank=std::tuple<float,float,int,int,float,int,int,int,int,int,int>;
Rank rank(const Scene& s,const Features& features,Point p,float present,float worst,int count,Action first,Point second) {
    const auto& f=features.at(p);
    return {present,f.response,s.terrain->home[s.terrain->index(p)],-f.nearest,worst,count,
        first.target.x,first.target.y,int(first.kind),second.x,second.y};
}
std::vector<Point> endpoints(const Scene& s,Point from,int range) {
    std::vector<Point> out;
    for(int dy=-range;dy<=range;++dy)for(int dx=-range;dx<=range;++dx) {
        Point p{from.x+dx,from.y+dy};if(p==from||!s.physical(p,s.pos))continue;
        bool connected=distance(p,from)==1;
        if(!connected)for(auto d:directions){Point mid=add(from,d);if(distance(mid,p)==1&&s.physical(mid,s.pos)){connected=true;break;}}
        if(connected)out.push_back(p);
    }return out;
}
struct HomePath {bool found=false,complete=true;Point first;};
HomePath faster_home(const Scene& s) {
    struct Node{Point p,first;int depth;};std::vector<Node> queue{{s.pos,s.pos,0}};
    std::vector<unsigned char> seen(s.visible.size());seen[s.terrain->index(s.pos)]=1;
    int edges=0;
    for(unsigned head=0;head<queue.size();++head) {
        auto n=queue[head];if(n.depth>=std::min(5,s.timer-(s.movement_spent?1:0)))continue;
        for(auto d:directions) {
            if(++edges>Limits::bfs_edges)return {false,false,{}};
            Point p=add(n.p,d);if(!s.physical(p,s.pos))continue;int i=s.terrain->index(p);
            if(seen[i])continue;
            seen[i]=1;
            if(risk(s,p)>0||risk(s,p,true)>0)continue;
            Point first=n.depth?n.first:p;
            if(s.terrain->spawn[i])return {true,true,first};
            if(queue.size()>=Limits::bfs_nodes)return {false,false,{}};
            queue.push_back({p,first,n.depth+1});
        }
    }return {};
}
void latch(const Scene& s,Memory& m){if(s.hp<=s.max_hp*Config::recovery_low)m.recovering=true;if(s.hp>=s.max_hp*Config::recovery_high)m.recovering=false;}
bool movable(const Scene& s){return s.alive&&!s.completed&&!s.stunned&&!s.recalling&&!s.tribute&&!s.teleport;}
}
Plan select_plan(const Scene& s,bool allow_step,bool allow_dash) {
    Plan best;if(!valid(s)){best.complete=false;return best;}
    const Features features(s);
    const float origin=features.at(s.pos).present;auto score=rank(s,features,s.pos,origin,0,0,{},s.pos);
    bool step=movable(s)&&allow_step&&s.can_move&&!s.move_restricted;
    bool dash=movable(s)&&allow_dash&&s.can_cast&&!s.move_restricted&&!s.cast_restricted&&
        s.dash.available&&s.dash.supported&&s.dash.range>=1&&s.dash.range<=2&&s.dash.radius<=Limits::effect_radius;
    // Cache effect results once per possible landing (the local 7x7 square).
    std::array<Effect,49> effects;std::array<bool,49> computed{};
    auto get_effect=[&](Point p)->const Effect&{int i=(p.y-s.pos.y+3)*7+p.x-s.pos.x+3;
        if(!computed[i]){effects[i]=effect(s,p);computed[i]=true;if(!effects[i].known)++best.effect_unknown;}return effects[i];};
    int raw=1;
    auto consider=[&](Action first,Point end,int count,float prefix,const Effect* e) {
        if(++raw>Limits::candidates){best.complete=false;return;}
        float terminal=features.at(end).present+(e?extra(s,*e,end):0);
        float worst=std::max(prefix,terminal);if(worst>origin){++best.risk_rejections;return;}
        auto r=rank(s,features,end,terminal,worst,count,first,end);
        if(r<score){score=r;best.first=first;best.actions=count;}
    };
    auto steps=step?endpoints(s,s.pos,1):std::vector<Point>{};
    for(auto p:steps)consider({Kind::step,p},p,1,0,nullptr);
    if(dash)for(auto p:endpoints(s,s.pos,s.dash.range)) {
        const auto& e=get_effect(p);if(!e.known)continue;
        Action a{Kind::dash,p,s.dash.slot};float prefix=features.at(p).present+extra(s,e,p);
        consider(a,p,1,0,&e);
        if(step)for(auto q:endpoints(s,p,1))consider(a,q,2,prefix,&e);
    }
    if(dash)for(auto p:steps) {
        float prefix=features.at(p).present;
        for(auto q:endpoints(s,p,s.dash.range)) {
            const auto& e=get_effect(q);if(e.known)consider({Kind::step,p},q,2,prefix,&e);
        }
    }
    best.raw=raw;return best;
}
Outcome execute(Intent intent,Memory& memory,Backend& backend) {
    Outcome out;
    try {
    Epoch start=backend.epoch();Scene s;
    auto finish=[&](Status status){out.status=status;return out;};
    auto same_turn=[&]{auto e=backend.epoch();return e.actor==start.actor&&e.life==start.life&&e.round==start.round;};
    auto refresh=[&]()->Status {
        if(!same_turn())return Status::stale;
        if(out.captures>=Limits::captures)return Status::incomplete;
        ++out.captures;Scene fresh;auto status=backend.capture(fresh);
        if(status!=Status::ready)return status;
        if(!same_turn()||!backend.current(fresh.epoch))return Status::stale;
        if(!valid(fresh))return Status::incomplete;
        s=std::move(fresh);latch(s,memory);return Status::ready;
    };
    auto status=backend.prepare(start);if(status!=Status::ready)return finish(status);
    if((status=refresh())!=Status::ready)return finish(status);
    bool step_attempted=false,dash_attempted=false,suppress_recall=s.recall_started||s.recall_cancelled;
    auto issue=[&](Action a)->int {
        if(!backend.current(s.epoch))return -1;
        bool success=backend.issue(s,a);
        // Record completed work once even if the host action rolled into a new round.
        if(success){out.history.push_back(a);if(a.kind==Kind::step)++out.moves;if(a.kind==Kind::dash)++out.dashes;
            if(a.kind==Kind::cancel)++out.cancellations;
            if(a.kind==Kind::recall)++out.recall_starts;}
        if(!same_turn())return -1;
        return success?1:0;
    };
    if(s.tribute||s.teleport||!s.alive||s.completed)return finish(Status::defensive_wait);
    if(s.recalling) {
        HomePath path;
        if(risk(s,s.pos)==0&&risk(s,s.pos,true)==0) {
            path=faster_home(s);if(!backend.current(s.epoch))return finish(Status::stale);
            if(!path.complete)return finish(Status::incomplete);
            if(!path.found)return finish(Status::channeling);
        }
        // Never attempt a second cancellation, including after reentry within this round.
        if(s.recall_cancelled||s.stunned)return finish(Status::channeling);
        int result=issue({Kind::cancel,{}});suppress_recall=true;
        if(result<0)return finish(Status::stale);
        if(!result)return finish(Status::blocked);
        if((status=refresh())!=Status::ready)return finish(status);
        if(path.found) {
            out.homeward=true;
            if(!movable(s)||!s.can_move||s.move_restricted)return finish(Status::cancelled_wait);
            if(!s.physical(path.first,s.pos)||risk(s,path.first)>0||risk(s,path.first,true)>0)return finish(Status::partial);
            step_attempted=true;++out.motion_attempts;
            result=issue({Kind::step,path.first});
            if(result<0)return finish(Status::stale);
            if(!result)return finish(Status::blocked);
            if((status=refresh())!=Status::ready)return finish(status);
        }
    }
    for(int iteration=0;iteration<2&&!out.homeward;++iteration) {
        if(!movable(s))break;
        auto plan=select_plan(s,!step_attempted,!dash_attempted);out.candidates+=plan.raw;out.effect_unknown+=plan.effect_unknown;out.risk_rejections+=plan.risk_rejections;
        if(!backend.current(s.epoch))return finish(Status::stale);
        if(!plan.complete)return finish(Status::incomplete);
        if(!plan.actions)break;
        if(plan.first.kind==Kind::step)step_attempted=true;else dash_attempted=true;
        ++out.motion_attempts;int result=issue(plan.first);
        if(result<0)return finish(Status::stale);
        if(!result)return finish(Status::blocked);
        if((status=refresh())!=Status::ready)return finish(status);
    }
    if(!backend.current(s.epoch))return finish(Status::stale);
    if(movable(s)) {
        bool acted=backend.defend(s);if(acted)++out.defenses;
        if(!same_turn())return finish(Status::stale);
        if(acted&&(status=refresh())!=Status::ready)return finish(status);
    }
    if(!backend.current(s.epoch))return finish(Status::stale);
    if(s.spawn())return finish(memory.recovering?Status::reached_spawn:Status::recovered);
    // Intent is the entry adapter's explanation; only fresh observed HP can enable health recall.
    (void)intent;
    if(memory.recovering&&s.hp<s.max_hp*Config::recovery_high&&movable(s)&&!s.stunned&&
        !suppress_recall&&!s.recall_started&&s.enemies.empty()&&risk(s,s.pos)==0) {
        int result=issue({Kind::recall,{}});
        if(result<0)return finish(Status::stale);
        if(!result)return finish(Status::blocked);
        if((status=refresh())!=Status::ready)return finish(status);
        return finish(s.recalling?Status::channeling:Status::partial);
    }
    if(!memory.recovering&&intent==Intent::health)return finish(Status::recovered);
    return finish(out.moves+out.dashes+out.cancellations?Status::partial:
        s.stunned||s.completed?Status::defensive_wait:Status::no_improvement);
    } catch(const Halt& halt) {out.status=halt.status;return out;}
}
}
