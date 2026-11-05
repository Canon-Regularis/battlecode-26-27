#include "navigation.h"
#include "camp_topology_access.h"
#include "dash_witness.h"
#include <tuple>
namespace lp {
RouteStatus move_to(bitboard goals,bool safe,TurnBudget& budget,Memory& mem,CampTopologyView topology,bool constrained) {
    auto& me=cambc::self();if(!budget.current()||!me.is_alive()||channel(me)||!me.can_move()) return RouteStatus::wait;
    const auto& s=observe();auto blocked=s.blocked;
    std::vector<VisibleCamp> camps;
    if(safe) {
        blocked|=s.risk;
        if(!capture_camps(camps,blocked,budget,!constrained))return RouteStatus::deferred;
    }
    blocked.set(s.pos,false);goals&=~blocked;
    if(goals.is_empty()) {++mem.blocked;return RouteStatus::invalid_goals;}
    if(goals.is_set(s.pos)) return RouteStatus::at_goal;
    if(!budget.admit()) return RouteStatus::deferred;
    distance_field field;bitboard reached;auto root=around(s.pos,0);++budget.fields;
    field.compute_to(blocked,goals,root,reached);
    if(!budget.current()) return RouteStatus::deferred;
    if(!reached.is_set(s.pos)) {
        ++mem.blocked;
        if(mem.blocked>=3&&!constrained) {
            bool yield=false;for(const auto& a:s.allies) if(id(a)<id(me)&&cheb(a.position(),s.pos)<=2) yield=true;
            if(yield&&mem.blocked%5>=3) {
                for(auto p:blocked.reachable_tiles(s.pos,1).positions()) if(p!=s.pos&&cheb(p,s.pos)==1&&incoming_at(p,s.foes)<=s.incoming) {
                    if(!action_current(budget))return RouteStatus::deferred;
                    if(move_checked(p)) {invalidate_observations();return RouteStatus::moved;}
                    break;
                }
            }
        }
        return RouteStatus::no_route_now;
    }
    auto origin_distance=field.get(s.pos);auto best=s.pos;auto score=std::tuple{origin_distance,s.pos.y,s.pos.x};
    for(auto p:blocked.reachable_tiles(s.pos,1).positions()) {
        auto v=std::tuple{field.get(p),p.y,p.x};if(v<score&&field.get(p)<origin_distance){best=p;score=v;}
    }
    // Restrict dashes to the same walking-connected mask. This conservative subset is always a legal dash path.
    if(!constrained&&me.can_cast()) for(const auto& a:me.abilities()) if(a.is_dash()&&ready(a)) {
        auto range=int(a.get<ability_dash>().range);auto end=s.pos;int dist=origin_distance;
        for(auto p:blocked.reachable_tiles(s.pos,range).positions()) if(p!=s.pos&&field.get(p)<dist&&cheb(p,s.pos)<=range) {end=p;dist=field.get(p);}
        if(end!=s.pos&&dist<int(origin_distance)-1) {
            if(!budget.current()||fuel_remaining()<Config::reserve)return RouteStatus::deferred;
            if(safe) {
                auto decision=dash_witness(a,end,camps,topology,budget);
                if(decision==DashCheck::deferred)return RouteStatus::deferred;
                if(decision!=DashCheck::clear)break; // Keep the original ordinary best.
            }
            if(!action_current(budget))return RouteStatus::deferred;
            if(a.use(end)) {invalidate_observations();mem.blocked=0;mem.last_distance=dist;return RouteStatus::moved;}
            return RouteStatus::wait;
        }
    }
    if(!action_current(budget))return RouteStatus::deferred;
    if(best==s.pos){++mem.blocked;return RouteStatus::no_route_now;}
    if(move_checked(best)){invalidate_observations();mem.blocked=0;mem.last_distance=field.get(best);return RouteStatus::moved;}
    invalidate_observations();++mem.blocked;
    // Hidden blockers reveal themselves. A fresh field may try one different step.
    if(budget.fields<Config::max_fields&&me.can_move()&&budget.admit()) return move_to(goals,safe,budget,mem,topology,true);
    return RouteStatus::wait;
}
bool retreat(TurnBudget& budget,Memory& mem,CampTopologyView topology) {
    const auto& s=observe();auto& me=cambc::self();auto goals=map::spawn_region(team::ally);
    if(move_to(goals,true,budget,mem,topology)==RouteStatus::moved) return true;
    if(!action_current(budget)||!me.can_move()) return false;
    auto spawn=map::spawn_region(team::ally).positions();if(spawn.empty()) return false;
    auto rank=[&](vec2 p){int nearest=1000;for(auto& e:s.foes)nearest=std::min(nearest,cheb(p,e.position()));return std::tuple{incoming_at(p,s.foes),-nearest,cheb(p,spawn.front())};};
    auto best=s.pos;auto score=rank(best);
    for(auto p:s.blocked.reachable_tiles(s.pos,1).positions()) if(rank(p)<score){best=p;score=rank(p);}
    if(!action_current(budget))return false;
    if(best!=s.pos) {bool moved=move_checked(best);invalidate_observations();return moved;}return false;
}
}
