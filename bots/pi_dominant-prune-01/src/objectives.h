#pragma once
#include "navigation.h"
namespace lp {
struct Objective {
    map::camp_group group;
    vec2 anchor;
    bitboard tiles;
    bitboard approach;
    int seen=-1000, respawn=0, cooldown=0, capture_timer=5;
    int lifecycle=0; // 0 unknown, 1 living, 2 reward, 3 respawning
    float remaining=0,design_health=0;
};
struct World {
    std::vector<Objective> camps;
    std::vector<vec2> altars;
    std::vector<int> altar_retry;
    std::vector<champion> roster;
    std::vector<int> preference;
    std::vector<std::vector<int>> loop_routes;
    int loop_choice=0,loop_cursor=0;
    int dominant_gem_camp=-1;
    int slot=0,width=0,height=0,columns=0,rows=0;
    int refreshed_round=-1;unsigned refreshed_version=0;
    void init();
    void refresh(const Snapshot&,Memory&);
    int chunk(vec2 p) const;
    vec2 center(int chunk) const;
};
bitboard camp_goals(const Objective&,const Snapshot&);
int choose_camp(World&,const Snapshot&,TurnBudget&,bool distance_only=false,bool bootstrap=false);
int choose_altar(World&,const Snapshot&,TurnBudget&,int previous=-1);
bool explore(World&,TurnBudget&,Memory&);
}
