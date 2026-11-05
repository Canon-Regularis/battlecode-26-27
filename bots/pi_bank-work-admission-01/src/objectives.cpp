#include "objectives.h"
#include "route_plan.h"
#include <numeric>
#include <iostream>
#include <tuple>
namespace lp {
void World::init() {
    if(!roster.empty())return;
    roster=champions(team::ally);std::sort(roster.begin(),roster.end(),[](auto a,auto b){return id(a)<id(b);});
    for(int i=0;i<int(roster.size());++i)if(id(roster[i])==id(self()))slot=i;
    auto groups=map::camp_groups();
    for(auto& g:groups) {
        auto tiles=g.spawn_tiles();auto positions=tiles.positions();auto p=*std::min_element(positions.begin(),positions.end(),[](auto a,auto b){return std::tie(a.y,a.x)<std::tie(b.y,b.x);});
        float health=0;for(const auto& c:g.camps())health+=c.base_stats().base_health;
        bitboard approach=tiles;
        approach|=tiles.shift_right(1);approach|=tiles.shift_right(-1);
        auto horizontal=approach;approach|=horizontal.shift_up(1);approach|=horizontal.shift_up(-1);
        camps.push_back({g,p,tiles,approach,-1000,0,0,5,0,health,health});
    }
    std::sort(camps.begin(),camps.end(),[](auto& a,auto& b){return std::tie(a.anchor.y,a.anchor.x)<std::tie(b.anchor.y,b.anchor.x);});
    altars=map::altars().positions();std::sort(altars.begin(),altars.end(),[](auto a,auto b){return std::tie(a.y,a.x)<std::tie(b.y,b.x);});
    altar_retry.resize(altars.size());
    auto b=map::walls();width=b.width();height=b.height();columns=(width+14)/15;rows=(height+14)/15;
    preference.resize(roster.size());std::iota(preference.begin(),preference.end(),0);
    auto rank=[&](int i){auto t=roster[i].champion_name();int r=t==champion_type::heart_of_ruin?0:t==champion_type::ren?1:t==champion_type::marcella?2:3;
        return std::tuple{r,-champion(t).base_stats().base_health,i};};
    std::sort(preference.begin(),preference.end(),[&](int a,int b){return rank(a)<rank(b);});
    load_draft_routes(*this);
}
int World::chunk(vec2 p) const {return (p.y*rows/height)*columns+p.x*columns/width;}
vec2 World::center(int n) const {
    int x=n%columns,y=n/columns;
    return {((x*width+columns-1)/columns+((x+1)*width+columns-1)/columns-1)/2,
            ((y*height+rows-1)/rows+((y+1)*height+rows-1)/rows-1)/2};
}
void World::refresh(const Snapshot& s,Memory& mem) {
    if(refreshed_round==s.round&&refreshed_version==observation_version())return;
    refreshed_round=s.round;refreshed_version=observation_version();
    for(int i=0;i<int(camps.size());++i) {
        auto& o=camps[i];
        // Reserve movement fuel: only the committed objective needs per-action detail.
        if(i!=mem.task&&(s.round+i)%8!=0)continue;
        if((o.tiles&s.visible).is_empty())continue;
        int old=o.lifecycle,oldtimer=o.capture_timer;float hp=o.remaining;
        auto state=o.group.state();o.seen=s.round;
        if(auto p=std::get_if<map::camp_group_respawning>(&state)){o.lifecycle=3;o.respawn=s.round+p->timer;}
        else if(std::holds_alternative<map::camp_group_reward_available>(state)) {o.lifecycle=2;o.remaining=0;o.capture_timer=o.group.capture_state().timer;}
        else {
            o.lifecycle=1;o.remaining=0;
            if(i==mem.task)for(const auto& c:o.group.camps())o.remaining+=c.is_visible()?(c.is_alive()?c.health():0):c.base_stats().base_health;
            else o.remaining=o.design_health;
        }
        if(i==mem.task&&((o.remaining<hp)||(o.lifecycle==2&&old!=2)||(o.capture_timer<oldtimer)))mem.progressed=s.round;
    }
}
bitboard camp_goals(const Objective& o,const Snapshot& s) {
    if(o.lifecycle==2) return o.tiles&~s.blocked;
    if(o.seen!=s.round)return o.approach&~s.blocked;
    bitboard goals;auto& me=self();
    bool visible=false;
    for(const auto& c:o.group.camps())if(c.is_visible()&&c.is_alive()) {goals|=around(c.position(),me.attack_range());visible=true;}
    if(!visible)for(auto p:o.tiles.positions())goals|=around(p,1);
    return goals&~s.blocked;
}
int choose_camp(World& w,const Snapshot& s,TurnBudget& b,bool distance_only,bool bootstrap) {
    if(!b.admit()||b.fields>=1)return -2;
    distance_field f;bitboard reached;auto blocked=s.blocked|s.risk;blocked.set(s.pos,false);++b.fields;f.compute(blocked,around(s.pos,0),reached);
    if(!b.current())return -2;
    auto distances=f.export_linear_buffer();
    float damage=std::max(1.0f,self().strength()+self().focus()*0.2f);
    std::vector<vec2> allypositions;for(const auto& a:s.allies)if(id(a)!=id(self()))allypositions.push_back(a.position());
    int best=-1,best_distance=65535;std::int64_t bestvalue=-1,bestcost=1;
    bool needgold=bootstrap;
    std::vector<bool> eligible(w.camps.size());
    for(int i=0;i<int(w.camps.size());++i) {
        auto& o=w.camps[i];if(o.cooldown>s.round)continue;
        int d=65535;
        for(auto p:o.approach.positions())d=std::min(d,int(distances[p.y*w.width+p.x]));
        if(d==65535)continue;
        if(o.lifecycle==3&&o.respawn>s.round+d)continue;
        int altar=50;for(auto p:w.altars)altar=std::min(altar,cheb(o.anchor,p));
        float hp=o.lifecycle==2?0:(o.lifecycle==1&&o.seen==s.round?o.remaining:o.design_health);

        int clear=int(std::ceil(hp/damage));int gems=int(o.group.gem_value());
        if(clear>Config::max_clear)continue;
        eligible[i]=true;
        std::int64_t value=needgold?o.group.gold_value()*10:gems*300+o.group.gold_value();
        std::int64_t cost=std::max(1,d+clear+5+(gems?altar+(gems+9)/10:0));
        if(distance_only){value=1;cost=d+1;}
        // Nearby allies already working this living group provide useful damage, but don't herd everyone into it.
        int competitors=0;for(auto p:allypositions)if(cheb(p,o.anchor)<=3)++competitors;
        cost*=10+competitors*Config::competition_cost;
        if(value*bestcost>bestvalue*cost||(value*bestcost==bestvalue*cost&&d<best_distance)){
            best=i;bestvalue=value;bestcost=cost;best_distance=d;
        }
    }
    if(!bootstrap){int planned=preferred_loop_camp(w,eligible);if(planned>=0)return planned;}
    return best;
}
AltarSelection choose_altar(World& w,const Snapshot& s,TurnBudget& b,int previous) {
    if(!b.admit()||b.fields>=1)return {};
    distance_field f;bitboard reached;auto blocked=s.blocked|s.risk;blocked.set(s.pos,false);++b.fields;f.compute(blocked,around(s.pos,0),reached);
    if(!b.current()||fuel_remaining()<Config::reserve)return {};
    int best=-1,score=100000,old=100000;
    bool spatial=false,previous_eligible=false;
    for(int i=0;i<int(w.altars.size());++i) {
        int d=65535;auto goals=around(w.altars[i],1)&~blocked;
        for(auto p:goals.positions())if(reached.is_set(p))d=std::min(d,int(f.get(p)));
        if(d==65535)continue;
        spatial=true;
        if(w.altar_retry[i]>s.round)continue;
        int v=d+(s.visible.is_set(w.altars[i])?0:2);
        for(const auto& lock:vision::altar_locks(team::enemy))if(lock.position()==w.altars[i])v+=lock.hits_remaining();
        for(const auto& e:s.foes)if(cheb(e.position(),w.altars[i])<=6)v+=6;
        if(i==previous){old=v;previous_eligible=true;}if(v<score){score=v;best=i;}
    }
    // Geometry and scoring both invoke the host; field admission is not completion.
    if(!b.current()||fuel_remaining()<Config::reserve)return {};
    if(previous_eligible&&old<=score+3)best=previous;
    if(best>=0)return {AltarStatus::selected,best};
    return {spatial?AltarStatus::cooldown:AltarStatus::unavailable};
}
void apply_altar_selection(AltarSelection result,const Snapshot& s,TurnBudget& b,Memory& m) {
    if(result.status==AltarStatus::deferred)return;
    bool urgent=false;
    if(result.status==AltarStatus::unavailable&&s.bag>0)
        urgent=hard_bank_due(s.bag,s.round,global_submitted_gems(team::ally));
    // In particular, urgency's score query must not turn stale failure into admission.
    if(!b.current()||fuel_remaining()<Config::reserve)return;
    if(result.status==AltarStatus::selected) {
        m.altar=result.index;m.bank_unavailable_round=-1;return;
    }
    m.altar=-1;m.queue_started=-1;
    if(result.status==AltarStatus::unavailable) {
        if(s.bag>0&&!urgent)m.bank_unavailable_round=s.round;
        else m.bank_unavailable_round=-1;
    }
}
bool explore(World& w,TurnBudget& b,Memory& m) {
    const auto& s=observe();
    if(m.exploration<0||s.round-m.exploration_started>=8||m.blocked>=3||cheb(s.pos,w.camps[m.exploration].anchor)<=1) {
        int best=-1;auto rank=std::tuple{100000,100000,100000};
        for(int i=0;i<int(w.camps.size());++i) {
            auto& o=w.camps[i];if(o.cooldown>s.round)continue;
            // Least recently observed first, travel breaks ties; stagger equivalent initial choices.
            auto v=std::tuple{o.seen,cheb(s.pos,o.anchor),(i+w.slot)%std::max(1,int(w.camps.size()))};
            if(v<rank){rank=v;best=i;}
        }
        m.exploration=best;m.exploration_started=s.round;m.blocked=0;
    }
    if(m.exploration<0)return false;
    return move_to(camp_goals(w.camps[m.exploration],s),true,b,m)==RouteStatus::moved;
}
}
