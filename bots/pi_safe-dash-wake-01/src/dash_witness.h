#pragma once
#include "navigation.h"
namespace lp {
inline bool action_current(const TurnBudget& b) {
    const auto fuel=fuel_remaining();return b.current()&&fuel>=Config::reserve;
}
struct VisibleCamp {
    camp handle;
    bool alive=false,awake=false;
    vec2 position{};
    float strength=0;
    int range=0;
    bool combat_known=false;
};
// State is a value snapshot; camp wrapper getters themselves are live queries.
inline bool capture_camps(std::vector<VisibleCamp>& out,bitboard& blocked,const TurnBudget& b,bool witness) {
    auto visible=vision::camps();
    if(!action_current(b))return false;
    for(const auto& c:visible) {
        if(!action_current(b))return false;
        auto state=c.state();if(!action_current(b))return false;
        VisibleCamp v{c,state.is_alive(),state.is_awake()};
        if(v.alive) {
            if(v.awake) {
                v.strength=c.strength();if(!action_current(b))return false;
                if(v.strength>0) {
                    v.position=c.position();if(!action_current(b))return false;
                    v.range=c.attack_range();if(!action_current(b))return false;
                    v.combat_known=true;blocked|=around(v.position,v.range);
                }
            }
            if(witness&&!v.combat_known) {
                v.position=c.position();if(!action_current(b))return false;
            }
        }
        out.push_back(v);
    }
    return action_current(b);
}
enum class DashCheck { clear, witness, resource, incomplete, deferred };
inline DashCheck dash_witness(const ability& a,vec2 end,std::vector<VisibleCamp>& visible,
                              CampTopologyView topology,const TurnBudget& b) {
    const auto dash=a.get<ability_dash>(); // Immutable SDK metadata, no host query.
    if(dash.modifier<=0||dash.duration<=0)return DashCheck::clear;
    // Establish current-damage scope before admitting the witness scan. A
    // positive modifier with zero current Focus still preserves the dash.
    if(!action_current(b))return DashCheck::deferred;
    auto focus=self().focus();
    if(!action_current(b))return DashCheck::deferred;
    if(focus*dash.modifier<=0)return DashCheck::clear;
    // Fixed experimental admission, not an estimate of engine fuel cost.
    auto fuel=fuel_remaining();
    if(!b.current()||fuel<Config::reserve)return DashCheck::deferred;
    if(fuel<15000)return DashCheck::resource;
    // Reuse the fixed admission bound as a conservative continuation bound:
    // if query work consumes that headroom, keep the ordinary action reserve.
    auto resource_status=[&] {
        auto remaining=fuel_remaining();
        if(!b.current()||remaining<Config::reserve)return DashCheck::deferred;
        return remaining<15000?DashCheck::resource:DashCheck::clear;
    };
    std::vector<const void*> checked;
    bool incomplete=false;
    for(const auto& hit:visible) {
        if(auto status=resource_status();status!=DashCheck::clear)return status;
        if(!hit.alive||cheb(hit.position,end)>dash.radius)continue;
        auto members=topology.members(static_cast<handle_camp_t>(hit.handle));
        if(!members){incomplete=true;continue;}
        if(std::find(checked.begin(),checked.end(),members->identity())!=checked.end())continue;
        checked.push_back(members->identity());
        for(auto& v:visible) {
            if(auto status=resource_status();status!=DashCheck::clear)return status;
            if(!v.alive||v.awake||cheb(v.position,end)<=dash.radius||
               !members->contains(static_cast<handle_camp_t>(v.handle)))continue;
            if(!v.combat_known) {
                v.strength=v.handle.strength();if(auto status=resource_status();status!=DashCheck::clear)return status;
                if(v.strength>0) {
                    v.range=v.handle.attack_range();if(auto status=resource_status();status!=DashCheck::clear)return status;
                }
                v.combat_known=true;
            }
            if(v.strength>0&&cheb(v.position,end)<=v.range)return DashCheck::witness;
        }
    }
    if(auto status=resource_status();status!=DashCheck::clear)return status;
    return incomplete?DashCheck::incomplete:DashCheck::clear;
}
}
