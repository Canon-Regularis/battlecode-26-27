#include "route_plan.h"
#include "loop_planner.h"
#include <iostream>
#include <numeric>
#include <span>
#include <tuple>

namespace lp {
namespace {
constexpr unsigned draft_reserve=1000000;
struct DraftCamp {map::camp_group group;vec2 anchor;bitboard approach;float hp;double risk;int spawn,index;};
bitboard expanded(bitboard tiles) {
    auto out=tiles|tiles.shift_right(1)|tiles.shift_right(-1);
    return out|out.shift_up(1)|out.shift_up(-1);
}
int nearest(const std::vector<std::uint16_t>& field,const bitboard& tiles,int width) {
    int best=65535;for(auto p:tiles.positions())best=std::min(best,int(field[p.y*width+p.x]));
    return best==65535?-1:best;
}
std::vector<std::uint16_t> distances(const bitboard& blocked,bitboard roots) {
    distance_field field;bitboard reached;field.compute(blocked,roots&~blocked,reached);return field.export_linear_buffer();
}
double risk_at(int own,int enemy) {
    if(own<0)return enemy<0?.5:1.;if(enemy<0)return 0.;
    return double(own)/(own+enemy+1);
}
void byte(std::vector<std::uint8_t>& out,int n){out.push_back(std::uint8_t(n));}
void word(std::vector<std::uint8_t>& out,int n){byte(out,n);byte(out,n>>8);}
}

void prepare_draft_routes() {
    // Submit a valid empty fallback before any expensive work. Draft remains identical.
    std::vector<std::uint8_t> packet{'S','L','P',1,0};draft_memory=packet;
    const auto initial=fuel_remaining();
    auto blocked=static_blocked();int width=blocked.width();
    auto own=distances(blocked,map::spawn_region(team::ally));
    auto enemy=distances(blocked,expanded(map::spawn_region(team::enemy)));
    auto groups=map::camp_groups();std::vector<DraftCamp> all;
    for(auto& g:groups) {
        auto tiles=g.spawn_tiles();auto positions=tiles.positions();
        auto anchor=*std::min_element(positions.begin(),positions.end(),[](auto a,auto b){return std::tie(a.y,a.x)<std::tie(b.y,b.x);});
        float hp=0;for(const auto& c:g.camps())hp+=c.base_stats().base_health;
        auto approach=expanded(tiles)&~blocked;int spawn=nearest(own,approach,width);
        double risk=0;for(auto p:positions){int a=own[p.y*width+p.x],e=enemy[p.y*width+p.x];risk+=risk_at(a==65535?-1:a,e==65535?-1:e);}
        all.push_back({g,anchor,approach,hp,risk/positions.size(),spawn,0});
    }
    // Canonical IDs agree with World::init, including unreachable groups.
    std::sort(all.begin(),all.end(),[](const auto& a,const auto& b){return std::tie(a.anchor.y,a.anchor.x)<std::tie(b.anchor.y,b.anchor.x);});
    for(int i=0;i<int(all.size());++i)all[i].index=i;
    std::erase_if(all,[](const auto& c){return c.spawn<0;});
    std::stable_sort(all.begin(),all.end(),[](const auto& a,const auto& b){
        auto priority=[](const auto& c){return (c.group.gem_value()+.02*c.group.gold_value())/(c.spawn+c.hp/60+8)*(1-.8*c.risk);};
        return priority(a)>priority(b);
    });
    if(all.size()>24)all.erase(all.begin()+24,all.end());
    std::vector<vec2> altars=map::altars().positions();
    std::stable_sort(altars.begin(),altars.end(),[&](auto a,auto b){return nearest(own,around(a,1),width)<nearest(own,around(b,1),width);});
    if(altars.size()>4)altars.resize(4);
    subhan::Inputs data;std::vector<vec2> retained_altars;
    for(auto p:altars) {
        if(fuel_remaining()<draft_reserve+400000)break;
        auto field=distances(blocked,around(p,1));std::vector<int> row;
        for(const auto& c:all)row.push_back(nearest(field,c.approach,width));
        if(std::all_of(row.begin(),row.end(),[](int d){return d<0;}))continue;
        data.altar_distances.push_back(std::move(row));retained_altars.push_back(p);
        auto tiles=around(p,1)&~blocked;
        data.altar_risk.push_back(risk_at(nearest(own,tiles,width),nearest(enemy,tiles,width)));
    }
    std::size_t count=0;
    for(const auto& c:all) {
        if(fuel_remaining()<draft_reserve+800000)break;
        auto field=distances(blocked,c.approach);std::vector<int> row;
        for(const auto& destination:all)row.push_back(nearest(field,destination.approach,width));
        data.distances.push_back(std::move(row));++count;
    }
    all.erase(all.begin()+count,all.end());for(auto& row:data.distances)row.resize(count);for(auto& row:data.altar_distances)row.resize(count);
    if(!count||retained_altars.empty())return;
    for(const auto& c:all){data.spawn_distances.push_back(c.spawn);data.camp_risk.push_back(c.risk);}
    // Our current draft, not the squad assumptions in the original economy bot.
    const std::array types{champion_type::heart_of_ruin,champion_type::marcella,champion_type::vesper_vale,champion_type::ren,champion_type::vendetta};
    subhan::Config cfg;cfg.beam_width=4;cfg.max_camps=5;cfg.max_expansions=768;cfg.report_limit=3;
    for(std::size_t body=0;body<types.size();++body) {
        auto stats=champion(types[body]).base_stats();
        bool caster=types[body]==champion_type::heart_of_ruin||types[body]==champion_type::ren;
        double damage=std::max(1.,double(stats.base_strength+(caster?0:5*stats.strength_growth)+.2*(stats.base_focus+(caster?5*stats.focus_growth:0))));
        data.camps.clear();
        for(const auto& c:all)data.camps.push_back({int(c.group.gem_value()),int(c.group.gold_value()),int(std::ceil(c.hp/damage))+7,c.group.max_respawn_timer()});
        unsigned fuel=fuel_remaining();unsigned share=(fuel>draft_reserve?(fuel-draft_reserve)/(types.size()-body):0);
        auto loops=subhan::find_loops(data,cfg,[&]{return fuel_remaining()<draft_reserve||fuel-fuel_remaining()>=share;});
        if(loops.empty())continue;
        byte(packet,int(types[body]));byte(packet,int(loops.size()));
        for(const auto& loop:loops) {
            byte(packet,int(loop.route.size()));auto altar=retained_altars[loop.altar];byte(packet,altar.x);byte(packet,altar.y);
            for(int index:loop.route)word(packet,all[index].index);
        }
        ++packet[4];draft_memory=packet;
    }
    std::cout<<"SUBHAN_DRAFT candidates="<<all.size()<<" bodies="<<int(packet[4])<<" fuel="<<initial-fuel_remaining()<<" bytes="<<packet.size()<<'\n';
}

void load_draft_routes(World& w) {
    const auto& bytes=draft_memory;std::size_t at=0;
    auto read=[&]()->int {if(at>=bytes.size())throw std::out_of_range("route packet truncated");return std::to_integer<unsigned>(bytes[at++]);};
    if(bytes.size()<5||read()!='S'||read()!='L'||read()!='P'||read()!=1)return;
    int bodies=read();if(bodies>13)return;
    for(int i=0;i<bodies;++i) {
        int type=read(),routes=read();if(routes>3)return;
        for(int j=0;j<routes;++j) {
            int count=read();read();read();if(count>5)return;std::vector<int> route;
            for(int k=0;k<count;++k){int n=read();n|=read()<<8;if(n>=int(w.camps.size()))return;route.push_back(n);}
            if(type==int(self().champion_name())&&!route.empty())w.loop_routes.push_back(std::move(route));
        }
    }
    // Diversify independently acting bodies without adding allocated team roles.
    if(!w.loop_routes.empty())w.loop_choice=w.slot%w.loop_routes.size();
}
int preferred_loop_camp(World& w,const std::vector<bool>& eligible) {
    if(w.loop_routes.empty())return -1;auto& route=w.loop_routes[w.loop_choice];
    for(int offset=0;offset<int(route.size());++offset) {
        int cursor=(w.loop_cursor+offset)%route.size();int n=route[cursor];
        if(eligible[n]){w.loop_cursor=cursor;return n;}
    }
    return -1;
}
void advance_loop(World& w,int completed) {
    if(w.loop_routes.empty())return;auto& route=w.loop_routes[w.loop_choice];
    if(route[w.loop_cursor]==completed)w.loop_cursor=(w.loop_cursor+1)%route.size();
}
}
