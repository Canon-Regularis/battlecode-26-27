#include "observations.h"
#include <optional>
namespace lp {
occupancy::Cache camp_occupancy;
namespace {std::vector<champion> occupancy_roster;}
void configure_camp_occupancy(const std::vector<champion>& roster) {
    if(!occupancy_roster.empty())return;
    occupancy_roster=roster;std::vector<int> ids;for(const auto& a:roster)ids.push_back(id(a));
    camp_occupancy.configure(ids,id(self()));
}
occupancy::Attempt prepare_camp_occupancy(const Snapshot& s,bool normal_attempt) {
    return camp_occupancy.prepare(s.allies_owned,normal_attempt,[&]{return s.round==int(round_number())&&s.allies_owned.revision==observation_version();},[](int identity)->std::optional<bool>{
        try {for(const auto& a:occupancy_roster)if(id(a)==identity)return a.is_alive();return std::nullopt;}
        catch(const error& e){if(e.code()!=error_code::api_not_in_vision&&e.code()!=error_code::api_not_found)throw;return std::nullopt;}
    });
}
namespace {Snapshot cached;bool valid_cache=false;unsigned revision=1;}
void invalidate_observations(){valid_cache=false;++revision;}
bool move_checked(vec2 p) {
    if(!self().can_move()||self().restrictions().contains(buff_restrictions::move))return false;
    bool moved=false;
    try {moved=self().move_absolute(p);}
    catch(const cambc::error& e) {
        if(e.code()!=error_code::invalid_action_move_bad_destination)throw;
    }
    // A rejected move can reveal an occupant. Always invalidate before retrying.
    invalidate_observations();return moved;
}
unsigned observation_version(){return revision;}
bitboard static_blocked() {return map::walls()|map::holes()|map::altars()|map::spawn_region(team::enemy);}
float incoming_at(vec2 p,const std::vector<champion>& enemies) {
    float d=0;
    for(const auto& e:enemies) if(cheb(e.position(),p)<=e.attack_range()) d+=e.strength();
    for(const auto& c:vision::camps()) if(c.is_alive()&&c.is_awake()&&c.strength()>0&&cheb(c.position(),p)<=c.attack_range()) d+=c.strength();
    return d;
}
const Snapshot& observe() {
    int round=round_number();if(valid_cache&&cached.round==round)return cached;
    const auto epoch=revision;
    Snapshot s;s.round=round;auto& me=cambc::self();s.alive=me.is_alive();
    if(!s.alive){cached=std::move(s);valid_cache=true;return cached;}
    s.pos=me.position();s.hp=me.health();s.max_hp=me.max_health();s.bag=int(me.gem_count());
    s.spawn=map::spawn_region(team::ally).is_set(s.pos);s.visible=vision::visible_tiles();
    s.blocked=static_blocked()|vision::champion_tiles()|vision::camp_tiles()|vision::teleport_tiles();s.blocked.set(s.pos,false);
    s.foes=vision::champions(team::enemy);
    // Same owning tile enumeration as SDK vision::champions, retaining its value positions.
    s.allies_owned.round=round;s.allies_owned.revision=epoch;
    s.allies_owned.width=s.blocked.width();s.allies_owned.height=s.blocked.height();
    const bool batch_current=int(round_number())==round&&revision==epoch;
    for(auto p:vision::champion_tiles(team::ally).positions()) {
        auto a=vision::champion_at(p);s.allies.push_back(a);
        s.allies_owned.positives.push_back({id(a),{p.x,p.y}});
    }
    for(auto p:s.visible.positions())s.allies_owned.visible.push_back({p.x,p.y});
    s.allies_owned.complete=batch_current&&int(round_number())==round&&revision==epoch;
    if(!s.allies_owned.complete)s.allies_owned.positives.clear();
    for(const auto& e:s.foes) {
        if(cheb(s.pos,e.position())<=6) ++s.enemies;
        s.risk|=around(e.position(),e.attack_range()+1);
    }
    for(const auto& a:s.allies) if(id(a)!=id(me)&&a.is_alive()&&!channel(a)&&cheb(s.pos,a.position())<=4) ++s.friends;
    for(const auto& c:vision::camps()) if(c.is_alive()&&c.is_awake()&&c.strength()>0) {
        if(cheb(s.pos,c.position())<=c.attack_range()) s.camp_hit=true;
    }
    s.incoming=incoming_at(s.pos,s.foes);prepare_camp_occupancy(s,false);cached=std::move(s);valid_cache=true;return cached;
}
}
