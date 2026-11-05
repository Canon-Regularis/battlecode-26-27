#include "feature_flags.h"
#if PARTY_FEATURE_MASK & (1ULL<<16)
#include "combat.h"
#include "strategy_policy.h"
#include <iostream>
namespace lp {
void feature_ward(const World& w,int task,TurnBudget& budget,const Memory& memory) {
    auto& me=self();if(!Config::wards||!me.is_alive()||channel(me)||me.ward_cooldown()>0||fuel_remaining()<Config::ward_fuel||me.restrictions().contains(buff_restrictions::ward))return;
    const auto& s=observe();if(s.hp<s.max_hp*Config::recovery_high||s.enemies>0)return;
    static distance_field approach;static bool ready_field=false;
    static vec2 placed_from{-1000,-1000};static int placed_task=-2;
    auto positions=me.ward_positions();
    int objective=memory.altar>=0?1000+memory.altar:memory.carrier>=0?2000+memory.pending_altar:task;
    if(!positions.empty()&&cheb(s.pos,placed_from)<6&&placed_task==objective)return;
    if(!ready_field){
        if(!budget.admit())return;
        auto spawn=map::spawn_region(team::enemy);bitboard goals;
        for(auto p:spawn.positions())goals|=around(p,1);
        auto blocked=static_blocked();goals&=~blocked;if(goals.is_empty())return;
        bitboard reached;++budget.fields;approach.compute(blocked,goals,reached);
        if(!budget.current())return;ready_field=true;
    }
    auto anchor=memory.altar>=0?w.altars[memory.altar]:memory.carrier>=0?w.altars[memory.pending_altar]:task>=0?w.camps[task].anchor:s.pos;
    auto blocked=static_blocked();vec2 direction{0,0};int best_distance=approach.get(anchor);
    auto spawn=map::spawn_region(team::enemy).positions();if(spawn.empty())return;
    int best_angle=-100000;
    for(auto p:around(anchor,1).positions())if(!blocked.is_set(p)&&approach.get(p)<approach.get(anchor)){
        int d=approach.get(p),angle=(p.x-anchor.x)*(spawn.front().x-anchor.x)+(p.y-anchor.y)*(spawn.front().y-anchor.y);
        if(d<best_distance||(d==best_distance&&angle>best_angle)){best_distance=d;best_angle=angle;direction=p-anchor;}
    }
    if(direction==vec2{0,0})return;
    auto free=me.ward_placement_tiles()&s.visible&~(s.blocked|vision::ward_tiles()|vision::teleport_tiles());
    vec2 best=s.pos;int best_radius=-1,best_cross=0,best_dot=1,coverage=-1,queries=0,scanned=0;
    for(auto p:free.positions()){
        if(++scanned>25)break;
        auto delta=p-s.pos;int dot=delta.x*direction.x+delta.y*direction.y,cross=std::abs(delta.x*direction.y-delta.y*direction.x),radius=cheb(p,s.pos);
        if(!ward_forward(dot,cross))continue;
        bool better=ward_better({radius,cross,dot},{best_radius,best_cross,best_dot});
        bool tie=radius==best_radius&&cross*best_dot==best_cross*dot&&dot==best_dot;
        int cover=-1;
        if((better||tie)&&queries<4&&fuel_remaining()>Config::ward_fuel){cover=(ward::visible_tiles_from(p)&~s.visible).positions().size();++queries;}
        if(better||(tie&&cover>coverage)){best=p;best_radius=radius;best_cross=cross;best_dot=dot;coverage=cover;}
    }
    if(best!=s.pos&&budget.current()&&fuel_remaining()>Config::reserve&&me.place_ward(best)){
        placed_from=s.pos;placed_task=objective;invalidate_observations();
        std::cout<<"LF event=ward_placed round="<<s.round<<" objective="<<task<<" x="<<best.x<<" y="<<best.y<<'\n';
    }
}
}

#endif
