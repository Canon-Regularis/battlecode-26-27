#pragma once
#include <cambc.h>
#include "model.h"
#include "ally_occupancy.h"
namespace lp {
using namespace cambc;
inline int id(const champion& c) {return int(static_cast<handle_champion_t>(c));}
inline int cheb(vec2 a,vec2 b) {return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
inline bitboard around(vec2 p,int r) {bitboard b;b.draw_chebyshev(p,r);return b;}
inline bool channel(const champion& c) {return c.is_recalling()||c.is_submitting_gems()||c.is_teleporting();}
inline bool ready(const ability& a) {
    const auto& info=a.info();
    return info&&a.is_ready()&&(!std::visit([](const auto& v){return v.exclusive_with_movement;},*info)||self().can_move());
}
struct Snapshot {
    occupancy::Batch allies_owned;
    int round=0;
    vec2 pos{};
    float hp=0,max_hp=1,incoming=0;
    int bag=0, enemies=0,friends=1;
    bool alive=false,spawn=false,camp_hit=false;
    bitboard visible,blocked,risk;
    std::vector<champion> foes,allies;
};
extern occupancy::Cache camp_occupancy;
void configure_camp_occupancy(const std::vector<champion>&);
occupancy::Attempt prepare_camp_occupancy(const Snapshot&,bool normal_attempt);
bitboard static_blocked();
const Snapshot& observe();
void invalidate_observations();
bool move_checked(vec2);
unsigned observation_version();
float incoming_at(vec2 p,const std::vector<champion>& enemies);
}
