// Executes extracted, unmodified production refresh bodies with scripted host-facing
// SDK substitutes. Memory, Config and task_expired come from production model.h.
#include "model.h"
#include <cassert>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <variant>
#include <vector>
namespace lp {
enum class error_code { api_not_in_vision, api_not_found, api_value_out_of_range };
struct error : std::runtime_error {
    error_code value;
    explicit error(error_code c):std::runtime_error("scripted SDK error"),value(c){}
    error_code code() const {return value;}
};
struct vec2 {int x,y;};
struct bitboard {
    std::uint64_t bits=0;
    bool is_set(vec2 p) const {return (bits&(1ULL<<p.x))!=0;}
    bool is_empty() const {return !bits;}
    friend bitboard operator&(bitboard a,bitboard b){return {a.bits&b.bits};}
};
struct Snapshot {int round=0;bitboard visible;};
int host_round=0,round_calls=0,roll_on_round_call=0;
unsigned version=0;
unsigned observation_version(){return version;}
unsigned round_number(){++round_calls;if(round_calls==roll_on_round_call)++host_round;return host_round;}
struct HostCamp {
    bool live_info=true,dead=false;
    float hp=120;
    int failure=-1;
    bool rollover=false;
    mutable int info_calls=0,state_calls=0,health_calls=0,base_calls=0;
};
std::vector<HostCamp> host;
struct Camp {
    int index;
    vec2 spawn_position() const {return {index,0};}
    bool is_visible() const {++host[index].info_calls;return host[index].live_info;}
    bool state_dead() const {
        auto& h=host[index];++h.state_calls;
        if(h.rollover)++host_round;
        if(h.failure>=0)throw error(static_cast<error_code>(h.failure));
        return h.dead;
    }
    bool is_alive() const {return !state_dead();}
    bool is_dead() const {return state_dead();}
    float health() const {auto& h=host[index];assert(h.live_info&&!h.dead);++h.health_calls;return h.hp;}
    struct Stats {float base_health;};
    Stats base_stats() const {++host[index].base_calls;return {120};}
};
namespace map {
struct camp_group_alive {};
struct camp_group_reward_available {};
struct camp_group_respawning {int timer;};
using State=std::variant<camp_group_alive,camp_group_reward_available,camp_group_respawning>;
struct Group {
    std::vector<Camp> members;
    State status=camp_group_alive{};
    int timer=5;
    mutable int state_calls=0,capture_calls=0;
    State state() const {++state_calls;return status;}
    struct Capture {int timer;};
    Capture capture_state() const {++capture_calls;return {timer};}
    const std::vector<Camp>& camps() const {return members;}
};
}
struct Objective {
    map::Group group;
    bitboard tiles;
    int seen=-1000,respawn=0,capture_timer=5,lifecycle=1;
    float remaining=0,design_health=0;
};
struct World {
    std::vector<Objective> camps;
    int refreshed_round=-1;unsigned refreshed_version=0;
    void refresh(const Snapshot&,Memory&);
    void refresh_reference(const Snapshot&,Memory&);
};
#include "refresh-under-test.h"
#include "refresh-reference.h"
World make_world(int n=1) {
    host.assign(n,HostCamp{});host_round=0;round_calls=0;roll_on_round_call=0;
    World w;Objective o;o.tiles.bits=(1ULL<<n)-1;o.remaining=o.design_health=n*120;
    for(int i=0;i<n;++i)o.group.members.push_back({i});
    w.camps.push_back(o);return w;
}
void run(World& w,Memory& m,int r,std::uint64_t visible=~0ULL,bool reference=false) {
    host_round=r;round_calls=0;++version;Snapshot s{r,{visible}};
    if(reference)w.refresh_reference(s,m);else w.refresh(s,m);
}
void natural(bool reference) {
    auto w=make_world(49);Memory m;m.task=0;m.task_started=20;m.progressed=20;
    for(int i=0;i<6;++i){host[i].live_info=false;host[i].dead=true;}
    run(w,m,29,~0ULL,reference);
    assert(w.camps[0].remaining==(reference?5880:5160));assert(m.progressed==(reference?20:29));
    host[6].hp=10;run(w,m,30,~0ULL,reference);
    assert(w.camps[0].remaining==(reference?5770:5050));assert(m.progressed==30);
    host[6].live_info=false;host[6].dead=true;run(w,m,34,~0ULL,reference);
    assert(w.camps[0].remaining==(reference?5880:5040));assert(m.progressed==(reference?30:34));
    run(w,m,38,~0ULL,reference);
    assert(task_expired(38,m.task_started,m.progressed)==reference);
    for(int i=0;i<7;++i)assert(host[i].health_calls==(i==6?2:0));
}
void checks() {
    natural(true);natural(false);
    auto w=make_world();Memory m;m.task=0;m.progressed=20;
    host[0].hp=10;run(w,m,30);assert(m.progressed==30);
    host[0].hp=5;run(w,m,34);assert(m.progressed==34&&w.camps[0].remaining==5);
    run(w,m,38);assert(m.progressed==34&&!task_expired(38,0,m.progressed));
    assert(round_calls==0); // No new round queries on the live branch.
    host[0].dead=true;run(w,m,39);assert(w.camps[0].remaining==0&&m.progressed==39);
    assert(host[0].health_calls==3); // Never dead live health.

    // Group remains visible via member 1 while member 0's spawn is hidden.
    for(bool dead:{false,true}) {
        w=make_world(2);host[0].live_info=false;host[0].dead=dead;
        run(w,m,40,2);assert(w.camps[0].remaining==240);
        assert(host[0].state_calls==0&&host[0].health_calls==0&&round_calls==0);
    }
    w=make_world();host[0].live_info=false;run(w,m,41);
    assert(w.camps[0].remaining==120&&host[0].state_calls==1&&host[0].health_calls==0&&round_calls==2);
    for(auto failure:{error_code::api_not_in_vision,error_code::api_not_found}) {
        w=make_world();host[0].live_info=false;host[0].dead=true;host[0].failure=int(failure);
        m.progressed=20;run(w,m,42);assert(w.camps[0].remaining==120&&m.progressed==20);
    }
    w=make_world();host[0].live_info=false;host[0].failure=int(error_code::api_value_out_of_range);
    bool threw=false;try {run(w,m,43);}catch(const error& e){threw=e.code()==error_code::api_value_out_of_range;}
    assert(threw);
    // Stale before probe, during probe, or during post-query round check.
    for(int crossing:{0,1,2}) {
        w=make_world();host[0].live_info=false;host[0].dead=true;
        if(crossing==0)roll_on_round_call=1;
        if(crossing==1)host[0].rollover=true;
        if(crossing==2)roll_on_round_call=2;
        m.progressed=20;run(w,m,44);
        assert(w.camps[0].remaining==120&&m.progressed==20);
        assert(host[0].state_calls==(crossing==0?0:1)&&host[0].health_calls==0);
    }
    // Fully dead group uses unchanged reward/capture path, then respawn/living.
    w=make_world();host[0].live_info=false;host[0].dead=true;
    w.camps[0].group.status=map::camp_group_reward_available{};run(w,m,45);
    assert(w.camps[0].remaining==0&&w.camps[0].lifecycle==2&&m.progressed==45);
    w.camps[0].group.timer=4;run(w,m,46);assert(m.progressed==46);
    run(w,m,47);assert(m.progressed==46);
    w.camps[0].group.status=map::camp_group_respawning{10};run(w,m,48);
    assert(w.camps[0].lifecycle==3&&w.camps[0].respawn==58&&m.progressed==46);
    w.camps[0].group.status=map::camp_group_alive{};host[0]=HostCamp{};run(w,m,58);
    assert(w.camps[0].remaining==120&&w.camps[0].lifecycle==1&&m.progressed==46);
    assert(host[0].health_calls==1&&round_calls==0);
    // Noncommitted scheduling/design-health and hidden group skip remain intact.
    w=make_world();m.task=-1;m.progressed=20;host[0].live_info=false;host[0].dead=true;
    run(w,m,63);assert(w.camps[0].group.state_calls==0);
    run(w,m,64);assert(w.camps[0].remaining==120&&m.progressed==20&&host[0].info_calls==0&&host[0].state_calls==0);
    m.task=0;run(w,m,65,0);assert(w.camps[0].group.state_calls==1);
    assert(Config::stall==8&&Config::task_limit==90);
    assert(!task_expired(37,20,30)&&task_expired(38,20,30));
    assert(!task_expired(89,0,88)&&task_expired(90,0,89));
    // Existing same-round/version refresh suppression remains effective.
    auto calls=w.camps[0].group.state_calls;
    w.refresh(Snapshot{65,{~0ULL}},m);assert(w.camps[0].group.state_calls==calls);
}
}
int main(){lp::checks();std::cout<<"PASS committed refresh/progress contracts (parent and candidate)\n";}
