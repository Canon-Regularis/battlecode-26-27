#pragma once
// SDK-independent, owned scene and single controller shared by native scenarios and production.
#include "model.h"
#include <memory>
#include <vector>
#include <tuple>
namespace lp::recovery {
struct Point {int x=0,y=0; friend bool operator==(Point,Point)=default;};
inline int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
struct Epoch {int actor=0,life=0,round=0;unsigned revision=0;friend bool operator==(Epoch,Epoch)=default;};
struct Limits {static constexpr int cells=16384,enemies=32,camps=256,groups=128,queries=4096,
    abilities=2,candidates=417,bfs_nodes=121,bfs_edges=968,captures=6,effect_radius=2;};
struct Terrain {
    int width=0,height=0;
    std::vector<unsigned char> blocked,spawn;
    std::vector<unsigned short> home; // full static-only field, 65535 means unreachable
    bool inside(Point p)const{return p.x>=0&&p.y>=0&&p.x<width&&p.y<height;}
    int index(Point p)const{return p.y*width+p.x;}
};
struct Threat {Point pos;int range=0;float strength=0;};
struct Camp {Point pos;int group=-1,range=0;float strength=0;bool known=false,alive=false,awake=false;};
struct Dash {bool available=false,supported=false,damage=false,stun=false;int range=0,radius=0,slot=-1;};
struct Scene {
    Epoch epoch;
    std::shared_ptr<const Terrain> terrain;
    std::vector<unsigned char> visible,occupied;
    std::vector<Threat> enemies;
    std::vector<Camp> camps;
    Point pos;
    float hp=0,max_hp=1;
    bool alive=false,completed=false,stunned=false,can_move=false,can_cast=false,
        move_restricted=false,cast_restricted=false,recalling=false,tribute=false,teleport=false;
    bool recall_started=false,recall_cancelled=false,movement_spent=false;
    int timer=0,groups=0;
    Dash dash;
    bool spawn()const{return terrain->spawn[terrain->index(pos)];}
    bool physical(Point p,Point origin)const {
        if(!terrain->inside(p))return false;
        int i=terrain->index(p);
        return visible[i]&&!terrain->blocked[i]&&(!occupied[i]||p==origin);
    }
};
enum class Intent {health,evasion};
enum class Status {ready,channeling,reached_spawn,recovered,partial,blocked,no_improvement,
    incomplete,initialization_deferred,stale,defensive_wait,cancelled_wait};
enum class Kind {stay,step,dash,cancel,recall};
struct Action {Kind kind=Kind::stay;Point target;int slot=-1;friend bool operator==(Action,Action)=default;};
struct Outcome {
    Status status=Status::no_improvement;
    int moves=0,dashes=0,motion_attempts=0,cancellations=0,recall_starts=0,defenses=0,captures=0,candidates=0,effect_unknown=0,risk_rejections=0;
    bool homeward=false;
    std::vector<Action> history;
    bool stop_dispatch()const{return status==Status::stale||status==Status::incomplete||status==Status::initialization_deferred;}
};
struct Plan {Action first;int actions=0,raw=0,effect_unknown=0,risk_rejections=0;bool complete=true;};
// No backend queries occur in select_plan, effects, or BFS. Stay participates in the same ranking.
Plan select_plan(const Scene&,bool allow_step=true,bool allow_dash=true);
struct Halt {Status status;};
struct Backend {
    virtual ~Backend()=default;
    virtual Epoch epoch()=0;
    virtual bool current(Epoch)=0;
    virtual Status prepare(Epoch)=0;
    virtual Status capture(Scene&)=0;
    // Issue performs exact live permissions/epoch preflight. A false result is a blocked attempt.
    virtual bool issue(const Scene&,Action)=0;
    // At most one compatible primitive; no movement, channels, or opaque legacy dispatch.
    virtual bool defend(const Scene&)=0;
};
Outcome execute(Intent,Memory&,Backend&);
inline bool routes(State state,bool health){return state==State::escape||(state==State::recall&&health);}
}
